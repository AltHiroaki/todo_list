from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.infrastructure.google.tasks_gateway import GoogleTasksGateway


@dataclass(slots=True)
class CompletedLogEntry:
    task_id: str
    title: str
    completed_raw: str
    notes: str


def _parse_completed(value: str) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min


class LoadCompletedLogUseCase:
    def __init__(self, gateway: GoogleTasksGateway):
        self.gateway = gateway

    def execute(self, tasklist_id: str, days: int) -> list[CompletedLogEntry]:
        tasks = self.gateway.list_completed(tasklist_id=tasklist_id, days=days)
        tasks.sort(key=lambda item: _parse_completed(item.completed or ""), reverse=True)
        return [
            CompletedLogEntry(
                task_id=item.id,
                title=item.title,
                completed_raw=item.completed or "",
                notes=item.notes or "",
            )
            for item in tasks
        ]

