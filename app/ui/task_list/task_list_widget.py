"""Task list pane with add/edit/select interactions."""

from __future__ import annotations

from datetime import date, datetime

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app import database as db
from app.ui.task_list.calendar_popup import CalendarPopup
from app.ui.task_list.icons import build_calendar_icon, build_refresh_icon
from app.ui.task_list.task_item_widget import TaskItemWidget


class TaskListWidget(QWidget):
    """Task list pane: add input, list rendering, and keyboard-first interactions."""

    tasks_changed = pyqtSignal()
    task_create_requested = pyqtSignal(str, object)  # title, due_date
    task_toggled = pyqtSignal(int, bool)
    task_updated = pyqtSignal(int, str, object, str)  # request: id, title, due_date, notes
    refresh_requested = pyqtSignal()
    tasklist_changed = pyqtSignal(str)
    task_completion_requested = pyqtSignal(int)
    task_completion_undo = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._task_widgets: dict[int, TaskItemWidget] = {}
        self._task_order: list[int] = []
        self._selected_task_id: int | None = None
        self._selected_due_date: str | None = None
        self._read_only = False
        # IDs waiting for the 2-second undo window before remote completion.
        self._pending_completion: set[int] = set()

        self.setObjectName("taskListRoot")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 14)
        layout.setSpacing(0)

        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(2, 0, 2, 0)
        header_layout.setSpacing(1)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)

        self.header_label = QLabel("SlideTasks")
        self.header_label.setObjectName("headerLabel")
        title_layout.addWidget(self.header_label)

        self.tasklist_combo = QComboBox()
        self.tasklist_combo.setObjectName("tasklistCombo")
        self.tasklist_combo.setMinimumWidth(120)
        self.tasklist_combo.currentIndexChanged.connect(self._on_tasklist_combo_changed)
        title_layout.addWidget(self.tasklist_combo, 1)

        self.refresh_btn = QPushButton("")
        self.refresh_btn.setObjectName("refreshButton")
        self.refresh_btn.setFixedSize(24, 24)
        self.refresh_btn.setIcon(build_refresh_icon())
        self.refresh_btn.setIconSize(QSize(14, 14))
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setToolTip("Google Tasksと同期")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        title_layout.addWidget(self.refresh_btn)

        header_layout.addWidget(title_row)

        self.date_label = QLabel()
        self.date_label.setObjectName("dateLabel")
        header_layout.addWidget(self.date_label)

        layout.addWidget(header_container)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)
        layout.addSpacing(10)

        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("taskInput")
        self.input_field.setPlaceholderText("タスクを追加...")
        self.input_field.returnPressed.connect(self._add_task)
        input_layout.addWidget(self.input_field)

        self.calendar_btn = QPushButton("")
        self.calendar_btn.setObjectName("dueButton")
        self.calendar_btn.setFixedHeight(32)
        self.calendar_btn.setMinimumWidth(72)
        self.calendar_btn.setMaximumWidth(86)
        self._due_icon_idle = build_calendar_icon(color="#a78bfa")
        self._due_icon_active = build_calendar_icon(color="#f1f0f7")
        self.calendar_btn.setIconSize(QSize(14, 14))
        self.calendar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.calendar_btn.clicked.connect(self._toggle_calendar_popup)
        input_layout.addWidget(self.calendar_btn)
        self._update_due_button_display()

        layout.addWidget(input_container)
        layout.addSpacing(10)

        self.counter_label = QLabel()
        self.counter_label.setObjectName("counterLabel")
        layout.addWidget(self.counter_label)
        layout.addSpacing(4)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(6)
        self.task_layout.addStretch()

        self.scroll_area.setWidget(self.task_container)
        layout.addWidget(self.scroll_area)

        self._dim_effect = QGraphicsOpacityEffect(self.scroll_area)
        self._dim_effect.setOpacity(1.0)
        self.scroll_area.setGraphicsEffect(self._dim_effect)

        self._empty_widget = QWidget()
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(4)
        empty_label = QLabel("タスクはありません")
        empty_label.setObjectName("emptyLabel")
        empty_layout.addWidget(empty_label)
        self.task_layout.insertWidget(0, self._empty_widget)

    def _toggle_calendar_popup(self):
        if self._read_only:
            return

        popup = CalendarPopup(self, initial_due=self._selected_due_date)
        popup.adjustSize()

        btn_rect = self.calendar_btn.rect()
        bottom_right = self.calendar_btn.mapToGlobal(btn_rect.bottomRight())
        popup.move(bottom_right.x() - popup.width(), bottom_right.y() + 4)

        if popup.exec():
            self._selected_due_date = popup.selected_date()
        self._update_due_button_display()
        self.input_field.setFocus()

    @staticmethod
    def _parse_due_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _update_due_button_display(self):
        # Style states are driven by dynamic properties consumed by QSS.
        parsed_due = self._parse_due_date(self._selected_due_date)
        has_due = parsed_due is not None
        is_overdue = bool(parsed_due and parsed_due < date.today())

        if has_due:
            badge = parsed_due.strftime("%m/%d")
            self.calendar_btn.setText(badge)
            self.calendar_btn.setIcon(self._due_icon_active)
            self.calendar_btn.setToolTip(f"期限: {self._selected_due_date}")
        else:
            self.calendar_btn.setText("")
            self.calendar_btn.setIcon(self._due_icon_idle)
            self.calendar_btn.setToolTip("期限を設定")

        self.calendar_btn.setProperty("dueSelected", has_due)
        self.calendar_btn.setProperty("dueOverdue", is_overdue)
        self.calendar_btn.style().unpolish(self.calendar_btn)
        self.calendar_btn.style().polish(self.calendar_btn)

    def load_tasks(self):
        self._clear_all()
        tasks = [task for task in db.get_today_tasks() if not bool(task["is_done"])]

        by_gid = {task.get("google_task_id"): task for task in tasks if task.get("google_task_id")}
        children: dict[str, list[dict]] = {}
        roots: list[dict] = []

        for task in tasks:
            parent_gid = task.get("parent_google_id")
            if parent_gid and parent_gid in by_gid:
                children.setdefault(parent_gid, []).append(task)
            else:
                roots.append(task)

        def sort_key(task: dict):
            position = task.get("google_position")
            return (position is None, position or "", task["id"])

        # Keep Google order and render child tasks with increasing indent.
        def insert_tree(task: dict, indent_level: int):
            self._insert_task_widget(
                task["id"],
                task["title"],
                False,
                due_date=task.get("due_date"),
                notes=task.get("notes") or "",
                animate=False,
                indent_level=indent_level,
            )
            gid = task.get("google_task_id")
            if gid and gid in children:
                for child in sorted(children[gid], key=sort_key):
                    insert_tree(child, indent_level + 1)

        for root in sorted(roots, key=sort_key):
            insert_tree(root, 0)

        self._ensure_selection()
        self._update_empty_state()
        self._update_counter()
        self.tasks_changed.emit()

    def _add_task(self):
        if self._read_only:
            return

        title = self.input_field.text().strip()
        if not title:
            return

        due_date = self._selected_due_date
        self.input_field.clear()

        self._selected_due_date = None
        self._update_due_button_display()

        self.task_create_requested.emit(title, due_date)

    def _insert_task_widget(
        self,
        task_id: int,
        title: str,
        is_done: bool,
        due_date: str | None = None,
        notes: str = "",
        animate: bool = False,
        indent_level: int = 0,
    ):
        widget = TaskItemWidget(
            task_id,
            title,
            is_done,
            due_date=due_date,
            notes=notes,
            indent_level=indent_level,
        )
        widget.toggled.connect(self._on_task_toggled)
        widget.edited_full.connect(self._on_task_edited_full)
        widget.clicked.connect(self._on_task_clicked)

        idx = self.task_layout.count() - 1
        self.task_layout.insertWidget(idx, widget)
        self._task_widgets[task_id] = widget
        self._task_order.append(task_id)
        widget.set_interaction_enabled(not self._read_only)

        if animate:
            widget.fade_in()

    def _on_task_clicked(self, task_id: int):
        self.setFocus()
        self._select_task(task_id, ensure_visible=False)

    def _on_task_toggled(self, task_id: int, is_done: bool):
        if self._read_only:
            self.load_tasks()
            return

        if is_done:
            self._pending_completion.add(task_id)
            self.task_completion_requested.emit(task_id)
            self._update_counter()
            self.tasks_changed.emit()
            return

        if task_id in self._pending_completion:
            self._pending_completion.remove(task_id)
            self.task_completion_undo.emit(task_id)
            self._update_counter()
            self.tasks_changed.emit()
            return

        # Google-first: request remote reopen/update and wait for sync refresh.
        self.task_toggled.emit(task_id, False)

    def _on_task_edited_full(self, task_id: int, title: str, due_date: object, notes: str):
        if self._read_only:
            self.load_tasks()
            return

        due_value = due_date if isinstance(due_date, str) else None
        # Google-first: emit request only; UI updates after sync refresh.
        self.task_updated.emit(task_id, title, due_value, notes or "")

    def _clear_all(self):
        for widget in self._task_widgets.values():
            self.task_layout.removeWidget(widget)
            widget.deleteLater()
        self._task_widgets.clear()
        self._task_order.clear()
        self._selected_task_id = None

    def _update_empty_state(self):
        self._empty_widget.setVisible(len(self._task_widgets) == 0)

    def _update_counter(self):
        total = len(self._task_widgets)
        done = len(self._pending_completion)
        self.counter_label.setText(f"  {done} / {total} 完了" if total else "")

    def _select_task(self, task_id: int, ensure_visible: bool):
        if task_id not in self._task_widgets:
            return

        if self._selected_task_id in self._task_widgets:
            self._task_widgets[self._selected_task_id].set_selected(False)

        self._selected_task_id = task_id
        current = self._task_widgets[task_id]
        current.set_selected(True)
        if ensure_visible:
            self.scroll_area.ensureWidgetVisible(current, 12, 20)

    def _ensure_selection(self):
        if not self._task_order:
            self._selected_task_id = None
            return

        if self._selected_task_id in self._task_widgets:
            self._select_task(self._selected_task_id, ensure_visible=False)
            return

        self._select_task(self._task_order[0], ensure_visible=False)

    def _move_selection(self, step: int):
        if not self._task_order:
            return

        if self._selected_task_id not in self._task_order:
            self._select_task(self._task_order[0], ensure_visible=True)
            return

        index = self._task_order.index(self._selected_task_id)
        next_index = max(0, min(len(self._task_order) - 1, index + step))
        self._select_task(self._task_order[next_index], ensure_visible=True)

    def update_date_label(self, text: str):
        self.date_label.setText(text)

    def set_read_only(self, read_only: bool):
        self._read_only = read_only
        self.input_field.setEnabled(not read_only)
        self.calendar_btn.setEnabled(not read_only)
        self.tasklist_combo.setEnabled(not read_only)
        for widget in self._task_widgets.values():
            widget.set_interaction_enabled(not read_only)

    def set_dimmed(self, dimmed: bool):
        self._dim_effect.setOpacity(0.62 if dimmed else 1.0)

    def finalize_completion(self, task_id: int) -> bool:
        if task_id not in self._pending_completion:
            return False

        self._pending_completion.remove(task_id)

        removed_index = -1
        if task_id in self._task_order:
            removed_index = self._task_order.index(task_id)
            self._task_order.remove(task_id)

        widget = self._task_widgets.pop(task_id, None)
        if widget:
            self.task_layout.removeWidget(widget)
            widget.deleteLater()

        if self._selected_task_id == task_id:
            self._selected_task_id = None
            if self._task_order:
                fallback_index = min(max(removed_index, 0), len(self._task_order) - 1)
                self._select_task(self._task_order[fallback_index], ensure_visible=True)

        self._update_empty_state()
        self._update_counter()
        self.tasks_changed.emit()
        return True

    def set_tasklists(self, tasklists: list[dict], current_tasklist_id: str):
        self.tasklist_combo.blockSignals(True)
        self.tasklist_combo.clear()
        current_index = -1
        for index, item in enumerate(tasklists):
            title = item.get("title", "(無題)")
            tasklist_id = item.get("id", "")
            self.tasklist_combo.addItem(title, tasklist_id)
            if tasklist_id == current_tasklist_id:
                current_index = index

        if self.tasklist_combo.count() > 0:
            self.tasklist_combo.setCurrentIndex(current_index if current_index >= 0 else 0)
        self.tasklist_combo.blockSignals(False)

    def _on_tasklist_combo_changed(self, index: int):
        if index < 0:
            return
        tasklist_id = self.tasklist_combo.itemData(index)
        if tasklist_id:
            self.tasklist_changed.emit(tasklist_id)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Up:
            self._move_selection(-1)
            event.accept()
            return
        if key == Qt.Key.Key_Down:
            self._move_selection(1)
            event.accept()
            return
        if key == Qt.Key.Key_Space and self._selected_task_id is not None:
            widget = self._task_widgets.get(self._selected_task_id)
            if widget and widget.checkbox.isEnabled():
                widget.checkbox.toggle()
                event.accept()
                return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._selected_task_id is not None:
            widget = self._task_widgets.get(self._selected_task_id)
            if widget:
                widget.open_editor()
                event.accept()
                return
        super().keyPressEvent(event)
