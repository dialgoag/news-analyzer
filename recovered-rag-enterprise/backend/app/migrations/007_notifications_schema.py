"""
Migration 007: Create notifications schema

Domain: User Notifications & System Events
Description: Tables for in-app notifications when reports are updated
Depends on: 001_authentication_schema, 006_reporting_schema
"""

from yoyo import step

steps = [
    step(
        # Notifications table
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            report_kind VARCHAR(50) NOT NULL,
            report_date DATE NOT NULL,
            message TEXT,
            created_at TIMESTAMP NOT NULL
        )
        """,
        "DROP TABLE IF EXISTS notifications"
    ),
    step(
        "CREATE INDEX idx_notifications_created ON notifications(created_at DESC)",
        "DROP INDEX IF EXISTS idx_notifications_created"
    ),
    step(
        # Notification reads - track which user read which notification
        """
        CREATE TABLE IF NOT EXISTS notification_reads (
            notification_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            read_at TIMESTAMP NOT NULL,
            PRIMARY KEY (notification_id, user_id),
            FOREIGN KEY (notification_id) REFERENCES notifications(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        "DROP TABLE IF EXISTS notification_reads"
    ),
    step(
        "CREATE INDEX idx_notification_reads_user ON notification_reads(user_id)",
        "DROP INDEX IF EXISTS idx_notification_reads_user"
    ),
]
