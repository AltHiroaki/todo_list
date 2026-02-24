from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from app.application.usecases.load_completed_log import LoadCompletedLogUseCase
from app.infrastructure.google.tasks_gateway import GoogleTasksGateway


def _format_completed(raw_value: str) -> str:
    if not raw_value:
        return "-"
    try:
        value = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return raw_value


class CompletedLogWindow(QWidget):
    def __init__(self, tasklist_provider: Callable[[], str], parent: QWidget | None = None):
        super().__init__(parent)
        self._tasklist_provider = tasklist_provider
        self._usecase = LoadCompletedLogUseCase(GoogleTasksGateway())

        self.setWindowTitle("SlideTasks - 完了ログ")
        self.setMinimumSize(560, 680)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("完了済みタスク")
        title.setObjectName("completedLogTitle")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()

        self.range_combo = QComboBox()
        self.range_combo.addItem("1か月", 30)
        self.range_combo.addItem("2か月", 60)
        self.range_combo.addItem("3か月", 90)
        self.range_combo.addItem("6か月", 180)
        self.range_combo.addItem("1年", 365)
        self.range_combo.currentIndexChanged.connect(self.refresh_logs)
        header.addWidget(self.range_combo)

        self.refresh_button = QPushButton("再読み込み")
        self.refresh_button.clicked.connect(self.refresh_logs)
        header.addWidget(self.refresh_button)

        root.addLayout(header)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        root.addWidget(self.status_label)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #2a2a45;")
        root.addWidget(line)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            """
            QListWidget {
                border: none;
                background: transparent;
            }
            QListWidget::item {
                border-bottom: 1px solid #23233d;
                padding: 4px;
            }
            """
        )
        root.addWidget(self.list_widget, 1)

    def refresh_logs(self):
        days = int(self.range_combo.currentData() or 30)
        tasklist_id = self._tasklist_provider() or "@default"

        self.status_label.setText("完了タスクを読み込み中...")
        QApplication.processEvents()

        entries = self._usecase.execute(tasklist_id=tasklist_id, days=days)
        self.list_widget.clear()

        if not entries:
            self.status_label.setText("選択期間に完了タスクはありません。")
            return

        self.status_label.setText(f"過去{days}日: {len(entries)}件")
        for entry in entries:
            item = QListWidgetItem()
            widget = self._build_row(entry.title, entry.completed_raw, entry.notes)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def _build_row(self, title: str, completed_raw: str, notes: str) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)

        title_label = QLabel(title or "(無題)")
        title_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #e2e8f0;")
        layout.addWidget(title_label)

        meta_label = QLabel(f"完了日時: {_format_completed(completed_raw)}")
        meta_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(meta_label)

        if notes:
            notes_label = QLabel(notes)
            notes_label.setWordWrap(True)
            notes_label.setStyleSheet("font-size: 11px; color: #cbd5e1;")
            layout.addWidget(notes_label)

        return row
