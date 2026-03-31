"""Background worker for Google Tasks sync."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from app.auth.errors import AuthRequiredError
from app.auth.google_sync import google_sync
from app.application.usecases.refresh_on_show import RefreshOnShowUseCase
from app.domain.models import AppSyncState, TaskItem
from app.infrastructure.cache.json_cache import JsonCache
from app.infrastructure.google.tasks_gateway import GoogleTasksGateway
from app.infrastructure.storage import database as db


class SyncWorker(QObject):
    """Worker object living in a QThread for network + DB sync operations."""

    data_changed = pyqtSignal()
    sync_finished = pyqtSignal()
    sync_error = pyqtSignal(str)
    auth_required = pyqtSignal(str)
    offline_mode = pyqtSignal()
    tasklists_loaded = pyqtSignal(object, str)  # list[dict], selected_tasklist_id

    def __init__(self):
        super().__init__()
        self._refresh_usecase = RefreshOnShowUseCase(
            gateway=GoogleTasksGateway(),
            cache=JsonCache(),
        )

    def initial_sync(self):
        self._run_refresh_cycle(require_available=True, require_authentication=True)

    def poll_tasks(self):
        self._run_refresh_cycle()

    def push_add_request(self, title: str, due_date: str = ""):
        try:
            created = google_sync.add_task(title, due_date=due_date or None)
        except AuthRequiredError as exc:
            self._emit_auth_required(exc)
            self.sync_finished.emit()
            return
        if not created:
            self.sync_error.emit("Google Tasksへのタスク追加に失敗しました。")
            self.sync_finished.emit()
            return
        self.poll_tasks()

    def push_toggle(self, task_id: int, is_done: bool):
        gid = db.get_google_task_id(task_id)
        if not gid:
            self.sync_finished.emit()
            return
        try:
            if is_done:
                google_sync.complete_task(gid)
            else:
                google_sync.reopen_task(gid)
        except AuthRequiredError as exc:
            self._emit_auth_required(exc)
            self.sync_finished.emit()
            return
        self.poll_tasks()

    def push_update_details(self, task_id: int, title: str, due_date: object, notes: str):
        gid = db.get_google_task_id(task_id)
        if not gid:
            self.sync_finished.emit()
            return
        due_text = due_date if isinstance(due_date, str) else None
        try:
            ok = google_sync.update_task_details(
                gid,
                title=title,
                due_date=due_text,
                notes=notes or "",
            )
        except AuthRequiredError as exc:
            self._emit_auth_required(exc)
            self.sync_finished.emit()
            return
        if not ok:
            self.sync_error.emit("Google Tasks上のタスク更新に失敗しました。")
        self.poll_tasks()

    def _run_refresh_cycle(
        self,
        *,
        require_available: bool = False,
        require_authentication: bool = False,
    ) -> None:
        if require_available and not google_sync.is_available():
            self.offline_mode.emit()
            self.sync_finished.emit()
            return

        try:
            if require_authentication and not google_sync.authenticate():
                self.offline_mode.emit()
                return
            self._refresh_selected_tasklist()
        except AuthRequiredError as exc:
            self._emit_auth_required(exc)
        except Exception as exc:  # pragma: no cover - defensive signal path
            self.sync_error.emit(str(exc))
        finally:
            self.sync_finished.emit()

    def _refresh_selected_tasklist(self) -> None:
        result = self._refresh_usecase.execute(tasklist_id=google_sync.tasklist_id)
        self._emit_tasklists(result.tasklists)
        changed = self._apply_remote_tasks(result.tasks, result.state, google_sync.tasklist_id)
        self._apply_result_state(result.state, result.error_message)
        if changed:
            self.data_changed.emit()

    def _emit_auth_required(self, exc: AuthRequiredError) -> None:
        self.auth_required.emit(str(exc))

    def _emit_tasklists(self, tasklists):
        payload = [{"id": item.id, "title": item.title} for item in tasklists]
        if payload:
            self.tasklists_loaded.emit(payload, google_sync.tasklist_id)

    def _apply_result_state(self, state: AppSyncState, error_message: str):
        if state == AppSyncState.OFFLINE_READONLY:
            self.offline_mode.emit()
        elif state == AppSyncState.BLOCKING_ERROR:
            self.sync_error.emit(error_message or "Google Tasksからの取得に失敗しました。")

    def _apply_remote_tasks(self, remote_tasks: list[TaskItem], state: AppSyncState, tasklist_id: str) -> bool:
        """Mirror remote task state into local cache DB for the selected tasklist."""
        if self._should_preserve_local_cache(remote_tasks, state, tasklist_id):
            # Guard against transient empty payloads wiping local data in offline/error paths.
            return False

        remote_map = {item.id: item for item in remote_tasks}
        local_tasks = db.get_all_tasks(tasklist_id=tasklist_id)
        local_map = {item["google_task_id"]: item for item in local_tasks if item["google_task_id"]}
        conn = db._get_connection()
        changed = False

        try:
            for gid, remote in remote_map.items():
                local = local_map.get(gid)
                if local is None:
                    self._insert_remote_task(conn, remote, tasklist_id)
                    changed = True
                    continue

                if self._update_local_task(conn, local, remote):
                    changed = True

            if self._delete_missing_local_tasks(conn, local_map, remote_map):
                changed = True

            if changed:
                conn.commit()
            return changed
        finally:
            conn.close()

    @staticmethod
    def _should_preserve_local_cache(
        remote_tasks: list[TaskItem],
        state: AppSyncState,
        tasklist_id: str,
    ) -> bool:
        return state != AppSyncState.IDLE and not remote_tasks and bool(db.get_all_tasks(tasklist_id=tasklist_id))

    def _update_local_task(self, conn, local: dict, remote: TaskItem) -> bool:
        updates, params = self._build_local_update(local, remote)
        if not updates:
            return False

        params.append(local["id"])
        conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", tuple(params))
        return True

    def _build_local_update(self, local: dict, remote: TaskItem) -> tuple[list[str], list[object]]:
        updates: list[str] = []
        params: list[object] = []

        field_pairs = (
            ("title", local["title"], remote.title),
            ("due_date", local.get("due_date"), remote.due.isoformat() if remote.due else None),
            ("google_position", local.get("google_position"), remote.position),
            ("parent_google_id", local.get("parent_google_id"), remote.parent),
            ("notes", local.get("notes") or "", remote.notes or ""),
        )
        for column, current_value, new_value in field_pairs:
            if current_value != new_value:
                updates.append(f"{column} = ?")
                params.append(new_value)

        local_done = bool(local["is_done"])
        if local_done != remote.is_completed:
            updates.append("is_done = ?")
            params.append(1 if remote.is_completed else 0)
            updates.append("completed_at = ?")
            params.append(self._completed_at_for_existing_task(remote) if remote.is_completed else None)

        return updates, params

    def _insert_remote_task(self, conn, remote: TaskItem, tasklist_id: str) -> None:
        created_at = datetime.now().isoformat()
        is_done_val = 1 if remote.is_completed else 0
        completed_at = self._completed_at_for_new_task(remote, created_at)

        conn.execute(
            """
            INSERT INTO tasks (
                title, is_done, created_at, completed_at,
                due_date, tasklist_id, google_task_id, google_position,
                parent_google_id, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                remote.title,
                is_done_val,
                created_at,
                completed_at,
                remote.due.isoformat() if remote.due else None,
                tasklist_id,
                remote.id,
                remote.position,
                remote.parent,
                remote.notes or "",
            ),
        )

    @staticmethod
    def _delete_missing_local_tasks(conn, local_map: dict, remote_map: dict[str, TaskItem]) -> bool:
        changed = False
        for gid, local in local_map.items():
            if gid not in remote_map:
                conn.execute("DELETE FROM tasks WHERE id = ?", (local["id"],))
                changed = True
        return changed

    @staticmethod
    def _completed_at_for_existing_task(remote: TaskItem) -> str:
        completed_at = datetime.now().isoformat()
        if not remote.completed:
            return completed_at

        try:
            z_value = remote.completed.replace("Z", "+00:00")
            dt_utc = datetime.fromisoformat(z_value)
            return dt_utc.astimezone().replace(tzinfo=None).isoformat()
        except Exception:
            return remote.completed

    @staticmethod
    def _completed_at_for_new_task(remote: TaskItem, created_at: str) -> str | None:
        if not remote.is_completed:
            return None
        return remote.completed or created_at
