from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.domain.models import TaskItem, TaskListItem, TaskStatus
from app.infrastructure.google.auth_service import GoogleAuthService


logger = logging.getLogger(__name__)


def _parse_date(value: str | None):
    if not value:
        return None
    # RFC3339: YYYY-MM-DDTHH:MM:SS.sssZ
    raw = value.split("T")[0]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


class GoogleTasksGateway:
    def __init__(self, auth_service: GoogleAuthService | None = None):
        self.auth = auth_service or GoogleAuthService()

    def is_available(self) -> bool:
        return self.auth.is_available()

    def _service(self):
        return self.auth.get_service()

    def list_tasklists(self) -> list[TaskListItem]:
        service = self._service()
        if service is None:
            return []

        try:
            response = service.tasklists().list(maxResults=100).execute()
            return [
                TaskListItem(id=item["id"], title=item.get("title", "(無題)"))
                for item in response.get("items", [])
            ]
        except Exception:
            logger.exception("Failed to list tasklists from Google Tasks.")
            return []

    def list_tasks(
        self,
        tasklist_id: str = "@default",
        *,
        include_completed: bool = False,
        include_hidden: bool = False,
    ) -> list[TaskItem]:
        service = self._service()
        if service is None:
            return []

        try:
            response = service.tasks().list(
                tasklist=tasklist_id,
                showCompleted=include_completed,
                showHidden=include_hidden,
            ).execute()
            items = response.get("items", [])
            return [self._to_task_item(item, tasklist_id=tasklist_id) for item in items]
        except Exception:
            logger.exception("Failed to list tasks from Google Tasks.")
            return []

    def list_completed(self, tasklist_id: str = "@default", days: int = 30) -> list[TaskItem]:
        service = self._service()
        if service is None:
            return []

        bounded_days = min(max(days, 30), 365)
        completed_min = (datetime.now(timezone.utc) - timedelta(days=bounded_days)).isoformat()

        try:
            response = service.tasks().list(
                tasklist=tasklist_id,
                showCompleted=True,
                showHidden=True,
                completedMin=completed_min,
            ).execute()
            result = []
            for item in response.get("items", []):
                if item.get("status") == TaskStatus.COMPLETED.value:
                    result.append(self._to_task_item(item, tasklist_id=tasklist_id))
            return result
        except Exception:
            logger.exception("Failed to list completed tasks from Google Tasks.")
            return []

    def add_task(self, title: str, due_date: str | None = None, tasklist_id: str = "@default") -> TaskItem | None:
        service = self._service()
        if service is None:
            return None

        body = {
            "title": title,
            "status": TaskStatus.NEEDS_ACTION.value,
        }
        if due_date:
            body["due"] = f"{due_date}T00:00:00.000Z"

        try:
            created = service.tasks().insert(tasklist=tasklist_id, body=body).execute()
            return self._to_task_item(created, tasklist_id=tasklist_id)
        except Exception:
            logger.exception("Failed to add task to Google Tasks.")
            return None

    def update_task(self, task_id: str, patch: dict, tasklist_id: str = "@default") -> TaskItem | None:
        service = self._service()
        if service is None or not task_id:
            return None

        try:
            current = service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
            current.update(patch)
            updated = service.tasks().update(tasklist=tasklist_id, task=task_id, body=current).execute()
            return self._to_task_item(updated, tasklist_id=tasklist_id)
        except Exception:
            logger.exception("Failed to update task in Google Tasks.")
            return None

    def complete_task(self, task_id: str, tasklist_id: str = "@default") -> bool:
        updated = self.update_task(task_id=task_id, patch={"status": TaskStatus.COMPLETED.value}, tasklist_id=tasklist_id)
        return updated is not None

    def reopen_task(self, task_id: str, tasklist_id: str = "@default") -> bool:
        updated = self.update_task(
            task_id=task_id,
            patch={"status": TaskStatus.NEEDS_ACTION.value, "completed": None},
            tasklist_id=tasklist_id,
        )
        return updated is not None

    def update_title(self, task_id: str, new_title: str, tasklist_id: str = "@default") -> bool:
        updated = self.update_task(task_id=task_id, patch={"title": new_title}, tasklist_id=tasklist_id)
        return updated is not None

    def update_due_date(self, task_id: str, due_date: str | None, tasklist_id: str = "@default") -> bool:
        patch = {"due": f"{due_date}T00:00:00.000Z"} if due_date else {"due": None}
        updated = self.update_task(task_id=task_id, patch=patch, tasklist_id=tasklist_id)
        return updated is not None

    @staticmethod
    def _to_task_item(item: dict, *, tasklist_id: str) -> TaskItem:
        status = item.get("status", TaskStatus.NEEDS_ACTION.value)
        task_status = TaskStatus.COMPLETED if status == TaskStatus.COMPLETED.value else TaskStatus.NEEDS_ACTION

        return TaskItem(
            id=item["id"],
            title=item.get("title", ""),
            status=task_status,
            tasklist_id=tasklist_id,
            due=_parse_date(item.get("due")),
            completed=item.get("completed"),
            notes=item.get("notes", ""),
            parent=item.get("parent"),
            position=item.get("position"),
        )
