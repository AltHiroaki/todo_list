"""Background worker for Google Tasks sync."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from app import database as db
from app.application.usecases.refresh_on_show import RefreshOnShowUseCase
from app.domain.models import AppSyncState, TaskItem
from app.google_sync import google_sync
from app.infrastructure.cache.json_cache import JsonCache
from app.infrastructure.google.tasks_gateway import GoogleTasksGateway


class SyncWorker(QObject):
    """Worker object living in a QThread for network + DB sync operations."""

    data_changed = pyqtSignal()
    sync_finished = pyqtSignal()
    sync_error = pyqtSignal(str)
    offline_mode = pyqtSignal()
    tasklists_loaded = pyqtSignal(object, str)  # list[dict], selected_tasklist_id

    def __init__(self):
        super().__init__()
        self._refresh_usecase = RefreshOnShowUseCase(
            gateway=GoogleTasksGateway(),
            cache=JsonCache(),
        )

    def initial_sync(self):
        if not google_sync.is_available():
            self.offline_mode.emit()
            self.sync_finished.emit()
            return

        if not google_sync.authenticate():
            self.offline_mode.emit()
            self.sync_finished.emit()
            return

        try:
            result = self._refresh_usecase.execute(tasklist_id=google_sync.tasklist_id)
            self._emit_tasklists(result.tasklists)
            changed = self._apply_remote_tasks(result.tasks, result.state, google_sync.tasklist_id)
            self._apply_result_state(result.state, result.error_message)
            if changed:
                self.data_changed.emit()
        except Exception as exc:  # pragma: no cover - defensive signal path
            self.sync_error.emit(str(exc))
        finally:
            self.sync_finished.emit()

    def poll_tasks(self):
        try:
            result = self._refresh_usecase.execute(tasklist_id=google_sync.tasklist_id)
            self._emit_tasklists(result.tasklists)
            changed = self._apply_remote_tasks(result.tasks, result.state, google_sync.tasklist_id)
            self._apply_result_state(result.state, result.error_message)
            if changed:
                self.data_changed.emit()
        except Exception as exc:  # pragma: no cover - defensive signal path
            self.sync_error.emit(str(exc))
        finally:
            self.sync_finished.emit()

    def push_add_request(self, title: str, due_date: str = ""):
        created = google_sync.add_task(title, due_date=due_date or None)
        if not created:
            self.sync_error.emit("Google Tasksへのタスク追加に失敗しました。")
            self.sync_finished.emit()
            return
        self.poll_tasks()

    def push_toggle(self, task_id: int, is_done: bool):
        gid = db.get_google_task_id(task_id)
        if not gid:
            return
        if is_done:
            google_sync.complete_task(gid)
        else:
            google_sync.reopen_task(gid)
        self.poll_tasks()

    def push_update_details(self, task_id: int, title: str, due_date: object, notes: str):
        gid = db.get_google_task_id(task_id)
        if not gid:
            return
        due_text = due_date if isinstance(due_date, str) else None
        ok = google_sync.update_task_details(
            gid,
            title=title,
            due_date=due_text,
            notes=notes or "",
        )
        if not ok:
            self.sync_error.emit("Google Tasks上のタスク更新に失敗しました。")
        self.poll_tasks()

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
        if state != AppSyncState.IDLE and not remote_tasks and db.get_all_tasks(tasklist_id=tasklist_id):
            # Guard against transient empty payloads wiping local data in offline/error paths.
            return False

        changed = False
        remote_map = {item.id: item for item in remote_tasks}

        local_tasks = db.get_all_tasks(tasklist_id=tasklist_id)
        local_map = {item["google_task_id"]: item for item in local_tasks if item["google_task_id"]}

        conn = db._get_connection()

        for gid, remote in remote_map.items():
            title = remote.title
            is_completed = remote.is_completed
            due_date = remote.due.isoformat() if remote.due else None
            remote_completed = remote.completed
            position = remote.position
            parent_gid = remote.parent
            notes = remote.notes or ""

            if gid in local_map:
                local = local_map[gid]
                updates = []
                params = []

                if local["title"] != title:
                    updates.append("title = ?")
                    params.append(title)

                if local.get("due_date") != due_date:
                    updates.append("due_date = ?")
                    params.append(due_date)

                if local.get("google_position") != position:
                    updates.append("google_position = ?")
                    params.append(position)

                if local.get("parent_google_id") != parent_gid:
                    updates.append("parent_google_id = ?")
                    params.append(parent_gid)

                if (local.get("notes") or "") != notes:
                    updates.append("notes = ?")
                    params.append(notes)

                local_done = bool(local["is_done"])
                if local_done != is_completed:
                    updates.append("is_done = ?")
                    params.append(1 if is_completed else 0)

                    if is_completed:
                        completed_at = datetime.now().isoformat()
                        if remote_completed:
                            try:
                                z_value = remote_completed.replace("Z", "+00:00")
                                dt_utc = datetime.fromisoformat(z_value)
                                completed_at = dt_utc.astimezone().replace(tzinfo=None).isoformat()
                            except Exception:
                                completed_at = remote_completed
                        updates.append("completed_at = ?")
                        params.append(completed_at)
                    else:
                        updates.append("completed_at = ?")
                        params.append(None)

                if updates:
                    params.append(local["id"])
                    conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", tuple(params))
                    changed = True
            else:
                created_at = datetime.now().isoformat()
                is_done_val = 1 if is_completed else 0
                completed_at = remote_completed if (is_completed and remote_completed) else (created_at if is_completed else None)

                conn.execute(
                    """
                    INSERT INTO tasks (
                        title, is_done, created_at, completed_at,
                        due_date, tasklist_id, google_task_id, google_position,
                        parent_google_id, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (title, is_done_val, created_at, completed_at, due_date, tasklist_id, gid, position, parent_gid, notes),
                )
                changed = True

        for gid, local in local_map.items():
            if gid not in remote_map:
                conn.execute("DELETE FROM tasks WHERE id = ?", (local["id"],))
                changed = True

        if changed:
            conn.commit()
        conn.close()
        return changed
