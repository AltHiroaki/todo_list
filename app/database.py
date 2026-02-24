"""SQLite storage for SlideTasks.

This module intentionally keeps a small API surface used by the UI and sync worker.
Google Tasks remains the source of truth, while SQLite stores UI-friendly local state.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime

from app.utils import get_base_path

DB_DIR = os.path.join(get_base_path(), "data")
DB_PATH = os.path.join(DB_DIR, "slidetasks.db")
DEFAULT_TASKLIST_ID = "@default"

_current_tasklist_id = DEFAULT_TASKLIST_ID


def _get_connection() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def set_current_tasklist(tasklist_id: str):
    global _current_tasklist_id
    _current_tasklist_id = tasklist_id or DEFAULT_TASKLIST_ID


def get_current_tasklist() -> str:
    return _current_tasklist_id


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = _get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT    NOT NULL,
            is_done         INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL,
            completed_at    TEXT,
            google_task_id  TEXT,
            due_date        TEXT,
            tasklist_id     TEXT    NOT NULL DEFAULT '@default',
            google_position TEXT,
            parent_google_id TEXT,
            notes           TEXT
        );
        CREATE TABLE IF NOT EXISTS daily_logs (
            date             TEXT PRIMARY KEY,
            total_count      INTEGER NOT NULL DEFAULT 0,
            done_count       INTEGER NOT NULL DEFAULT 0,
            achievement_rate REAL    NOT NULL DEFAULT 0.0
        );
        """
    )
    _ensure_column(conn, "tasks", "tasklist_id", "TEXT NOT NULL DEFAULT '@default'")
    _ensure_column(conn, "tasks", "google_position", "TEXT")
    _ensure_column(conn, "tasks", "parent_google_id", "TEXT")
    _ensure_column(conn, "tasks", "notes", "TEXT")
    conn.execute("UPDATE tasks SET tasklist_id = ? WHERE tasklist_id IS NULL OR tasklist_id = ''", (DEFAULT_TASKLIST_ID,))
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_tasklist ON tasks(tasklist_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_tasklist_google ON tasks(tasklist_id, google_task_id)")
    conn.commit()
    conn.close()


def reset_all_data():
    conn = _get_connection()
    conn.executescript(
        """
        DROP TABLE IF EXISTS tasks;
        DROP TABLE IF EXISTS daily_logs;
        """
    )
    conn.close()
    init_db()


def add_task(
    title: str,
    due_date: str | None = None,
    tasklist_id: str | None = None,
    created_at: str | None = None,
    completed_at: str | None = None,
    is_done: int = 0,
) -> dict:
    conn = _get_connection()
    tasklist_id = tasklist_id or get_current_tasklist()
    created_at = created_at or datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO tasks (title, is_done, created_at, completed_at, due_date, tasklist_id) VALUES (?, ?, ?, ?, ?, ?)",
        (title, is_done, created_at, completed_at, due_date, tasklist_id),
    )
    task_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row)


def toggle_done(task_id: int) -> dict:
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


def get_active_tasks() -> list[dict]:
    conn = _get_connection()
    today_str = date.today().isoformat()
    current_tasklist = get_current_tasklist()
    rows = conn.execute(
        """
        SELECT * FROM tasks
        WHERE tasklist_id = ?
          AND (
               is_done = 0
           OR (is_done = 1 AND date(created_at) = ?)
          )
        ORDER BY is_done ASC,
                 CASE WHEN google_position IS NULL THEN 1 ELSE 0 END ASC,
                 google_position ASC,
                 due_date ASC,
                 id ASC
        """,
        (current_tasklist, today_str),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_today_tasks() -> list[dict]:
    conn = _get_connection()
    current_tasklist = get_current_tasklist()
    rows = conn.execute(
        """
        SELECT * FROM tasks
        WHERE tasklist_id = ?
          AND (
               is_done = 0
           OR (is_done = 1 AND substr(completed_at, 1, 10) = date('now', 'localtime'))
          )
        ORDER BY is_done ASC,
                 CASE WHEN google_position IS NULL THEN 1 ELSE 0 END ASC,
                 google_position ASC,
                 due_date ASC,
                 id ASC
        """
        ,
        (current_tasklist,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_tasks(tasklist_id: str | None = None) -> list[dict]:
    effective_tasklist = tasklist_id or get_current_tasklist()
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE tasklist_id = ? ORDER BY id ASC",
        (effective_tasklist,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_today_stats() -> tuple[int, int]:
    tasks = get_today_tasks()
    today_str = date.today().isoformat()

    total = 0
    done = 0
    for item in tasks:
        if item["is_done"]:
            done += 1
            total += 1
        else:
            if not item["due_date"] or item["due_date"] <= today_str:
                total += 1

    return total, done


def update_google_task_id(task_id: int, google_task_id: str):
    conn = _get_connection()
    conn.execute("UPDATE tasks SET google_task_id = ? WHERE id = ?", (google_task_id, task_id))
    conn.commit()
    conn.close()


def update_due_date(task_id: int, due_date: str | None):
    conn = _get_connection()
    conn.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (due_date, task_id))
    conn.commit()
    conn.close()


def update_task_title(task_id: int, new_title: str):
    conn = _get_connection()
    conn.execute("UPDATE tasks SET title = ? WHERE id = ?", (new_title, task_id))
    conn.commit()
    conn.close()


def update_task_notes(task_id: int, notes: str):
    conn = _get_connection()
    conn.execute("UPDATE tasks SET notes = ? WHERE id = ?", (notes, task_id))
    conn.commit()
    conn.close()


def update_task_details(task_id: int, title: str, due_date: str | None, notes: str):
    conn = _get_connection()
    conn.execute(
        "UPDATE tasks SET title = ?, due_date = ?, notes = ? WHERE id = ?",
        (title, due_date, notes, task_id),
    )
    conn.commit()
    conn.close()


def get_google_task_id(task_id: int) -> str | None:
    conn = _get_connection()
    row = conn.execute("SELECT google_task_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return row["google_task_id"] if row else None


def get_tasks_for_date(target_date: date) -> list[dict]:
    conn = _get_connection()
    target = target_date.isoformat()
    current_tasklist = get_current_tasklist()
    rows = conn.execute(
        """
        SELECT * FROM tasks
        WHERE tasklist_id = ?
          AND (
               date(created_at) = ?
           OR (is_done = 1 AND date(completed_at) = ?)
          )
        """,
        (current_tasklist, target, target),
    ).fetchall()
    conn.close()

    results: list[dict] = []
    for row in rows:
        item = dict(row)
        if item["is_done"] and item["completed_at"] and item["completed_at"].startswith(target):
            item["_status_on_date"] = "done"
        else:
            item["_status_on_date"] = "active"
        results.append(item)

    return sorted(results, key=lambda x: x["id"])


def recalc_stats_for_date(target_date: date) -> dict:
    conn = _get_connection()
    target = target_date.isoformat()
    current_tasklist = get_current_tasklist()
    rows = conn.execute(
        """
        SELECT is_done, completed_at FROM tasks
        WHERE tasklist_id = ?
          AND (
               date(created_at) = ?
           OR (is_done = 1 AND date(completed_at) = ?)
          )
        """,
        (current_tasklist, target, target),
    ).fetchall()
    conn.close()

    total = len(rows)
    done = 0
    for row in rows:
        if row["is_done"] and row["completed_at"] and row["completed_at"].startswith(target):
            done += 1

    rate = (done / total * 100) if total > 0 else 0.0
    return {
        "date": target,
        "total_count": total,
        "done_count": done,
        "achievement_rate": rate,
    }


def get_logs_in_range(start_date: date, end_date: date) -> list[dict]:
    conn = _get_connection()
    rows = conn.execute(
        """
        SELECT * FROM daily_logs
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_yearly_stats(year: int) -> list[dict]:
    conn = _get_connection()

    monthly = {f"{year}-{month:02d}": {"total": 0, "done": 0} for month in range(1, 13)}
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    rows = conn.execute(
        """
        SELECT
            strftime('%Y-%m', date) AS month,
            SUM(total_count) AS total,
            SUM(done_count) AS done
        FROM daily_logs
        WHERE date >= ? AND date <= ?
        GROUP BY month
        """,
        (start_date, end_date),
    ).fetchall()
    conn.close()

    for row in rows:
        month = row["month"]
        if month in monthly:
            monthly[month]["total"] = row["total"] or 0
            monthly[month]["done"] = row["done"] or 0

    result = []
    for month in sorted(monthly.keys(), reverse=True):
        total = monthly[month]["total"]
        done = monthly[month]["done"]
        rate = (done / total * 100) if total > 0 else 0
        result.append(
            {
                "date": month,
                "total_count": total,
                "done_count": done,
                "achievement_rate": rate,
            }
        )
    return result


def save_daily_log(target_date: date, total: int, done: int):
    rate = (done / total * 100) if total > 0 else 0.0
    conn = _get_connection()
    conn.execute(
        """
        INSERT INTO daily_logs (date, total_count, done_count, achievement_rate)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            total_count = excluded.total_count,
            done_count = excluded.done_count,
            achievement_rate = excluded.achievement_rate
        """,
        (target_date.isoformat(), total, done, rate),
    )
    conn.commit()
    conn.close()
