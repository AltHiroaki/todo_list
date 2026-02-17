"""
SlideTasks — タスクウィジェット（プレミアムデザイン版）
タスクリストUI: 入力欄、個別タスクアイテム（チェック + ラベル + 削除）を提供。
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QCheckBox, QPushButton, QScrollArea, QLabel, QFrame,
    QSizePolicy, QGraphicsOpacityEffect, QCalendarWidget, QDialog,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QSequentialAnimationGroup, QParallelAnimationGroup,
    pyqtProperty, QDate,
)
from PyQt6.QtGui import QFont, QIcon, QColor

from app import database as db
from datetime import datetime, date


class TaskItemWidget(QFrame):
    """個別タスク: チェックボックス + タイトル + 期限 + 削除ボタン"""

    toggled = pyqtSignal(int, bool)   # task_id, is_done
    deleted = pyqtSignal(int)         # task_id

    def __init__(self, task_id: int, title: str, is_done: bool, due_date: str | None = None, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self._is_done = is_done
        self._due_date = due_date
        self._update_object_name(is_done)
        self.setMinimumHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(10)

        # チェックボックス
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(is_done)
        self.checkbox.setFixedSize(24, 24)
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.stateChanged.connect(self._on_toggle)
        layout.addWidget(self.checkbox)

        # タイトル & 期限 ラベル用コンテナ
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        # タイトルラベル
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._apply_done_style(is_done)
        text_layout.addWidget(self.title_label)

        # 期限ラベル
        if due_date:
            date_text, color_style = self._format_due_date(due_date)
            self.date_label = QLabel(date_text)
            self.date_label.setObjectName("dateLabel")
            self.date_label.setStyleSheet(f"font-size: 11px; {color_style}")
            text_layout.addWidget(self.date_label)
        
        layout.addWidget(text_container)

        # 削除ボタン（普段は透明度を下げる）
        self.delete_btn = QPushButton("✕")
        self.delete_btn.setObjectName("deleteButton")
        self.delete_btn.setFixedSize(26, 26)
        self.delete_btn.setToolTip("削除")
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(self.delete_btn)

        # フェードイン効果
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

    def _format_due_date(self, due_date_str: str) -> tuple[str, str]:
        """日付文字列から表示用テキストとスタイル(色)を返す"""
        try:
            d = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            today = date.today()
            delta = (d - today).days
            
            # strftimeで月日を取得 (ゼロ埋め削除はプラットフォーム依存だが、ここでは簡易的に)
            m = d.month
            day = d.day
            base_text = f"📅 {m}/{day}"

            if delta < 0:
                return f"{base_text} (期限切れ)", "color: #ef4444; font-weight: bold;"
            elif delta == 0:
                return f"{base_text} (今日まで！)", "color: #f59e0b; font-weight: bold;"
            elif delta == 1:
                return f"{base_text} (あと1日)", "color: #a78bfa;"
            else:
                return f"{base_text} (あと{delta}日)", "color: #94a3b8;"
        except ValueError:
            return due_date_str, "color: #94a3b8;"

    def fade_in(self):
        """タスク追加時のフェードインアニメーション"""
        self._opacity_effect.setOpacity(0.0)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(250)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _on_toggle(self, state):
        is_done = state == 2  # Qt.CheckState.Checked
        self._is_done = is_done
        self._apply_done_style(is_done)
        self._update_object_name(is_done)
        # スタイル更新を反映
        self.style().unpolish(self)
        self.style().polish(self)
        self.toggled.emit(self.task_id, is_done)

    def _on_delete(self):
        self.deleted.emit(self.task_id)

    def _update_object_name(self, done: bool):
        self.setObjectName("taskItemDone" if done else "taskItem")

    def _apply_done_style(self, done: bool):
        if done:
            self.title_label.setObjectName("taskTitleDone")
        else:
            self.title_label.setObjectName("taskTitle")
        # スタイル再適用
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)


class CalendarPopup(QDialog):
    """カレンダー選択ポップアップ"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e33;
                border: 1px solid #2a2a45;
                border-radius: 8px;
            }
            QCalendarWidget QWidget { alternate-background-color: #2a2a45; color: white; }
            QCalendarWidget QToolButton { color: white; icon-size: 20px; }
            QCalendarWidget QMenu { background-color: #1e1e33; color: white; }
            QCalendarWidget QSpinBox { color: white; background-color: #1e1e33; selection-background-color: #8b5cf6; }
            QCalendarWidget QAbstractItemView:enabled { font-size: 13px; color: white; background-color: #1e1e33; selection-background-color: #8b5cf6; selection-color: white; }
            QCalendarWidget QAbstractItemView:disabled { color: #555; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.clicked.connect(self.accept)
        layout.addWidget(self.calendar)
        
    def selected_date(self) -> str:
        return self.calendar.selectedDate().toString("yyyy-MM-dd")


class TaskListWidget(QWidget):
    """タスク入力欄＋スクロール可能なタスクリスト"""

    tasks_changed = pyqtSignal()  # タスク数変更シグナル
    task_added = pyqtSignal(int, str, str) # id, title, due_date (added due_date)
    task_toggled = pyqtSignal(int, bool)
    task_deleted = pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 14)
        layout.setSpacing(0)

        # ── ヘッダー ──
        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(2, 0, 2, 0)
        header_layout.setSpacing(1)

        self.header_label = QLabel("SlideTasks")
        self.header_label.setObjectName("headerLabel")
        header_layout.addWidget(self.header_label)

        self.date_label = QLabel()
        self.date_label.setObjectName("dateLabel")
        header_layout.addWidget(self.date_label)

        layout.addWidget(header_container)

        # ── セパレータ ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)
        layout.addSpacing(10)

        # ── 入力欄エリア (アイコンボタン追加) ──
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("taskInput")
        self.input_field.setPlaceholderText("＋ 新しいタスクを追加...")
        self.input_field.returnPressed.connect(self._add_task)
        input_layout.addWidget(self.input_field)

        # カレンダーボタン
        self.calendar_btn = QPushButton("📅")
        self.calendar_btn.setFixedSize(32, 32)
        self.calendar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.calendar_btn.setToolTip("期限を設定")
        self.calendar_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(139, 92, 246, 0.1);
                border: 1px solid #2a2a45;
                border-radius: 6px;
                color: #a78bfa;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(139, 92, 246, 0.2);
                border-color: #8b5cf6;
            }
            QPushButton:checked {
                background-color: rgba(139, 92, 246, 0.4);
                color: #fff;
                border-color: #8b5cf6;
            }
        """)
        self.calendar_btn.setCheckable(True)
        self.calendar_btn.clicked.connect(self._toggle_calendar_popup)
        input_layout.addWidget(self.calendar_btn)
        
        layout.addWidget(input_container)
        layout.addSpacing(10)
        
        self._selected_due_date = None

        # ── タスクカウンター ──
        self.counter_label = QLabel()
        self.counter_label.setObjectName("counterLabel")
        layout.addWidget(self.counter_label)
        layout.addSpacing(4)

        # ── スクロールエリア ──
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(6)
        self.task_layout.addStretch()

        self.scroll_area.setWidget(self.task_container)
        layout.addWidget(self.scroll_area)

        # ── 空の状態 ──
        self._empty_widget = QWidget()
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(4)

        empty_icon = QLabel("✨")
        empty_icon.setObjectName("emptyIcon")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)

        empty_text = QLabel("タスクを追加してみましょう")
        empty_text.setObjectName("emptyLabel")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_text)

        self.task_layout.insertWidget(0, self._empty_widget)

        self._task_widgets: dict[int, TaskItemWidget] = {}

    def _toggle_calendar_popup(self):
        if not self.calendar_btn.isChecked():
            self._selected_due_date = None
            self.calendar_btn.setToolTip("期限を設定")
            return

        popup = CalendarPopup(self)
        # ボタンの下に表示
        pos = self.calendar_btn.mapToGlobal(self.calendar_btn.rect().bottomLeft())
        popup.move(pos)
        if popup.exec():
            self._selected_due_date = popup.selected_date()
            self.calendar_btn.setChecked(True)
            self.calendar_btn.setToolTip(f"期限: {self._selected_due_date}")
            # 入力欄にフォーカスを戻す
            self.input_field.setFocus()
        else:
            self.calendar_btn.setChecked(False)
            self._selected_due_date = None

    def load_tasks(self):
        """DBからタスクを読み込んで表示する"""
        self._clear_all()
        tasks = db.get_today_tasks()
        for task in tasks:
            # DBカラム追加に伴い get('due_date') で取得
            self._insert_task_widget(
                task["id"], task["title"], bool(task["is_done"]),
                due_date=task.get("due_date"),
                animate=False,
            )
        self._update_empty_state()
        self._update_counter()
        self.tasks_changed.emit()

    def _add_task(self):
        title = self.input_field.text().strip()
        if not title:
            return
        
        due_date = self._selected_due_date
        if not due_date:
            due_date = date.today().isoformat()
            
        task = db.add_task(title, due_date)
        
        self._insert_task_widget(
            task["id"], task["title"], False, due_date=due_date, animate=True
        )
        self.input_field.clear()
        
        # カレンダー選択状態をリセット
        self.calendar_btn.setChecked(False)
        self.calendar_btn.setToolTip("期限を設定")
        self._selected_due_date = None
        
        self._update_empty_state()
        self._update_counter()
        self.tasks_changed.emit()
        self.task_added.emit(task["id"], task["title"], due_date or "")

    def _insert_task_widget(
        self, task_id: int, title: str, is_done: bool, due_date: str | None = None, animate: bool = False
    ):
        widget = TaskItemWidget(task_id, title, is_done, due_date)
        widget.toggled.connect(self._on_task_toggled)
        widget.deleted.connect(self._on_task_deleted)
        # ストレッチの前に挿入
        idx = self.task_layout.count() - 1  # stretch の直前
        self.task_layout.insertWidget(idx, widget)
        self._task_widgets[task_id] = widget
        if animate:
            widget.fade_in()

    def _on_task_toggled(self, task_id: int, is_done: bool):
        db.toggle_done(task_id)
        self._update_counter()
        self.tasks_changed.emit()
        self.task_toggled.emit(task_id, is_done)

    def _on_task_deleted(self, task_id: int):
        gid = db.get_google_task_id(task_id) or ""
        db.delete_task(task_id)
        widget = self._task_widgets.pop(task_id, None)
        if widget:
            self.task_layout.removeWidget(widget)
            widget.deleteLater()
        self._update_empty_state()
        self._update_counter()
        self.tasks_changed.emit()
        self.task_deleted.emit(task_id, gid)

    def _clear_all(self):
        for widget in self._task_widgets.values():
            self.task_layout.removeWidget(widget)
            widget.deleteLater()
        self._task_widgets.clear()

    def _update_empty_state(self):
        has_tasks = len(self._task_widgets) > 0
        self._empty_widget.setVisible(not has_tasks)

    def _update_counter(self):
        total = len(self._task_widgets)
        done = sum(
            1 for w in self._task_widgets.values() if w._is_done
        )
        if total == 0:
            self.counter_label.setText("")
        else:
            self.counter_label.setText(f"  {done} / {total} 完了")

    def update_date_label(self, text: str):
        self.date_label.setText(text)

    def get_added_task(self) -> dict | None:
        """直前に追加されたタスク情報を取得（Google同期用フック）"""
        return None  # Phase 3 で実装

