"""
Migration 001: Create authentication schema (Users table)

Domain: Authentication & Security
Description: Core user management tables for authentication
"""

from yoyo import step

steps = [
    step(
        # Create users table
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role VARCHAR(50) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
        """,
        # Rollback
        "DROP TABLE IF EXISTS users"
    ),
    step(
        # Create index for username lookup
        "CREATE INDEX idx_users_username ON users(username)",
        "DROP INDEX IF EXISTS idx_users_username"
    ),
    step(
        # Create index for email lookup
        "CREATE INDEX idx_users_email ON users(email)",
        "DROP INDEX IF EXISTS idx_users_email"
    ),
]
