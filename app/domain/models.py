from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class TaskStatus(str, Enum):
    NEEDS_ACTION = "needsAction"
    COMPLETED = "completed"


class AppSyncState(str, Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    OFFLINE_READONLY = "offline_readonly"
    BLOCKING_ERROR = "blocking_error"


@dataclass(slots=True)
class TaskListItem:
    id: str
    title: str


@dataclass(slots=True)
class TaskItem:
    id: str
    title: str
    status: TaskStatus
    tasklist_id: str
    due: date | None = None
    completed: str | None = None
    notes: str = ""
    parent: str | None = None
    position: str | None = None
    children: list["TaskItem"] = field(default_factory=list)

    @property
    def is_completed(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    @property
    def is_overdue(self) -> bool:
        if self.due is None or self.is_completed:
            return False
        return self.due < date.today()

