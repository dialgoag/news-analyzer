"""
Migration 006: Create reporting schema

Domain: Analytics & Reporting
Description: Tables for daily and weekly reports generated from news items and insights
Depends on: 005_news_items_schema
"""

from yoyo import step

steps = [
    step(
        # Daily reports
        """
        CREATE TABLE IF NOT EXISTS daily_reports (
            id SERIAL PRIMARY KEY,
            report_date DATE UNIQUE NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP
        )
        """,
        "DROP TABLE IF EXISTS daily_reports"
    ),
    step(
        "CREATE INDEX idx_daily_reports_date ON daily_reports(report_date)",
        "DROP INDEX IF EXISTS idx_daily_reports_date"
    ),
    step(
        # Weekly reports
        """
        CREATE TABLE IF NOT EXISTS weekly_reports (
            id SERIAL PRIMARY KEY,
            week_start DATE UNIQUE NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP
        )
        """,
        "DROP TABLE IF EXISTS weekly_reports"
    ),
    step(
        "CREATE INDEX idx_weekly_reports_week_start ON weekly_reports(week_start)",
        "DROP INDEX IF EXISTS idx_weekly_reports_week_start"
    ),
]
