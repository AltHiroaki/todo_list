"""
SlideTasks — SQLite データベース操作
tasks テーブルと daily_logs テーブルの CRUD を提供する。
"""

import sqlite3
import os
from datetime import datetime, date


from app.utils import get_base_path

DB_DIR = os.path.join(get_base_path(), "data")
DB_PATH = os.path.join(DB_DIR, "slidetasks.db")


def _get_connection() -> sqlite3.Connection:
    """DB接続を取得（ディレクトリがなければ作成）"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn



def init_db():
    """テーブルを初期化する"""
    conn = _get_connection()
    
    # マイグレーション: due_date カラムがない場合は reset_all_data を呼ぶためのチェック
    try:
        # tasks テーブルがあるか確認
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()
        
        if table_exists:
            # due_date カラムがあるか確認
            columns = conn.execute("PRAGMA table_info(tasks)").fetchall()
            column_names = [col["name"] for col in columns]
            
            missing_cols = []
            if "due_date" not in column_names:
                missing_cols.append("due_date")
            if "google_calendar_event_id" not in column_names:
                missing_cols.append("google_calendar_event_id")
                
            if missing_cols:
                # カラムが足りないのでリセット（開発中につき簡易対応）
                conn.close()
                reset_all_data()
                return
    except Exception:
        pass

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT    NOT NULL,
            is_done         INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL,
            completed_at    TEXT,
            google_task_id  TEXT,
            due_date        TEXT,
            google_calendar_event_id TEXT
        );
        CREATE TABLE IF NOT EXISTS daily_logs (
            date             TEXT PRIMARY KEY,
            total_count      INTEGER NOT NULL DEFAULT 0,
            done_count       INTEGER NOT NULL DEFAULT 0,
            achievement_rate REAL    NOT NULL DEFAULT 0.0
        );
    """)
    conn.commit()
    conn.close()


def reset_all_data():
    """全データを削除し、テーブルを再作成する（開発用）"""
    conn = _get_connection()
    conn.executescript("""
        DROP TABLE IF EXISTS tasks;
        DROP TABLE IF EXISTS daily_logs;
    """)
    conn.close()
    init_db()


# ── タスク CRUD ────────────────────────────────────────

def add_task(title: str, due_date: str | None = None) -> dict:
    """タスクを追加し、追加した行を辞書で返す"""
    conn = _get_connection()
    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO tasks (title, is_done, created_at, due_date) VALUES (?, 0, ?, ?)",
        (title, now, due_date),
    )
    task_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row)


def toggle_done(task_id: int) -> dict:
    """完了 ↔ 未完了をトグルし、更新後の行を返す"""
    conn = _get_connection()
    row = conn.execute("SELECT is_done FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"Task {task_id} not found")
    new_done = 0 if row["is_done"] else 1
    completed_at = datetime.now().isoformat() if new_done else None
    conn.execute(
        "UPDATE tasks SET is_done = ?, completed_at = ? WHERE id = ?",
        (new_done, completed_at, task_id),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(updated)


def delete_task(task_id: int):
    """タスクを削除する"""
    conn = _get_connection()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def get_active_tasks() -> list[dict]:
    """今日作成された or 未完了のタスクを返す（完了タスクも含む）"""
    conn = _get_connection()
    today_str = date.today().isoformat()
    rows = conn.execute(
        """SELECT * FROM tasks
           WHERE is_done = 0
              OR (is_done = 1 AND date(created_at) = ?)
           ORDER BY is_done ASC, due_date ASC, id ASC""",
        (today_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_tasks() -> list[dict]:
    """今日のアクティブなタスク（未完了 + 今日完了したもの）を全て返す"""
    conn = _get_connection()
    today_str = date.today().isoformat()
    rows = conn.execute(
        """SELECT * FROM tasks
           WHERE is_done = 0
              OR (is_done = 1 AND date(completed_at) >= ?)
           ORDER BY is_done ASC, due_date ASC, id ASC""",
        (today_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_stats() -> tuple[int, int]:
    """(総タスク数, 完了タスク数) を返す"""
    tasks = get_today_tasks()
    total = len(tasks)
    done = sum(1 for t in tasks if t["is_done"])
    return total, done


def update_google_task_id(task_id: int, google_task_id: str):
    """Google Tasks の ID を紐づける"""
    conn = _get_connection()
    conn.execute(
        "UPDATE tasks SET google_task_id = ? WHERE id = ?",
        (google_task_id, task_id),
    )
    conn.commit()
    conn.close()


def update_google_calendar_event_id(task_id: int, event_id: str):
    """Google Calendar Event ID を紐づける"""
    conn = _get_connection()
    conn.execute(
        "UPDATE tasks SET google_calendar_event_id = ? WHERE id = ?",
        (event_id, task_id),
    )
    conn.commit()
    conn.close()


def get_google_task_id(task_id: int) -> str | None:
    """タスクIDからGoogle Task IDを取得する"""
    conn = _get_connection()
    row = conn.execute("SELECT google_task_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return row["google_task_id"] if row else None


def get_tasks_for_date(target_date: date) -> list[dict]:
    """
    指定した日付のアクティビティ（作成 or 完了）を取得する。
    - その日に完了したタスク
    - その日に作成されたタスク
    ※以前はバックログ（未完了タスク全て）を表示していたが、
      「複数の日付が混入」という指摘を受け、その日に動きがあったものだけに限定する。
    """
    conn = _get_connection()
    t_str = target_date.isoformat()
    
    # 1. その日に完了したタスク OR その日に作成されたタスク
    rows = conn.execute(
        """
        SELECT * FROM tasks 
        WHERE date(created_at) = ?
           OR (is_done = 1 AND date(completed_at) = ?)
        """,
        (t_str, t_str)
    ).fetchall()
    
    conn.close()
    
    results = []
    for r in rows:
        d = dict(r)
        # その日時点でのステータスを判定
        # 完了日がその日なら done, そうでなければ（作成されただけなら） active
        if d['is_done'] and d['completed_at'] and d['completed_at'].startswith(t_str):
            d['_status_on_date'] = 'done'
        else:
            d['_status_on_date'] = 'active'
        results.append(d)
        
    return sorted(results, key=lambda x: x['id'])


def get_aggregated_logs(period: str = 'month') -> list[dict]:
    """
    指定期間ごとのログを集計して返す
    period: 'week' (直近7日), 'month' (直近30日), 'year' (直近12ヶ月 - 月単位集計)
    """
    conn = _get_connection()
    
    if period == 'year':
        # 月ごとの集計
        # last 12 months
        rows = conn.execute(
            """
            SELECT 
                strftime('%Y-%m', date) as month,
                SUM(total_count) as total,
                SUM(done_count) as done
            FROM daily_logs
            WHERE date >= date('now', '-12 months', 'start of month')
            GROUP BY month
            ORDER BY month DESC
            """
        ).fetchall()
        
        result = []
        for r in rows:
            t = r['total']
            d = r['done']
            rate = (d / t * 100) if t > 0 else 0
            result.append({
                'date': r['month'], # "2023-10"
                'total_count': t,
                'done_count': d,
                'achievement_rate': rate
            })
        conn.close()
        return result

    else:
        # 日ごとのデータ (week=7, month=30)
        limit = 7 if period == 'week' else 30
        rows = conn.execute(
            """SELECT * FROM daily_logs
               ORDER BY date DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


def get_logs_in_range(start_date: date, end_date: date) -> list[dict]:
    """指定期間（開始日〜終了日）のログを全て返す"""
    conn = _get_connection()
    rows = conn.execute(
        """SELECT * FROM daily_logs
           WHERE date >= ? AND date <= ?
           ORDER BY date DESC""",
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    conn.close()
    try:
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_yearly_stats(year: int) -> list[dict]:

    """指定年の月別集計を返す（1月〜12月）"""
    conn = _get_connection()
    
    # 1. 1〜12月の枠を作成
    monthly_data = {
        f"{year}-{month:02d}": {"total": 0, "done": 0} 
        for month in range(1, 13)
    }

    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    rows = conn.execute(
        """
        SELECT 
            strftime('%Y-%m', date) as month,
            SUM(total_count) as total,
            SUM(done_count) as done
        FROM daily_logs
        WHERE date >= ? AND date <= ?
        GROUP BY month
        """,
        (start_date, end_date)
    ).fetchall()
    conn.close()

    # 2. 取得したデータを枠に埋める
    for r in rows:
        m = r['month']
        if m in monthly_data:
            monthly_data[m]['total'] = r['total'] if r['total'] else 0
            monthly_data[m]['done'] = r['done'] if r['done'] else 0

    result = []
    # UI側で reverse して表示しているので、ここでは DESC (新しい順: 12月 -> 1月) で返す
    months_desc = sorted(monthly_data.keys(), reverse=True)
    
    for month_str in months_desc:
        data = monthly_data[month_str]
        t = data['total']
        d = data['done']
        rate = (d / t * 100) if t > 0 else 0
        result.append({
            'date': month_str,
            'total_count': t,
            'done_count': d,
            'achievement_rate': rate
        })
        
    return result


# ── 日次ログ ───────────────────────────────────────────

def save_daily_log(target_date: date, total: int, done: int):
    """指定日の日次ログを保存（UPSERT）"""
    rate = (done / total * 100) if total > 0 else 0.0
    conn = _get_connection()
    conn.execute(
        """INSERT INTO daily_logs (date, total_count, done_count, achievement_rate)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET
               total_count = excluded.total_count,
               done_count  = excluded.done_count,
               achievement_rate = excluded.achievement_rate""",
        (target_date.isoformat(), total, done, rate),
    )
    conn.commit()
    conn.close()


def get_logs(days: int = 30) -> list[dict]:
    """直近 N 日間のログを返す"""
    conn = _get_connection()
    rows = conn.execute(
        """SELECT * FROM daily_logs
           ORDER BY date DESC
           LIMIT ?""",
        (days,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def archive_completed_tasks():
    """完了済みタスクを非表示（削除）にする。日次リセットで呼ぶ。"""
    # 履歴機能のために削除しないように変更
    pass

