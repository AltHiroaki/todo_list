"""Single task row widget."""

from __future__ import annotations

from datetime import date, datetime

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.task_list.task_edit_dialog import TaskEditDialog


class TaskItemWidget(QFrame):
    """Single task row used in the active task list."""

    toggled = pyqtSignal(int, bool)
    edited_full = pyqtSignal(int, str, object, str)
    clicked = pyqtSignal(int)

    def __init__(
        self,
        task_id: int,
        title: str,
        is_done: bool,
        due_date: str | None = None,
        notes: str = "",
        indent_level: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.task_id = task_id
        self._is_done = is_done
        self._due_date = due_date
        self._notes = notes or ""
        self._can_interact = True
        self._selected = False

        self.setObjectName("taskItem")
        self.setMinimumHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12 + (indent_level * 18), 8, 8, 8)
        layout.setSpacing(10)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(is_done)
        self.checkbox.setFixedSize(24, 24)
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.stateChanged.connect(self._on_toggle)
        layout.addWidget(self.checkbox)

        text_container = QWidget()
        self._text_layout = QVBoxLayout(text_container)
        self._text_layout.setContentsMargins(0, 0, 0, 0)
        self._text_layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._text_layout.addWidget(self.title_label)

        self.date_label: QLabel | None = None
        self._refresh_due_label()

        self.notes_label = QLabel(self._notes)
        self.notes_label.setObjectName("taskNotes")
        self.notes_label.setWordWrap(True)
        self.notes_label.setVisible(False)
        self._text_layout.addWidget(self.notes_label)

        layout.addWidget(text_container, 1)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._apply_done_style(is_done)
        self.set_selected(False)

    def set_interaction_enabled(self, enabled: bool):
        self._can_interact = enabled
        self.checkbox.setEnabled(enabled)
        cursor = Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor
        self.setCursor(cursor)

    def set_selected(self, selected: bool):
        self._selected = selected
        self.setProperty("selected", selected)
        self.notes_label.setVisible(selected and bool(self._notes.strip()) and not self._is_done)
        self.style().unpolish(self)
        self.style().polish(self)

    def fade_in(self):
        self._opacity_effect.setOpacity(0.0)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(220)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.task_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.task_id)
            self.open_editor()
        super().mouseDoubleClickEvent(event)

    def _format_due_date(self, due_date_str: str) -> tuple[str, str]:
        try:
            due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            return due_date_str, "color: #94a3b8;"

        delta = (due - date.today()).days
        text = due.strftime("期限 %m/%d")
        if delta < 0:
            return f"{text} (期限切れ)", "color: #ef4444; font-weight: bold;"
        if delta == 0:
            return f"{text} (今日)", "color: #f59e0b; font-weight: bold;"
        return text, "color: #94a3b8;"

    def _refresh_due_label(self):
        if self._due_date and self.date_label is None:
            self.date_label = QLabel()
            self.date_label.setObjectName("dateLabel")
            self._text_layout.insertWidget(1, self.date_label)

        if self._due_date and self.date_label is not None:
            text, style = self._format_due_date(self._due_date)
            self.date_label.setText(text)
            self.date_label.setStyleSheet(f"font-size: 11px; {style}")
            return

        if self.date_label is not None:
            self._text_layout.removeWidget(self.date_label)
            self.date_label.deleteLater()
            self.date_label = None

    def _on_toggle(self, state: int):
        if not self._can_interact:
            self.checkbox.blockSignals(True)
            self.checkbox.setChecked(not (state == 2))
            self.checkbox.blockSignals(False)
            return

        is_done = state == 2
        self._is_done = is_done
        self._apply_done_style(is_done)
        self.toggled.emit(self.task_id, is_done)

    def open_editor(self):
        if not self._can_interact or self._is_done:
            return

        dialog = TaskEditDialog(self.title_label.text(), self._due_date, self._notes, self)
        if not dialog.exec():
            return

        title, due_date, notes = dialog.values()
        title_changed = title != self.title_label.text()
        details_changed = (due_date != self._due_date) or (notes != self._notes)
        if not title_changed and not details_changed:
            return

        # Keep UI unchanged until remote sync succeeds and list reloads.
        self.edited_full.emit(self.task_id, title, due_date, notes)

    def _apply_done_style(self, done: bool):
        self.setObjectName("taskItemDone" if done else "taskItem")
        self.notes_label.setVisible(self._selected and bool(self._notes.strip()) and not done)
        if done:
            self.title_label.setObjectName("taskTitleDone")
        else:
            self.title_label.setObjectName("taskTitle")

        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)
        self.style().unpolish(self)
        self.style().polish(self)
