"""
Migration 020: Add retry_count to news_items table

Purpose:
- Track number of failed attempts for each insight
- Prevent infinite retry loops for insights with insufficient context
- Allow configurable MAX_RETRIES limit

Date: 2026-04-07
"""

def up(conn):
    """Add retry_count column to news_items table."""
    cursor = conn.cursor()
    
    # Add retry_count column (default 0)
    cursor.execute("""
        ALTER TABLE news_items
        ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0 NOT NULL;
    """)
    
    # Create index for efficient queries on error status + retry_count
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_items_status_retry
        ON news_items(status, retry_count)
        WHERE status = 'insights_error';
    """)
    
    conn.commit()
    print("✅ Migration 020: Added retry_count column and index to news_items")


def down(conn):
    """Remove retry_count column from news_items table."""
    cursor = conn.cursor()
    
    # Drop index
    cursor.execute("""
        DROP INDEX IF EXISTS idx_news_items_status_retry;
    """)
    
    # Drop column
    cursor.execute("""
        ALTER TABLE news_items
        DROP COLUMN IF EXISTS retry_count;
    """)
    
    conn.commit()
    print("✅ Migration 020 (down): Removed retry_count column from news_items")


if __name__ == "__main__":
    import psycopg2
    import os
    
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rag_user:rag_password@postgres:5432/news_analyzer_db")
    conn = psycopg2.connect(DATABASE_URL)
    
    try:
        up(conn)
        print("Migration 020 applied successfully")
    except Exception as e:
        print(f"Error applying migration: {e}")
        conn.rollback()
    finally:
        conn.close()
