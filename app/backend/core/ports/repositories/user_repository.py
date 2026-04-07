"""
User repository port for auth/user management operations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class UserRepository(ABC):
    """Port for users persistence and authentication helpers."""

    @abstractmethod
    def authenticate_user_sync(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user dict when credentials are valid."""
        pass

    @abstractmethod
    def get_user_by_id_sync(self, user_id: int) -> Optional[Dict]:
        """Return active user by id."""
        pass

    @abstractmethod
    def list_users_sync(self) -> List[Dict]:
        """Return all active users."""
        pass

    @abstractmethod
    def create_user_sync(self, username: str, email: str, password: str, role: str) -> Optional[int]:
        """Create user and return its id (or None on duplicate/conflict)."""
        pass

    @abstractmethod
    def update_user_role_sync(self, user_id: int, new_role: str) -> bool:
        """Update user role."""
        pass

    @abstractmethod
    def delete_user_sync(self, user_id: int) -> bool:
        """Soft-delete user (set inactive)."""
        pass

    @abstractmethod
    def verify_password_sync(self, password: str, password_hash: str) -> bool:
        """Verify plain password against hashed password."""
        pass

    @abstractmethod
    def change_password_sync(self, user_id: int, new_password: str) -> bool:
        """Update user password hash."""
        pass
