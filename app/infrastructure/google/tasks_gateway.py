from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.auth.errors import AuthRequiredError
from app.domain.models import TaskItem, TaskListItem, TaskStatus
from app.infrastructure.google.auth_service import GoogleAuthService

try:
    from google.auth.exceptions import RefreshError
    from googleapiclient.errors import HttpError
except ImportError:
    RefreshError = None  # type: ignore[assignment]
    HttpError = None  # type: ignore[assignment]


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


def _raise_if_auth_error(exc: Exception) -> None:
    if RefreshError is not None and isinstance(exc, RefreshError):
        raise AuthRequiredError() from exc

    if HttpError is not None and isinstance(exc, HttpError):
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status == 401:
            raise AuthRequiredError() from exc

    message = str(exc).lower()
    if "invalid_grant" in message or "invalid credentials" in message:
        raise AuthRequiredError() from exc


class GoogleTasksGateway:
    def __init__(self, auth_service: GoogleAuthService | None = None):
        self.auth = auth_service or GoogleAuthService()

    def is_available(self) -> bool:
        return self.auth.is_available()

    def _service(self):
        return self.auth.get_service()

    def _execute_request(self, request, error_message: str):
        try:
            return request.execute()
        except Exception as exc:
            _raise_if_auth_error(exc)
            logger.exception(error_message)
            return None

    def list_tasklists(self) -> list[TaskListItem]:
        service = self._service()
        if service is None:
            return []

        response = self._execute_request(
            service.tasklists().list(maxResults=100),
            "Failed to list tasklists from Google Tasks.",
        )
        if response is None:
            return []
        return [
            TaskListItem(id=item["id"], title=item.get("title", "(無題)"))
            for item in response.get("items", [])
        ]

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

        response = self._execute_request(
            service.tasks().list(
                tasklist=tasklist_id,
                showCompleted=include_completed,
                showHidden=include_hidden,
            ),
            "Failed to list tasks from Google Tasks.",
        )
        if response is None:
            return []

        items = response.get("items", [])
        return [self._to_task_item(item, tasklist_id=tasklist_id) for item in items]

    def list_completed(self, tasklist_id: str = "@default", days: int = 30) -> list[TaskItem]:
        service = self._service()
        if service is None:
            return []

        bounded_days = min(max(days, 30), 365)
        completed_min = (datetime.now(timezone.utc) - timedelta(days=bounded_days)).isoformat()

        response = self._execute_request(
            service.tasks().list(
                tasklist=tasklist_id,
                showCompleted=True,
                showHidden=True,
                completedMin=completed_min,
            ),
            "Failed to list completed tasks from Google Tasks.",
        )
        if response is None:
            return []

        result = []
        for item in response.get("items", []):
            if item.get("status") == TaskStatus.COMPLETED.value:
                result.append(self._to_task_item(item, tasklist_id=tasklist_id))
        return result

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

        created = self._execute_request(
            service.tasks().insert(tasklist=tasklist_id, body=body),
            "Failed to add task to Google Tasks.",
        )
        if created is None:
            return None

        return self._to_task_item(created, tasklist_id=tasklist_id)

    def update_task(self, task_id: str, patch: dict, tasklist_id: str = "@default") -> TaskItem | None:
        service = self._service()
        if service is None or not task_id:
            return None

        current = self._execute_request(
            service.tasks().get(tasklist=tasklist_id, task=task_id),
            "Failed to load task from Google Tasks.",
        )
        if current is None:
            return None

        current.update(patch)
        updated = self._execute_request(
            service.tasks().update(tasklist=tasklist_id, task=task_id, body=current),
            "Failed to update task in Google Tasks.",
        )
        if updated is None:
            return None

        return self._to_task_item(updated, tasklist_id=tasklist_id)

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
