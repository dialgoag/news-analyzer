"""
PostgreSQL implementation of UserRepository.
"""

from datetime import datetime
from typing import Dict, List, Optional

import bcrypt
import psycopg2

from core.ports.repositories.user_repository import UserRepository
from .base import BasePostgresRepository


class PostgresUserRepository(BasePostgresRepository, UserRepository):
    """Auth/user management adapter on users table."""

    VALID_ROLES = {"admin", "super_user", "user"}

    def authenticate_user_sync(self, username: str, password: str) -> Optional[Dict]:
        user = self._get_user_by_username_sync(username)
        if not user:
            return None
        if not self.verify_password_sync(password, user["password_hash"]):
            return None
        self._update_last_login_sync(int(user["id"]))
        return self.get_user_by_id_sync(int(user["id"]))

    def get_user_by_id_sync(self, user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, username, email, role, password_hash, created_at, last_login
                FROM users
                WHERE id = %s AND is_active = 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            return self._map_user_row(cursor, row)
        finally:
            self.release_connection(conn)

    def list_users_sync(self) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, username, email, role, created_at, last_login
                FROM users
                WHERE is_active = 1
                ORDER BY id ASC
                """
            )
            rows = cursor.fetchall()
            return [self._map_user_row(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)

    def create_user_sync(self, username: str, email: str, password: str, role: str) -> Optional[int]:
        if role not in self.VALID_ROLES:
            raise ValueError(f"Invalid role: {role}")

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            password_hash = self._hash_password(password)
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, role, created_at, is_active)
                VALUES (%s, %s, %s, %s, %s, 1)
                RETURNING id
                """,
                (username, email, password_hash, datetime.utcnow().isoformat()),
            )
            row = cursor.fetchone()
            conn.commit()
            return int(row[0]) if row else None
        except psycopg2.IntegrityError:
            conn.rollback()
            return None
        finally:
            self.release_connection(conn)

    def update_user_role_sync(self, user_id: int, new_role: str) -> bool:
        if new_role not in self.VALID_ROLES:
            raise ValueError(f"Invalid role: {new_role}")
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET role = %s
                WHERE id = %s AND is_active = 1
                """,
                (new_role, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.release_connection(conn)

    def delete_user_sync(self, user_id: int) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET is_active = 0
                WHERE id = %s AND is_active = 1
                """,
                (user_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.release_connection(conn)

    def verify_password_sync(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    def change_password_sync(self, user_id: int, new_password: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            password_hash = self._hash_password(new_password)
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE id = %s AND is_active = 1
                """,
                (password_hash, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.release_connection(conn)

    def _get_user_by_username_sync(self, username: str) -> Optional[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, username, email, role, password_hash, created_at, last_login
                FROM users
                WHERE username = %s AND is_active = 1
                """,
                (username,),
            )
            row = cursor.fetchone()
            return self._map_user_row(cursor, row)
        finally:
            self.release_connection(conn)

    def _update_last_login_sync(self, user_id: int) -> None:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET last_login = %s WHERE id = %s",
                (datetime.utcnow().isoformat(), user_id),
            )
            conn.commit()
        finally:
            self.release_connection(conn)

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def _to_iso(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _map_user_row(self, cursor, row) -> Optional[Dict]:
        data = self.map_row_to_dict(cursor, row)
        if not data:
            return None
        data["created_at"] = self._to_iso(data.get("created_at"))
        data["last_login"] = self._to_iso(data.get("last_login"))
        return data
