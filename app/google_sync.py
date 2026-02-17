"""
SlideTasks — Google Tasks API 連携
OAuth 2.0 認証 + タスクの push/pull を行う。
双方向同期・リアルタイム更新対応。
"""

import os
import logging
from typing import List, Dict, Optional

# Google API パッケージ
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    HAS_GOOGLE_API = True
except ImportError:
    HAS_GOOGLE_API = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.utils import get_base_path

BASE_DIR = get_base_path()
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
SCOPES = [
    "https://www.googleapis.com/auth/tasks",
]


class GoogleTaskSync:
    def __init__(self):
        self.service = None
        self.tasklist_id = "@default"  # "My Tasks" は通常 @default

    def is_available(self) -> bool:
        """Google 連携が利用可能か"""
        return HAS_GOOGLE_API and os.path.exists(CREDENTIALS_FILE)

    def authenticate(self) -> bool:
        """認証を行いサービスを初期化する。失敗したらFalse"""
        if not self.is_available():
            logger.error("Google API libraries or credentials.json missing.")
            return False

        try:
            creds = None
            if os.path.exists(TOKEN_FILE):
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # トークン保存
                with open(TOKEN_FILE, "w") as f:
                    f.write(creds.to_json())

            self.service = build("tasks", "v1", credentials=creds)
            return True

        except Exception as e:
            logger.exception(f"Authentication failed: {e}")
            return False

    def _ensure_service(self) -> bool:
        if self.service:
            return True
        return self.authenticate()

    def fetch_tasks(self) -> List[Dict]:
        """
        未完了タスク + 直近24時間に完了したタスクを取得する
        return: [{'id': '...', 'title': '...', 'status': '...'}, ...]
        """
        if not self._ensure_service():
            return []

        try:
            # 1. 未完了タスク (showCompleted=False)
            results_open = self.service.tasks().list(
                tasklist=self.tasklist_id,
                showCompleted=False,
                showHidden=False
            ).execute()
            items_open = results_open.get("items", [])

            # 2. 直近24時間の完了タスク (showCompleted=True, completedMin=...)
            # RFC3339 timestamp format
            from datetime import datetime, timedelta, timezone
            min_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

            results_completed = self.service.tasks().list(
                tasklist=self.tasklist_id,
                showCompleted=True,
                showHidden=True,
                completedMin=min_date
            ).execute()
            items_completed = results_completed.get("items", [])
            
            # マージ (重複除去は念のためIDで行う)
            all_items = {t['id']: t for t in items_open}
            for t in items_completed:
                all_items[t['id']] = t
                
            return list(all_items.values())

        except Exception as e:
            logger.error(f"Failed to fetch tasks: {e}")
            return []

    def add_task(self, title: str, due_date: str | None = None) -> Optional[str]:
        """
        タスクを追加し、Google Task IDを返す
        due_date: "YYYY-MM-DD" or None
        """
        if not self._ensure_service():
            return None

        try:
            body = {"title": title, "status": "needsAction"}
            
            if due_date:
                # RFC3339 format: YYYY-MM-DDT00:00:00.000Z
                # ユーザーの入力は "YYYY-MM-DD"
                # ToDoリストなので時間は 00:00:00 でUTC扱いにするのが一般的
                body['due'] = f"{due_date}T00:00:00.000Z"

            result = self.service.tasks().insert(
                tasklist=self.tasklist_id,
                body=body
            ).execute()
            return result.get("id")
        except Exception as e:
            logger.error(f"Failed to add task: {e}")
            return None

    def complete_task(self, google_task_id: str) -> bool:
        """
        タスクを完了(completed)にする
        """
        if not self._ensure_service() or not google_task_id:
            return False

        try:
            # まず取得して update する必要がある
            task = self.service.tasks().get(
                tasklist=self.tasklist_id, 
                task=google_task_id
            ).execute()
            
            task["status"] = "completed"
            
            self.service.tasks().update(
                tasklist=self.tasklist_id,
                task=google_task_id,
                body=task
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to complete task {google_task_id}: {e}")
            return False

    def reopen_task(self, google_task_id: str) -> bool:
        """
        タスクを未完了(needsAction)に戻す
        """
        if not self._ensure_service() or not google_task_id:
            return False

        try:
            task = self.service.tasks().get(
                tasklist=self.tasklist_id, 
                task=google_task_id
            ).execute()
            
            task["status"] = "needsAction"
            # completed 日時はクリアされるはずだが、明示的にnull送ってもよいが、status変更だけで十分なはず
            task.pop("completed", None) 
            
            self.service.tasks().update(
                tasklist=self.tasklist_id,
                task=google_task_id,
                body=task
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to reopen task {google_task_id}: {e}")
            return False

    def delete_task(self, google_task_id: str) -> bool:
        """
        タスクを削除する
        """
        if not self._ensure_service() or not google_task_id:
            return False

        try:
            self.service.tasks().delete(
                tasklist=self.tasklist_id,
                task=google_task_id
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete task {google_task_id}: {e}")
            return False
            
    def update_title(self, google_task_id: str, new_title: str) -> bool:
        """
        タスクのタイトルを更新する
        """
        if not self._ensure_service() or not google_task_id:
            return False
            
        try:
            task = self.service.tasks().get(
                tasklist=self.tasklist_id, 
                task=google_task_id
            ).execute()
            
            if task['title'] == new_title:
                return True # No change needed
                
            task['title'] = new_title
            
            self.service.tasks().update(
                tasklist=self.tasklist_id,
                task=google_task_id,
                body=task
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update task title {google_task_id}: {e}")
            return False

# シングルトンとしてインスタンスを用意しておくと便利
google_sync = GoogleTaskSync()
