"""Custom exceptions for authentication flows."""

from __future__ import annotations


class AuthRequiredError(Exception):
    """Raised when stored credentials are invalid and interactive re-authentication is needed."""

    def __init__(self, message: str = "トークンの期限切れのため再認証が必要です"):
        super().__init__(message)
