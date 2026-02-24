from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import AppSyncState, TaskItem, TaskListItem
from app.infrastructure.cache.json_cache import JsonCache
from app.infrastructure.google.tasks_gateway import GoogleTasksGateway


@dataclass(slots=True)
class RefreshResult:
    state: AppSyncState
    tasklists: list[TaskListItem]
    tasks: list[TaskItem]
    from_cache: bool = False
    error_message: str = ""


class RefreshOnShowUseCase:
    def __init__(self, gateway: GoogleTasksGateway, cache: JsonCache):
        self.gateway = gateway
        self.cache = cache

    def execute(self, tasklist_id: str = "@default") -> RefreshResult:
        if not self.gateway.is_available():
            cached = self._load_cached(tasklist_id)
            if cached:
                return RefreshResult(
                    state=AppSyncState.OFFLINE_READONLY,
                    tasklists=cached[0],
                    tasks=cached[1],
                    from_cache=True,
                    error_message="Google APIを利用できないため、キャッシュを表示しています。",
                )
            return RefreshResult(
                state=AppSyncState.BLOCKING_ERROR,
                tasklists=[],
                tasks=[],
                error_message="Google APIを利用できず、キャッシュもありません。",
            )

        tasklists = self.gateway.list_tasklists()
        tasks = self.gateway.list_tasks(
            tasklist_id=tasklist_id,
            include_completed=True,
            include_hidden=True,
        )
        if tasklists or tasks:
            self._save_cache(tasklist_id=tasklist_id, tasklists=tasklists, tasks=tasks)
            return RefreshResult(state=AppSyncState.IDLE, tasklists=tasklists, tasks=tasks)

        cached = self._load_cached(tasklist_id)
        if cached:
            return RefreshResult(
                state=AppSyncState.OFFLINE_READONLY,
                tasklists=cached[0],
                tasks=cached[1],
                from_cache=True,
                error_message="Google Tasksに接続できないため、キャッシュを表示しています。",
            )

        return RefreshResult(
            state=AppSyncState.BLOCKING_ERROR,
            tasklists=[],
            tasks=[],
            error_message="Google Tasksからの取得に失敗しました。",
        )

    def _save_cache(self, tasklist_id: str, tasklists: list[TaskListItem], tasks: list[TaskItem]) -> None:
        self.cache.save(
            name=f"tasklists_{tasklist_id}",
            payload={"items": [{"id": t.id, "title": t.title} for t in tasklists]},
        )
        self.cache.save(
            name=f"tasks_{tasklist_id}",
            payload={
                "items": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "status": t.status.value,
                        "tasklist_id": t.tasklist_id,
                        "due": t.due.isoformat() if t.due else None,
                        "completed": t.completed,
                        "notes": t.notes,
                        "parent": t.parent,
                        "position": t.position,
                    }
                    for t in tasks
                ]
            },
        )

    def _load_cached(self, tasklist_id: str) -> tuple[list[TaskListItem], list[TaskItem]] | None:
        cached_lists = self.cache.load(name=f"tasklists_{tasklist_id}")
        cached_tasks = self.cache.load(name=f"tasks_{tasklist_id}")
        if not cached_lists and not cached_tasks:
            return None

        tasklists = []
        for item in (cached_lists or {}).get("payload", {}).get("items", []):
            if "id" in item:
                tasklists.append(TaskListItem(id=item["id"], title=item.get("title", "")))

        from datetime import date
        from app.domain.models import TaskStatus

        tasks = []
        for item in (cached_tasks or {}).get("payload", {}).get("items", []):
            status_val = item.get("status", TaskStatus.NEEDS_ACTION.value)
            status = TaskStatus.COMPLETED if status_val == TaskStatus.COMPLETED.value else TaskStatus.NEEDS_ACTION
            due_raw = item.get("due")
            due = date.fromisoformat(due_raw) if due_raw else None
            tasks.append(
                TaskItem(
                    id=item["id"],
                    title=item.get("title", ""),
                    status=status,
                    tasklist_id=item.get("tasklist_id", tasklist_id),
                    due=due,
                    completed=item.get("completed"),
                    notes=item.get("notes", ""),
                    parent=item.get("parent"),
                    position=item.get("position"),
                )
            )

        return tasklists, tasks
