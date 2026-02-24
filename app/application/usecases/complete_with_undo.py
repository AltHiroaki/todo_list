from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class CompleteWithUndoUseCase(QObject):
    committed = pyqtSignal(str)
    undone = pyqtSignal(str)

    def __init__(self, commit_fn: Callable[[str], bool], undo_ms: int = 2000):
        super().__init__()
        self.commit_fn = commit_fn
        self.undo_ms = undo_ms
        self._pending: dict[str, QTimer] = {}

    def queue(self, task_id: str) -> None:
        self.cancel(task_id)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._commit(task_id))
        self._pending[task_id] = timer
        timer.start(self.undo_ms)

    def cancel(self, task_id: str) -> None:
        timer = self._pending.pop(task_id, None)
        if timer:
            timer.stop()
            self.undone.emit(task_id)

    def _commit(self, task_id: str) -> None:
        self._pending.pop(task_id, None)
        if self.commit_fn(task_id):
            self.committed.emit(task_id)

