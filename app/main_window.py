"""Main application window for SlideTasks."""

from __future__ import annotations

import logging
from datetime import date

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QThread, QTimer, Qt, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QRegion
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app import daily_reset
from app import startup
from app import database as db
from app.application.usecases.complete_with_undo import CompleteWithUndoUseCase
from app.domain.models import AppSyncState
from app.google_sync import google_sync
from app.styles import MAIN_STYLESHEET
from app.sync_worker import SyncWorker
from app.ui.task_list import TaskListWidget
from app.ui.widgets.error_overlay import ErrorOverlay
from app.ui.windows.completed_log_window import CompletedLogWindow
from app.ui.windows.main_window_constants import (
    ANIMATION_DURATION_MS,
    DAILY_CHECK_INTERVAL_MS,
    HOVER_EXPAND_DELAY_MS,
    MAX_PANEL_WIDTH,
    MIN_PANEL_WIDTH,
    POLL_INTERVAL_MS,
    RESIZE_MARGIN,
    TOGGLE_EXPANDED_STYLESHEET,
    TOGGLE_HOVER_STYLESHEET,
    TOGGLE_IDLE_STYLESHEET,
    TRIGGER_WIDTH,
    WINDOW_HEIGHT_RATIO,
)
from app.ui.windows.main_window_state_store import MainWindowState, MainWindowStateStore
from app.ui.windows.tray_controller import TrayCallbacks, TrayController


class MainWindow(QMainWindow):
    """Right-edge slide panel host with tray + background sync orchestration."""

    global_hotkey_activated = pyqtSignal()
    request_initial_sync = pyqtSignal()
    request_poll_sync = pyqtSignal()
    request_add_task = pyqtSignal(str, str)
    request_update_task = pyqtSignal(int, str, object, str)
    request_toggle_task = pyqtSignal(int, bool)

    def __init__(self):
        super().__init__()

        self._ui_state_store = MainWindowStateStore()
        ui_state = self._load_ui_state()

        self.setWindowTitle("SlideTasks")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(MAIN_STYLESHEET)

        self._is_expanded = False
        self._animating = False
        self._resizing = False
        self._resize_anchor_right = 0
        self._current_mask_width = TRIGGER_WIDTH
        self._expanded_width = ui_state.panel_width
        self._pinned = ui_state.pinned
        self._startup_opt_out = ui_state.startup_opt_out
        self.app_state = AppSyncState.IDLE
        self.current_tasklist_id = "@default"
        google_sync.tasklist_id = self.current_tasklist_id
        self._apply_pin_flag(self._pinned)

        screen = QApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("プライマリ画面が見つかりません。")

        screen_geo = screen.availableGeometry()
        self._screen_right = screen_geo.right() + 1
        self._screen_top = screen_geo.top()
        self._screen_height = screen_geo.height()
        self._expanded_height = int(self._screen_height * WINDOW_HEIGHT_RATIO)
        self._expanded_y = self._screen_top

        self.setMinimumWidth(MIN_PANEL_WIDTH)
        self.setMaximumWidth(MAX_PANEL_WIDTH)
        self.setFixedHeight(self._expanded_height)
        self.resize(self._expanded_width, self._expanded_height)
        self.move(self._screen_right - self._expanded_width, self._expanded_y)

        container = QWidget(self)
        container.setObjectName("container")
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.content_panel = QWidget()
        self.content_panel.setObjectName("contentPanel")
        content_layout = QVBoxLayout(self.content_panel)
        content_layout.setContentsMargins(0, 0, 0, 14)
        content_layout.setSpacing(0)

        self.sync_progress = QProgressBar()
        self.sync_progress.setObjectName("syncProgress")
        self.sync_progress.setTextVisible(False)
        self.sync_progress.setRange(0, 0)
        self.sync_progress.hide()
        content_layout.addWidget(self.sync_progress)

        content_layout.addSpacing(14)

        self.task_list = TaskListWidget()
        self.task_list.set_read_only(False)
        self.task_list.tasks_changed.connect(self._update_progress)
        self.task_list.tasklist_changed.connect(self._on_tasklist_changed)
        content_layout.addWidget(self.task_list)

        progress_container = QWidget()
        progress_outer = QVBoxLayout(progress_container)
        progress_outer.setContentsMargins(14, 4, 14, 0)
        progress_outer.setSpacing(6)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        progress_outer.addWidget(sep)
        progress_outer.addSpacing(6)

        progress_header = QHBoxLayout()
        progress_header.setSpacing(0)

        progress_label = QLabel("今日の進捗")
        progress_label.setObjectName("progressLabel")
        progress_header.addWidget(progress_label)
        progress_header.addStretch()

        self.progress_pct_label = QLabel("0%")
        self.progress_pct_label.setObjectName("progressPercent")
        progress_header.addWidget(self.progress_pct_label)

        progress_outer.addLayout(progress_header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("")
        progress_outer.addWidget(self.progress_bar)

        content_layout.addWidget(progress_container)
        content_layout.addSpacing(8)

        footer_container = QWidget()
        footer_layout = QVBoxLayout(footer_container)
        footer_layout.setContentsMargins(14, 0, 14, 0)
        footer_layout.setSpacing(6)

        self.log_button = QPushButton("完了ログを開く")
        self.log_button.setObjectName("footerButton")
        self.log_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.log_button.clicked.connect(self._show_completed_log)
        footer_layout.addWidget(self.log_button)

        self.quit_button = QPushButton("アプリを終了")
        self.quit_button.setObjectName("quitButton")
        self.quit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quit_button.clicked.connect(self._quit_app)
        footer_layout.addWidget(self.quit_button)

        content_layout.addWidget(footer_container)
        container_layout.addWidget(self.content_panel)

        self.error_overlay = ErrorOverlay(self.content_panel)
        self.error_overlay.retry_clicked.connect(self._retry_sync)
        self.error_overlay.setGeometry(self.content_panel.rect())

        self.toggle_btn = QPushButton(">")
        self.toggle_btn.setObjectName("toggleButton")
        self.toggle_btn.setFixedWidth(TRIGGER_WIDTH)
        self.toggle_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_slide)
        self.toggle_btn.setStyleSheet(TOGGLE_IDLE_STYLESHEET)
        container_layout.addWidget(self.toggle_btn)

        self.setCentralWidget(container)

        self._slide_anim = QPropertyAnimation(self, b"slideWidth")
        self._slide_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._slide_anim.setDuration(ANIMATION_DURATION_MS)
        self._slide_anim.finished.connect(self._on_animation_finished)

        self._hover_expand_timer = QTimer(self)
        self._hover_expand_timer.setSingleShot(True)
        self._hover_expand_timer.timeout.connect(self._expand_from_hover)

        self.setMouseTracking(True)
        container.setMouseTracking(True)
        self.content_panel.setMouseTracking(True)
        self.toggle_btn.setMouseTracking(True)

        daily_reset.initialize()
        self._daily_timer = QTimer(self)
        self._daily_timer.timeout.connect(self._check_daily_reset)
        self._daily_timer.start(DAILY_CHECK_INTERVAL_MS)

        self._completed_log_window: CompletedLogWindow | None = None
        self._setup_tray()
        self._apply_startup_policy()

        self.global_hotkey_activated.connect(self._on_hotkey)
        self._register_hotkey()

        self._apply_mask(TRIGGER_WIDTH)

        db.init_db()
        db.set_current_tasklist(self.current_tasklist_id)
        self.task_list.load_tasks()
        self._update_date_label()
        self._update_progress()
        self._set_sync_state(AppSyncState.IDLE)

        self.sync_thread = QThread(self)
        self.sync_worker = SyncWorker()
        self.sync_worker.moveToThread(self.sync_thread)

        self.complete_with_undo = CompleteWithUndoUseCase(self._commit_local_completion, undo_ms=2000)
        self.complete_with_undo.committed.connect(self._on_completion_committed)

        # UI thread -> worker thread requests.
        self.request_initial_sync.connect(self.sync_worker.initial_sync)
        self.request_poll_sync.connect(self.sync_worker.poll_tasks)
        self.request_add_task.connect(self.sync_worker.push_add_request)
        self.request_update_task.connect(self.sync_worker.push_update_details)
        self.request_toggle_task.connect(self.sync_worker.push_toggle)

        # Task list intents from widgets.
        self.task_list.task_create_requested.connect(self._on_task_create_requested)
        self.task_list.task_toggled.connect(self._on_task_toggle_requested)
        self.task_list.task_updated.connect(self._on_task_update_requested)
        self.task_list.task_completion_requested.connect(self._queue_completion_with_undo)
        self.task_list.task_completion_undo.connect(self._cancel_completion_with_undo)
        self.task_list.refresh_requested.connect(self._on_manual_refresh)

        # Worker thread -> UI thread updates.
        self.sync_worker.data_changed.connect(self._on_remote_data_changed)
        self.sync_worker.sync_finished.connect(self._on_sync_finished)
        self.sync_worker.sync_error.connect(self._on_sync_error)
        self.sync_worker.offline_mode.connect(self._on_offline_mode)
        self.sync_worker.tasklists_loaded.connect(self._on_tasklists_loaded)

        self.sync_thread.start()
        self._start_initial_sync()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_if_allowed)
        self.poll_timer.start(POLL_INTERVAL_MS)

    def _register_hotkey(self):
        try:
            import keyboard
        except ImportError:
            logging.warning("keyboard package is not available. Global hotkey is disabled.")
            return

        try:
            keyboard.add_hotkey("ctrl+shift+space", self.global_hotkey_activated.emit)
        except Exception:
            logging.exception("Failed to register global hotkey.")

    def _unregister_hotkey(self):
        try:
            import keyboard
        except ImportError:
            return

        try:
            if hasattr(keyboard, "unhook_all_hotkeys"):
                keyboard.unhook_all_hotkeys()
            else:
                keyboard.unhook_all()
        except Exception:
            pass

    def _on_hotkey(self):
        if self._is_expanded:
            if self.isActiveWindow():
                self._toggle_slide()
            else:
                self.activateWindow()
                self.task_list.setFocus()
            return

        self.activateWindow()
        self._toggle_slide()

    def closeEvent(self, event):
        self._unregister_hotkey()
        self._save_ui_state()
        if hasattr(self, "_tray_controller"):
            self._tray_controller.hide()

        if hasattr(self, "poll_timer"):
            self.poll_timer.stop()
        if hasattr(self, "_daily_timer"):
            self._daily_timer.stop()
        if hasattr(self, "_hover_expand_timer"):
            self._hover_expand_timer.stop()

        if hasattr(self, "sync_thread"):
            self.sync_thread.quit()
            self.sync_thread.wait(1500)

        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "error_overlay"):
            self.error_overlay.setGeometry(self.content_panel.rect())

    def _start_initial_sync(self):
        if self.app_state == AppSyncState.BLOCKING_ERROR:
            return
        self._set_sync_state(AppSyncState.SYNCING)
        QTimer.singleShot(0, self.request_initial_sync.emit)

    def _poll_if_allowed(self):
        if self.app_state in {AppSyncState.BLOCKING_ERROR, AppSyncState.SYNCING}:
            return
        self._set_sync_state(AppSyncState.SYNCING)
        self.request_poll_sync.emit()

    @pyqtSlot()
    def _on_remote_data_changed(self):
        self.task_list.load_tasks()
        self._update_progress()

    @pyqtSlot(object, str)
    def _on_tasklists_loaded(self, tasklists: object, selected_tasklist_id: str):
        items = list(tasklists) if isinstance(tasklists, list) else []
        if not items:
            return

        ids = {item.get("id") for item in items}
        if self.current_tasklist_id not in ids:
            first_id = items[0].get("id")
            if first_id:
                self.current_tasklist_id = first_id
                google_sync.tasklist_id = first_id
        elif selected_tasklist_id in ids:
            self.current_tasklist_id = selected_tasklist_id

        db.set_current_tasklist(self.current_tasklist_id)
        self.task_list.set_tasklists(items, self.current_tasklist_id)

    @pyqtSlot(str)
    def _on_tasklist_changed(self, tasklist_id: str):
        if not tasklist_id or tasklist_id == self.current_tasklist_id:
            return

        self.current_tasklist_id = tasklist_id
        google_sync.tasklist_id = tasklist_id
        db.set_current_tasklist(tasklist_id)
        self.task_list.load_tasks()
        self._update_progress()
        self._on_manual_refresh()

        if self._completed_log_window and self._completed_log_window.isVisible():
            self._completed_log_window.refresh_logs()

    @pyqtSlot(int)
    def _queue_completion_with_undo(self, task_id: int):
        self.complete_with_undo.queue(str(task_id))

    @pyqtSlot(str, object)
    def _on_task_create_requested(self, title: str, due_date: object):
        if self.app_state in {AppSyncState.BLOCKING_ERROR, AppSyncState.SYNCING, AppSyncState.OFFLINE_READONLY}:
            return
        due_text = due_date if isinstance(due_date, str) else ""
        self._set_sync_state(AppSyncState.SYNCING)
        self.request_add_task.emit(title, due_text)

    @pyqtSlot(int, str, object, str)
    def _on_task_update_requested(self, task_id: int, title: str, due_date: object, notes: str):
        if self.app_state in {AppSyncState.BLOCKING_ERROR, AppSyncState.SYNCING, AppSyncState.OFFLINE_READONLY}:
            return
        self._set_sync_state(AppSyncState.SYNCING)
        self.request_update_task.emit(task_id, title, due_date, notes)

    @pyqtSlot(int, bool)
    def _on_task_toggle_requested(self, task_id: int, is_done: bool):
        if self.app_state in {AppSyncState.BLOCKING_ERROR, AppSyncState.SYNCING, AppSyncState.OFFLINE_READONLY}:
            return
        self._set_sync_state(AppSyncState.SYNCING)
        self.request_toggle_task.emit(task_id, is_done)

    @pyqtSlot(int)
    def _cancel_completion_with_undo(self, task_id: int):
        self.complete_with_undo.cancel(str(task_id))

    def _commit_local_completion(self, task_id: str) -> bool:
        try:
            task_id_int = int(task_id)
        except ValueError:
            return False
        return self.task_list.finalize_completion(task_id_int)

    @pyqtSlot(str)
    def _on_completion_committed(self, task_id: str):
        try:
            task_id_int = int(task_id)
        except ValueError:
            return

        if self.app_state not in {AppSyncState.BLOCKING_ERROR, AppSyncState.OFFLINE_READONLY}:
            self._set_sync_state(AppSyncState.SYNCING)
            self.request_toggle_task.emit(task_id_int, True)
        self._update_progress()

        if self._completed_log_window and self._completed_log_window.isVisible():
            self._completed_log_window.refresh_logs()

    @pyqtSlot()
    def _on_sync_finished(self):
        if self.app_state == AppSyncState.SYNCING:
            self._set_sync_state(AppSyncState.IDLE)

    def _on_manual_refresh(self):
        if self.app_state in {AppSyncState.BLOCKING_ERROR, AppSyncState.SYNCING}:
            return
        self._set_sync_state(AppSyncState.SYNCING)
        self.request_poll_sync.emit()

    @pyqtSlot(str)
    def _on_sync_error(self, error_msg: str):
        self.task_list.load_tasks()
        self._update_progress()
        self._set_sync_state(AppSyncState.BLOCKING_ERROR, error_msg)

    @pyqtSlot()
    def _on_offline_mode(self):
        self.task_list.load_tasks()
        self._update_progress()
        self._set_sync_state(AppSyncState.OFFLINE_READONLY, "オフラインモード: 閲覧専用")

    def _retry_sync(self):
        self.error_overlay.clear()
        self._set_sync_state(AppSyncState.IDLE)
        self._on_manual_refresh()

    def _set_sync_state(self, state: AppSyncState, message: str = ""):
        # Centralized UI mode switch. Keep all interactive-state toggles here
        # so OFFLINE/BLOCKING/SYNCING transitions are predictable.
        self.app_state = state

        if state == AppSyncState.SYNCING:
            self.sync_progress.show()
            self.task_list.refresh_btn.setEnabled(False)
            self.task_list.refresh_btn.setToolTip("同期中...")
            self.task_list.set_read_only(True)
            self.task_list.set_dimmed(False)
            self.log_button.setEnabled(False)
            self.error_overlay.clear()
            return

        if state == AppSyncState.OFFLINE_READONLY:
            self.sync_progress.hide()
            self.task_list.refresh_btn.setEnabled(False)
            self.task_list.refresh_btn.setToolTip(message or "オフライン閲覧専用モード")
            self.task_list.set_read_only(True)
            self.task_list.set_dimmed(True)
            self.log_button.setEnabled(False)
            self.error_overlay.clear()
            return

        if state == AppSyncState.BLOCKING_ERROR:
            self.sync_progress.hide()
            self.task_list.refresh_btn.setEnabled(False)
            self.task_list.refresh_btn.setToolTip("通信エラー")
            self.task_list.set_read_only(True)
            self.task_list.set_dimmed(False)
            self.log_button.setEnabled(False)
            self.error_overlay.show_error(message or "通信エラーが発生しました。")
            return

        self.sync_progress.hide()
        self.task_list.refresh_btn.setEnabled(True)
        self.task_list.refresh_btn.setToolTip("Google Tasksと同期")
        self.task_list.set_read_only(False)
        self.task_list.set_dimmed(False)
        self.log_button.setEnabled(True)
        self.error_overlay.clear()

    def _apply_mask(self, visible_width: int):
        # The window always stays full-width geometrically.
        # A dynamic mask reveals only the right-side slice for the slide effect.
        visible_width = max(1, min(visible_width, self.width()))
        x = self.width() - visible_width
        rect = QRegion(x, 0, visible_width, self.height())
        self.setMask(rect)
        self._current_mask_width = visible_width

    def _get_slide_width(self) -> int:
        return self._current_mask_width

    def _set_slide_width(self, width: int):
        self._apply_mask(width)

    slideWidth = pyqtProperty(int, fget=_get_slide_width, fset=_set_slide_width)

    def _is_on_resize_edge(self, x_pos: int) -> bool:
        return self._is_expanded and not self._animating and x_pos <= RESIZE_MARGIN

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._is_on_resize_edge(int(event.position().x()))
        ):
            self._resizing = True
            self._resize_anchor_right = self.geometry().right() + 1
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            mouse_x = int(event.globalPosition().x())
            new_width = self._resize_anchor_right - mouse_x
            new_width = max(MIN_PANEL_WIDTH, min(MAX_PANEL_WIDTH, new_width))
            self._expanded_width = new_width
            self.setGeometry(self._resize_anchor_right - new_width, self.y(), new_width, self.height())
            self._apply_mask(new_width if self._is_expanded else TRIGGER_WIDTH)
            event.accept()
            return

        if self._is_on_resize_edge(int(event.position().x())):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif self.cursor().shape() == Qt.CursorShape.SizeHorCursor:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._resizing:
            self._resizing = False
            self.unsetCursor()
            self._save_ui_state()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)
        if not self._is_expanded and not self._animating:
            self.toggle_btn.setStyleSheet(TOGGLE_HOVER_STYLESHEET)
            self._hover_expand_timer.start(HOVER_EXPAND_DELAY_MS)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if not self._is_expanded and not self._animating:
            self.toggle_btn.setStyleSheet(TOGGLE_IDLE_STYLESHEET)
            self._hover_expand_timer.stop()

    def _expand_from_hover(self):
        if self._is_expanded or self._animating:
            return
        self._toggle_slide()

    def _toggle_slide(self):
        if self._animating:
            return

        self._animating = True
        if self._is_expanded:
            self.toggle_btn.setText(">")
            self._slide_anim.setStartValue(self.width())
            self._slide_anim.setEndValue(TRIGGER_WIDTH)
        else:
            self.toggle_btn.setStyleSheet(TOGGLE_EXPANDED_STYLESHEET)
            self.toggle_btn.setText("×")
            self.task_list.load_tasks()
            self._update_date_label()
            self._on_manual_refresh()
            self._slide_anim.setStartValue(TRIGGER_WIDTH)
            self._slide_anim.setEndValue(self.width())

        self._slide_anim.start()

    def _on_animation_finished(self):
        self._is_expanded = not self._is_expanded
        self._animating = False

        if not self._is_expanded:
            self.toggle_btn.setStyleSheet(TOGGLE_IDLE_STYLESHEET)
            self._hover_expand_timer.stop()
            return

        self.task_list.setFocus()

    def changeEvent(self, event):
        super().changeEvent(event)
        if (
            event.type() == event.Type.ActivationChange
            and not self.isActiveWindow()
            and self._is_expanded
            and not self._animating
        ):
            active = QApplication.activeWindow()
            if active and isinstance(active, CompletedLogWindow):
                return
            self._toggle_slide()

    def _update_progress(self):
        total, done = db.get_today_stats()
        pct = int(done / total * 100) if total > 0 else 0

        self.progress_bar.setValue(pct)
        self.progress_pct_label.setText(f"{pct}%")
        if pct >= 100:
            self.progress_pct_label.setStyleSheet("color: #10b981; font-size: 20px; font-weight: 700;")
        else:
            self.progress_pct_label.setStyleSheet("color: #a78bfa; font-size: 20px; font-weight: 700;")

    def _update_date_label(self):
        today = date.today()
        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        weekday = weekdays[today.weekday()]
        self.task_list.update_date_label(f"{today.strftime('%Y/%m/%d')} ({weekday})")

    def _check_daily_reset(self):
        if daily_reset.check_and_reset():
            self.task_list.load_tasks()
            self._update_progress()
            self._update_date_label()

    def keyPressEvent(self, event):
        if self._is_expanded and event.key() in {
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Space,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        }:
            self.task_list.keyPressEvent(event)
            if event.isAccepted():
                return
        super().keyPressEvent(event)

    def _show_completed_log(self):
        if self._completed_log_window is None:
            self._completed_log_window = CompletedLogWindow(
                tasklist_provider=lambda: self.current_tasklist_id,
                parent=self,
            )

        self._completed_log_window.refresh_logs()
        self._completed_log_window.show()
        self._completed_log_window.raise_()
        self._completed_log_window.activateWindow()

    def _setup_tray(self):
        self._tray_controller = TrayController(
            parent=self,
            callbacks=TrayCallbacks(
                toggle=self._toggle_slide,
                show_completed_log=self._show_completed_log,
                set_pin_mode=self._set_pin_mode,
                toggle_startup=self._toggle_startup,
                quit_app=self._quit_app,
            ),
            pinned=self._pinned,
            startup_enabled=startup.is_registered(),
        )
        self._tray_controller.show()

    def _toggle_startup(self):
        if startup.is_registered():
            startup.unregister()
            self._startup_opt_out = True
        else:
            startup.register()
            self._startup_opt_out = False
        self._update_startup_action_text()
        self._save_ui_state()

    def _apply_startup_policy(self):
        if self._startup_opt_out:
            self._update_startup_action_text()
            return
        if not startup.is_registered():
            startup.register()
        self._update_startup_action_text()

    def _apply_pin_flag(self, pinned: bool):
        flags = Qt.WindowType.FramelessWindowHint
        if pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _set_pin_mode(self, pinned: bool):
        if self._pinned == pinned:
            return

        self._pinned = pinned
        geometry = self.geometry()
        self._apply_pin_flag(pinned)
        self.show()
        self.setGeometry(geometry)
        self._apply_mask(self._current_mask_width)
        if hasattr(self, "_tray_controller"):
            self._tray_controller.set_pinned(self._pinned)
        self._save_ui_state()

    def _load_ui_state(self) -> MainWindowState:
        return self._ui_state_store.load()

    def _save_ui_state(self):
        self._ui_state_store.save(
            MainWindowState(
                panel_width=self._expanded_width,
                pinned=self._pinned,
                startup_opt_out=self._startup_opt_out,
            )
        )

    def _update_startup_action_text(self):
        if hasattr(self, "_tray_controller"):
            self._tray_controller.set_startup_enabled(startup.is_registered())

    def _quit_app(self):
        if hasattr(self, "_tray_controller"):
            self._tray_controller.hide()
        QApplication.quit()
