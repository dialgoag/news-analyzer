"""
Authentication schemas - Pydantic models for auth endpoints

These models are imported from auth_models.py (legacy location).
Future: migrate to this module for consistency.
"""
from auth_models import (
    LoginRequest,
    LoginResponse,
    UserInfo,
    UserCreate,
    UserUpdate,
    PasswordChange,
    UserListResponse,
    MessageResponse,
)

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "UserInfo",
    "UserCreate",
    "UserUpdate",
    "PasswordChange",
    "UserListResponse",
    "MessageResponse",
]
