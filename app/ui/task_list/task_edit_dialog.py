"""Task edit dialog with title, due date, and notes."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.ui.task_list.calendar_popup import CalendarPopup


class TaskEditDialog(QDialog):
    def __init__(self, title: str, due_date: str | None, notes: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("タスク編集")
        self.setModal(True)
        self.setMinimumWidth(360)
        self._values: tuple[str, str | None, str] = (title, due_date, notes)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_label = QLabel("タイトル")
        layout.addWidget(title_label)

        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("タスク名")
        self.title_edit.returnPressed.connect(self._on_save)
        layout.addWidget(self.title_edit)

        due_label = QLabel("期限 (YYYY-MM-DD)")
        layout.addWidget(due_label)

        due_row = QHBoxLayout()
        due_row.setSpacing(6)
        self.due_edit = QLineEdit(due_date or "")
        self.due_edit.setPlaceholderText("YYYY-MM-DD")
        self.due_edit.returnPressed.connect(self._on_save)
        due_row.addWidget(self.due_edit, 1)

        self.pick_btn = QPushButton("選択")
        self.pick_btn.clicked.connect(self._pick_date)
        due_row.addWidget(self.pick_btn)

        self.clear_btn = QPushButton("クリア")
        self.clear_btn.clicked.connect(lambda: self.due_edit.setText(""))
        due_row.addWidget(self.clear_btn)
        layout.addLayout(due_row)

        notes_label = QLabel("メモ")
        layout.addWidget(notes_label)

        self.notes_edit = QPlainTextEdit(notes or "")
        self.notes_edit.setPlaceholderText("任意のメモ")
        self.notes_edit.setMinimumHeight(110)
        layout.addWidget(self.notes_edit)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _pick_date(self):
        due_text = self.due_edit.text().strip() or None
        popup = CalendarPopup(self, initial_due=due_text)

        popup.adjustSize()
        rect = self.pick_btn.rect()
        bottom_right = self.pick_btn.mapToGlobal(rect.bottomRight())
        popup.move(bottom_right.x() - popup.width(), bottom_right.y() + 4)
        if popup.exec():
            selected = popup.selected_date()
            self.due_edit.setText(selected or "")

    def _on_save(self):
        title = self.title_edit.text().strip()
        if not title:
            self.error_label.setText("タイトルは必須です。")
            self.error_label.setVisible(True)
            return

        due_text = self.due_edit.text().strip()
        due_value: str | None = None
        if due_text:
            try:
                datetime.strptime(due_text, "%Y-%m-%d")
            except ValueError:
                self.error_label.setText("期限は YYYY-MM-DD 形式で入力してください。")
                self.error_label.setVisible(True)
                return
            due_value = due_text

        notes = self.notes_edit.toPlainText().strip()
        self._values = (title, due_value, notes)
        self.accept()

    def values(self) -> tuple[str, str | None, str]:
        return self._values
