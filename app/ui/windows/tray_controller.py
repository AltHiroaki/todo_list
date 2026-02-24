"""System tray controller for MainWindow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


@dataclass(slots=True)
class TrayCallbacks:
    toggle: Callable[[], None]
    show_completed_log: Callable[[], None]
    set_pin_mode: Callable[[bool], None]
    toggle_startup: Callable[[], None]
    quit_app: Callable[[], None]


class TrayController:
    """Owns tray icon and menu actions."""

    def __init__(
        self,
        parent: QWidget,
        callbacks: TrayCallbacks,
        *,
        pinned: bool,
        startup_enabled: bool,
    ):
        self._callbacks = callbacks
        self._tray_icon = QSystemTrayIcon(parent)
        self._tray_icon.setIcon(_create_tray_icon())
        self._tray_icon.setToolTip("SlideTasks")
        self._tray_icon.activated.connect(self._on_activated)

        menu = QMenu()
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #1e1e33;
                color: #f1f0f7;
                border: 1px solid #2a2a45;
                border-radius: 8px;
                padding: 6px 2px;
                font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 8px 24px 8px 16px;
                border-radius: 4px;
                margin: 1px 4px;
            }
            QMenu::item:selected {
                background-color: rgba(139, 92, 246, 0.2);
                color: #a78bfa;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2a2a45;
                margin: 4px 12px;
            }
            """
        )

        toggle_action = QAction("開く / 閉じる", parent)
        toggle_action.triggered.connect(self._callbacks.toggle)
        menu.addAction(toggle_action)

        completed_action = QAction("完了ログ", parent)
        completed_action.triggered.connect(self._callbacks.show_completed_log)
        menu.addAction(completed_action)
        menu.addSeparator()

        self._pin_action = QAction("最前面に固定", parent)
        self._pin_action.setCheckable(True)
        self._pin_action.setChecked(pinned)
        self._pin_action.toggled.connect(self._callbacks.set_pin_mode)
        menu.addAction(self._pin_action)

        self._startup_action = QAction(parent)
        self._startup_action.triggered.connect(self._callbacks.toggle_startup)
        menu.addAction(self._startup_action)
        self.set_startup_enabled(startup_enabled)

        menu.addSeparator()
        quit_action = QAction("終了", parent)
        quit_action.triggered.connect(self._callbacks.quit_app)
        menu.addAction(quit_action)

        self._tray_icon.setContextMenu(menu)

    def show(self) -> None:
        self._tray_icon.show()

    def hide(self) -> None:
        self._tray_icon.hide()

    def set_pinned(self, pinned: bool) -> None:
        self._pin_action.blockSignals(True)
        self._pin_action.setChecked(pinned)
        self._pin_action.blockSignals(False)

    def set_startup_enabled(self, enabled: bool) -> None:
        self._startup_action.setText("自動起動を無効化" if enabled else "自動起動を有効化")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._callbacks.toggle()


def _create_tray_icon() -> QIcon:
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor("#8b5cf6")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, size - 8, size - 8, 14, 14)

    pen = QPen(QColor("#ffffff"))
    pen.setWidth(5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(18, 33, 28, 43)
    painter.drawLine(28, 43, 46, 22)
    painter.end()

    return QIcon(pixmap)
