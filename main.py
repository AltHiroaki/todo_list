"""
SlideTasks for Windows — エントリーポイント
画面右端に常駐するスライド式TODOアプリケーション。
"""

from __future__ import annotations

import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.utils import get_base_path


def setup_logging() -> None:
    log_dir = os.path.join(get_base_path(), "data")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> None:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("SlideTasks")
    app.setQuitOnLastWindowClosed(False)  # トレイ常駐向け

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
