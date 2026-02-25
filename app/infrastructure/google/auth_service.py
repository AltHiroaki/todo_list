from __future__ import annotations

import logging
import os

from app.domain.auth_errors import AuthRequiredError
from app.utils import get_base_path

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    HAS_GOOGLE_LIBS = True
except ImportError:
    HAS_GOOGLE_LIBS = False
    Credentials = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


class GoogleAuthService:
    SCOPES = ["https://www.googleapis.com/auth/tasks"]

    def __init__(self, credentials_path: str | None = None, token_path: str | None = None):
        base = get_base_path()
        self.credentials_path = credentials_path or os.path.join(base, "credentials.json")
        self.token_path = token_path or os.path.join(base, "token.json")
        self._credentials = None
        self._service = None

    def is_available(self) -> bool:
        return HAS_GOOGLE_LIBS and os.path.exists(self.credentials_path)

    def authenticate(self) -> bool:
        """Authenticate using stored/refreshable credentials only.

        Raises:
            AuthRequiredError: When credentials are missing or cannot be
                refreshed and interactive re-authentication is required.
        """
        if not self.is_available():
            logger.error("Google API libraries or credentials.json are missing.")
            return False

        try:
            creds = None
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # Do NOT launch browser implicitly – signal the caller.
                    raise AuthRequiredError()

                with open(self.token_path, "w", encoding="utf-8") as file:
                    file.write(creds.to_json())

            self._credentials = creds
            self._service = build("tasks", "v1", credentials=creds)
            return True
        except AuthRequiredError:
            raise
        except Exception:
            logger.exception("Google OAuth authentication failed.")
            return False

    def run_interactive_auth(self) -> bool:
        """Run the full OAuth browser flow.  Call ONLY from the UI thread."""
        if not self.is_available():
            return False

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path, self.SCOPES
            )
            creds = flow.run_local_server(port=0)

            with open(self.token_path, "w", encoding="utf-8") as file:
                file.write(creds.to_json())

            self._credentials = creds
            self._service = build("tasks", "v1", credentials=creds)
            return True
        except Exception:
            logger.exception("Interactive Google OAuth authentication failed.")
            return False

    def get_service(self):
        if self._service is not None:
            return self._service

        if not self.authenticate():
            return None
        return self._service

