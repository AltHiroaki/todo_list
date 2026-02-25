from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class ErrorOverlay(QWidget):
    retry_clicked = pyqtSignal()
    reauth_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("errorOverlay")
        self.setVisible(False)
        self.setStyleSheet(
            """
            QWidget#errorOverlay {
                background-color: rgba(0, 0, 0, 175);
                border-radius: 12px;
            }
            QLabel#errorTitle {
                color: #f8fafc;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#errorMessage {
                color: #cbd5e1;
                font-size: 12px;
            }
            QPushButton#errorRetry, QPushButton#errorReauth {
                background-color: #8b5cf6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton#errorRetry:hover, QPushButton#errorReauth:hover {
                background-color: #7c3aed;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        self.title_label = QLabel("通信エラー")
        self.title_label.setObjectName("errorTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.message_label = QLabel("Google Tasksに接続できません。")
        self.message_label.setObjectName("errorMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.message_label)

        self.retry_button = QPushButton("再試行")
        self.retry_button.setObjectName("errorRetry")
        self.retry_button.clicked.connect(self.retry_clicked.emit)
        layout.addWidget(self.retry_button)

        self.reauth_button = QPushButton("再認証する")
        self.reauth_button.setObjectName("errorReauth")
        self.reauth_button.clicked.connect(self.reauth_clicked.emit)
        self.reauth_button.setVisible(False)
        layout.addWidget(self.reauth_button)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def show_error(self, message: str, *, show_reauth: bool = False) -> None:
        self.message_label.setText(message)
        if show_reauth:
            self.title_label.setText("認証エラー")
            self.retry_button.setVisible(False)
            self.reauth_button.setVisible(True)
        else:
            self.title_label.setText("通信エラー")
            self.retry_button.setVisible(True)
            self.reauth_button.setVisible(False)
        self.setVisible(True)
        self.raise_()

    def clear(self) -> None:
        self.setVisible(False)
        self.retry_button.setVisible(True)
        self.reauth_button.setVisible(False)


