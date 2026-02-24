"""Google Tasks sync compatibility wrapper.

This module keeps the old call sites working while delegating all operations
to the new infrastructure gateway. Task deletion is intentionally unsupported.
"""

from __future__ import annotations

from app.infrastructure.google.auth_service import GoogleAuthService
from app.infrastructure.google.tasks_gateway import GoogleTasksGateway


class GoogleTaskSync:
    def __init__(self):
        self.tasklist_id = "@default"
        self._auth = GoogleAuthService()
        self._gateway = GoogleTasksGateway(self._auth)

    def is_available(self) -> bool:
        return self._gateway.is_available()

    def authenticate(self) -> bool:
        return self._auth.authenticate()

    def add_task(self, title: str, due_date: str | None = None) -> str | None:
        created = self._gateway.add_task(
            title=title,
            due_date=due_date,
            tasklist_id=self.tasklist_id,
        )
        return created.id if created else None

    def complete_task(self, google_task_id: str) -> bool:
        return self._gateway.complete_task(task_id=google_task_id, tasklist_id=self.tasklist_id)

    def reopen_task(self, google_task_id: str) -> bool:
        return self._gateway.reopen_task(task_id=google_task_id, tasklist_id=self.tasklist_id)

    def update_title(self, google_task_id: str, new_title: str) -> bool:
        return self._gateway.update_title(
            task_id=google_task_id,
            new_title=new_title,
            tasklist_id=self.tasklist_id,
        )

    def update_due_date(self, google_task_id: str, due_date: str | None) -> bool:
        return self._gateway.update_due_date(
            task_id=google_task_id,
            due_date=due_date,
            tasklist_id=self.tasklist_id,
        )

    def update_task_details(
        self,
        google_task_id: str,
        *,
        title: str,
        due_date: str | None,
        notes: str,
    ) -> bool:
        patch = {
            "title": title,
            "notes": notes,
            "due": f"{due_date}T00:00:00.000Z" if due_date else None,
        }
        updated = self._gateway.update_task(
            task_id=google_task_id,
            patch=patch,
            tasklist_id=self.tasklist_id,
        )
        return updated is not None


google_sync = GoogleTaskSync()
