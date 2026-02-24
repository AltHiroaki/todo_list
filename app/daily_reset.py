"""
SlideTasks — 日次リセット処理
日付が変わったら前日の統計を保存し、完了タスクをアーカイブする。
"""

from datetime import date, timedelta
from app import database as db


_last_known_date: date | None = None


def check_and_reset() -> bool:
    """
    日付が変わったかを確認し、変わっていれば日次リセットを実行する。
    Returns: True if reset was performed.
    """
    global _last_known_date
    today = date.today()

    if _last_known_date is None:
        _last_known_date = today
        return False

    if today <= _last_known_date:
        return False

    # 日付が変わった → 前日の統計を保存してリセット
    _perform_reset(_last_known_date)
    _last_known_date = today
    return True


def initialize(current_date: date | None = None):
    """起動時に呼ぶ。前回の日付と比較してリセットが必要か判定する。"""
    global _last_known_date
    _last_known_date = current_date or date.today()


def _perform_reset(yesterday: date):
    """前日の記録を保存する"""
    total, done = db.get_today_stats()
    if total > 0:
        db.save_daily_log(yesterday, total, done)
