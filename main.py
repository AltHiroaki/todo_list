"""
SlideTasks for Windows — エントリーポイント
画面右端に常駐するスライド式TODOアプリケーション。
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SlideTasks")
    app.setQuitOnLastWindowClosed(False)  # トレイ常駐向け

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
