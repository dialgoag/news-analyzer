"""
Database setup and models for authentication system
"""

import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import bcrypt
import logging
import os

logger = logging.getLogger(__name__)

# Database path - use /app/data in Docker, ./data locally
# All tables are stored in a single database file
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://raguser:ragpassword@postgres:5432/rag_enterprise")
DB_CONNECTION_STRING = DATABASE_URL
MIGRATIONS_DIR = os.getenv("MIGRATIONS_DIR", "/app/migrations")


class UserRole:
    """User role definitions"""
    ADMIN = "admin"
    SUPER_USER = "super_user"
    USER = "user"

    @classmethod
    def all_roles(cls):
        return [cls.ADMIN, cls.SUPER_USER, cls.USER]


class UserDatabase:
    """User database management"""

    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url
        # PostgreSQL doesn't require directory creation
        self.init_db()

    def get_connection(self):
        """Create database connection"""
        conn = psycopg2.connect(self.db_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def init_db(self):
        """Initialize database and create default admin user
        
        Note: Schema is managed by migrations.py - this only ensures users table
        and creates default admin if needed.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create users table (critical for authentication)
        cursor.execute('''
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
        ''')
        
        conn.commit()
        
        # Create default admin user if needed
        try:
            admin_exists = cursor.execute(
                "SELECT id FROM users WHERE username = %s",
                ("admin",)
            ).fetchone()

            if not admin_exists:
                import secrets
                default_admin_password = os.getenv("ADMIN_DEFAULT_PASSWORD", "")

                if not default_admin_password:
                    default_admin_password = secrets.token_urlsafe(16)
                    logger.warning("=" * 70)
                    logger.warning("🔐 ADMIN ACCOUNT CREATED WITH RANDOM PASSWORD")
                    logger.warning("")
                    logger.warning(f"   Username: admin")
                    logger.warning(f"   Password: {default_admin_password}")
                    logger.warning("")
                    logger.warning("⚠️  SAVE THIS PASSWORD NOW - it won't be shown again!")
                    logger.warning("You can change it after login in the admin panel.")
                    logger.warning("")
                    logger.warning("To set a specific password, add to .env:")
                    logger.warning("   ADMIN_DEFAULT_PASSWORD=your-secure-password")
                    logger.warning("=" * 70)
                else:
                    logger.info("✅ Admin user created with password from ADMIN_DEFAULT_PASSWORD")

                self.create_user(
                    username="admin",
                    email="admin@rag-enterprise.local",
                    password=default_admin_password,
                    role=UserRole.ADMIN
                )
        except Exception as e:
            logger.error(f"Error creating admin: {e}")

        conn.close()

    def hash_password(self, password: str) -> str:
        """Hash password with bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8')
        )

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str
    ) -> Optional[int]:
        """Create new user"""
        if role not in UserRole.all_roles():
            raise ValueError(f"Invalid role: {role}")

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            password_hash = self.hash_password(password)
            cursor.execute(
                '''INSERT INTO users
                   (username, email, password_hash, role, created_at)
                   VALUES (%s, %s, %s, %s, %s)''',
                (username, email, password_hash, role, datetime.utcnow().isoformat())
            )
            conn.commit()
            user_id = cursor.lastrowid
            logger.info(f"✅ User created: {username} (role: {role})")
            return user_id
        except psycopg2.IntegrityError as e:
            logger.error(f"❌ User creation error: {e}")
            return None
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Retrieve user by username"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username = %s AND is_active = 1",
            (username,)
        )
        row = cursor.fetchone()

        conn.close()

        if row:
            return dict(row)
        return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Retrieve user by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE id = %s AND is_active = 1",
            (user_id,)
        )
        row = cursor.fetchone()

        conn.close()

        if row:
            return dict(row)
        return None

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user"""
        user = self.get_user_by_username(username)

        if not user:
            return None

        if not self.verify_password(password, user['password_hash']):
            return None

        # Update last_login
        self.update_last_login(user['id'])

        return user

    def update_last_login(self, user_id: int):
        """Update last login timestamp"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET last_login = %s WHERE id = %s",
            (datetime.utcnow().isoformat(), user_id)
        )
        conn.commit()
        conn.close()

    def list_users(self) -> List[Dict]:
        """List all active users"""
        conn = self.get_connection()
        cursor = conn.cursor()

        rows = cursor.execute(
            "SELECT id, username, email, role, created_at, last_login FROM users WHERE is_active = 1"
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def update_user_role(self, user_id: int, new_role: str) -> bool:
        """Update user role"""
        if new_role not in UserRole.all_roles():
            raise ValueError(f"Invalid role: {new_role}")

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET role = %s WHERE id = %s",
            (new_role, user_id)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0

    def delete_user(self, user_id: int) -> bool:
        """Disable user (soft delete)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET is_active = 0 WHERE id = %s",
            (user_id,)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0

    def change_password(self, user_id: int, new_password: str) -> bool:
        """Change user password"""
        password_hash = self.hash_password(new_password)

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (password_hash, user_id)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0


class DocumentStatusStore:
    """Stores document processing status for dashboard (pending / processing / indexed / error)."""

    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url

    def get_connection(self):
        conn = psycopg2.connect(self.db_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def insert(
        self,
        document_id: str,
        filename: str,
        source: str,
        status: str = "processing",
        news_date: Optional[str] = None,
        file_hash: Optional[str] = None,
    ) -> bool:
        """Insert a new document record. source: 'upload' | 'inbox'. news_date: YYYY-MM-DD (optional). file_hash: SHA256 hash."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO document_status
                   (document_id, filename, source, status, ingested_at, news_date, file_hash)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    document_id,
                    filename,
                    source,
                    status,
                    datetime.utcnow().isoformat(),
                    news_date,
                    file_hash,
                ),
            )
            conn.commit()
            return True
        except psycopg2.IntegrityError:
            # document_id already exists (e.g. retry)
            conn.rollback()
            return False
        finally:
            conn.close()

    def update_status(
        self,
        document_id: str,
        status: str,
        indexed_at: Optional[str] = None,
        error_message: Optional[str] = None,
        num_chunks: Optional[int] = None,
        news_date: Optional[str] = None,
        processing_stage: Optional[str] = None,
    ) -> bool:
        """Update status for a document. processing_stage: 'ocr' | 'chunking' | 'indexing' (solo si status=processing)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            updates = ["status = %s"]
            args = [status]
            if indexed_at is not None:
                updates.append("indexed_at = %s")
                args.append(indexed_at)
            if error_message is not None:
                updates.append("error_message = %s")
                args.append(error_message)
            if num_chunks is not None:
                updates.append("num_chunks = %s")
                args.append(num_chunks)
            if news_date is not None:
                updates.append("news_date = %s")
                args.append(news_date)
            if processing_stage is not None:
                updates.append("processing_stage = %s")
                args.append(processing_stage)
            args.append(document_id)
            cursor.execute(
                f"UPDATE document_status SET {', '.join(updates)} WHERE document_id = %s",
                args,
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def store_ocr_text(self, document_id: str, ocr_text: str) -> bool:
        """Store the full OCR text for a document (for diagnostic purposes)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE document_status SET ocr_text = %s WHERE document_id = %s",
                (ocr_text, document_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def mark_for_reprocessing(self, document_id: str, requested: bool = True) -> bool:
        """Mark a document for reprocessing (persists across app restarts)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE document_status SET reprocess_requested = %s WHERE document_id = %s",
                (1 if requested else 0, document_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_documents_pending_reprocess(self) -> List[Dict]:
        """Get all documents marked for reprocessing."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM document_status WHERE reprocess_requested = 1 ORDER BY ingested_at DESC"
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def find_by_hash(self, file_hash: str) -> Optional[Dict]:
        """Find a document by its file hash (SHA256)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM document_status WHERE file_hash = %s LIMIT 1",
                (file_hash,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all(
        self,
        status_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
    ) -> List[Dict]:
        """List all documents, optionally filtered by status or source."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            query = "SELECT * FROM document_status WHERE 1=1"
            args = []
            if status_filter:
                query += " AND status = %s"
                args.append(status_filter)
            if source_filter:
                query += " AND source = %s"
                args.append(source_filter)
            query += " ORDER BY ingested_at DESC"
            cursor.execute(query, args)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_by_document_id(self, document_id: str) -> Optional[Dict]:
        """Get a single document by document_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            row = cursor.execute(
                "SELECT * FROM document_status WHERE document_id = %s",
                (document_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get(self, document_id: str) -> Optional[Dict]:
        """Alias for get_by_document_id."""
        return self.get_by_document_id(document_id)

    def get_document_ids_by_news_date(self, report_date: str) -> List[str]:
        """Return document_ids with status indexing_done+ and news_date = report_date."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT document_id FROM document_status WHERE status IN (%s, %s, %s, %s, %s) AND news_date = %s",
                ("indexing_done", "insights_pending", "insights_processing", "insights_done", "completed", report_date),
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_document_ids_by_news_date_range(self, start_date: str, end_date: str) -> List[str]:
        """Return document_ids with status indexing_done+ and news_date in range."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT document_id FROM document_status WHERE status IN (%s, %s, %s, %s, %s) AND news_date >= %s AND news_date <= %s",
                ("indexing_done", "insights_pending", "insights_processing", "insights_done", "completed", start_date, end_date),
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete(self, document_id: str) -> bool:
        """Remove document from status table (e.g. when deleted from index)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM document_status WHERE document_id = %s", (document_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_pending_documents(self, limit: int = 2) -> List[tuple]:
        """Get next documents in 'processing' status for OCR queue (oldest first).
        
        Returns list of tuples: (document_id, file_path, filename)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Construct file path based on UPLOAD_DIR (assuming documents are in uploads dir)
            import os
            from pathlib import Path
            
            cursor.execute(
                """SELECT document_id, filename, ingested_at FROM document_status
                   WHERE status = 'processing' ORDER BY ingested_at ASC LIMIT %s""",
                (limit,),
            )
            rows = cursor.fetchall()
            
            # Build full file paths
            result = []
            UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
            for row in rows:
                doc_id = row["document_id"]
                filename = row["filename"]
                file_path = os.path.join(UPLOAD_DIR, doc_id)
                result.append((doc_id, file_path, filename))
            
            return result
        finally:
            conn.close()

    def get_recovery_queue(self) -> List[Dict]:
        """Get documents that need recovery (incomplete processing).
        
        Returns list of dicts with: {document_id, filename, last_completed_step, next_step}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Find documents that are stuck in 'processing' status
            cursor.execute("""
                SELECT document_id, filename, status, indexed_at
                FROM document_status
                WHERE status IN ('processing', 'queued')
                AND ingested_at < NOW() - INTERVAL '5 minutes'
                ORDER BY ingested_at ASC
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


class ProcessingQueueStore:
    """Manages processing queue and worker task assignments."""
    
    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url
    
    def get_connection(self):
        conn = psycopg2.connect(self.db_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    
    def enqueue_task(self, document_id: str, filename: str, task_type: str, priority: int = 0) -> bool:
        """Add a task to the processing queue."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO processing_queue 
                (document_id, filename, task_type, priority, created_at, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, task_type) 
                DO UPDATE SET priority = EXCLUDED.priority, status = EXCLUDED.status
            """, (document_id, filename, task_type, priority, datetime.utcnow().isoformat(), 'pending'))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error enqueueing task: {e}")
            return False
        finally:
            conn.close()
    
    def get_pending_task(self, task_type: str = None) -> Optional[Dict]:
        """Get next pending task from queue."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if task_type:
                cursor.execute("""
                    SELECT * FROM processing_queue
                    WHERE status = 'pending' AND task_type = %s
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                """, (task_type,))
            else:
                cursor.execute("""
                    SELECT * FROM processing_queue
                    WHERE status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                """)
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def mark_task_completed(self, document_id: str, task_type: str) -> bool:
        """Mark a task as completed."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE processing_queue
                SET status = 'completed', processed_at = %s
                WHERE document_id = %s AND task_type = %s
            """, (datetime.utcnow().isoformat(), document_id, task_type))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def assign_worker(self, worker_id: str, worker_type: str, document_id: str, task_type: str) -> bool:
        """
        Assign a task to a worker. Prevents duplicate assignment using atomic database operations.
        
        Uses SELECT FOR UPDATE to lock the row and prevent race conditions between schedulers.
        Returns True if assignment succeeded, False if document already has an active worker.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Use SELECT FOR UPDATE to lock and check atomically
            # This prevents race conditions when multiple schedulers run simultaneously
            cursor.execute("""
                SELECT worker_id FROM worker_tasks
                WHERE document_id = %s AND task_type = %s AND status IN ('assigned', 'started')
                FOR UPDATE
                LIMIT 1
            """, (document_id, task_type))
            
            existing_worker = cursor.fetchone()
            if existing_worker:
                # Document already has an active worker - don't reassign
                conn.rollback()
                return False
            
            # Safe to assign this document to the worker (atomic INSERT)
            cursor.execute("""
                INSERT INTO worker_tasks
                (worker_id, worker_type, document_id, task_type, status, assigned_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (worker_id, worker_type, document_id, task_type, 'assigned', datetime.utcnow().isoformat()))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error assigning worker {worker_id} to {document_id}: {e}")
            return False
        finally:
            conn.close()
    
    def update_worker_status(self, worker_id: str, document_id: str, task_type: str, status: str, error_message: str = None) -> bool:
        """Update worker task status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.utcnow().isoformat()
            if status == 'started':
                cursor.execute("""
                    UPDATE worker_tasks
                    SET status = %s, started_at = %s
                    WHERE worker_id = %s AND document_id = %s AND task_type = %s
                """, (status, now, worker_id, document_id, task_type))
            elif status == 'completed':
                cursor.execute("""
                    UPDATE worker_tasks
                    SET status = %s, completed_at = %s
                    WHERE worker_id = %s AND document_id = %s AND task_type = %s
                """, (status, now, worker_id, document_id, task_type))
            elif status == 'error':
                cursor.execute("""
                    UPDATE worker_tasks
                    SET status = %s, completed_at = %s, error_message = %s
                    WHERE worker_id = %s AND document_id = %s AND task_type = %s
                """, (status, now, error_message, worker_id, document_id, task_type))
            else:
                cursor.execute("""
                    UPDATE worker_tasks
                    SET status = %s
                    WHERE worker_id = %s AND document_id = %s AND task_type = %s
                """, (status, worker_id, document_id, task_type))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_free_worker_slot(self) -> bool:
        """Check if there's a free worker slot available."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*) as active
                FROM worker_tasks
                WHERE status IN ('assigned', 'started')
            """)
            active_count = cursor.fetchone()['active']
            # Can be adjusted based on actual worker count
            return active_count < 4  # Max 4 concurrent workers
        finally:
            conn.close()

class DailyReportStore:
    """Stores generated daily reports (report_date, content markdown)."""

    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url

    def get_connection(self):
        conn = psycopg2.connect(self.db_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def insert(self, report_date: str, content: str) -> bool:
        """Insert or replace report for a date. report_date: YYYY-MM-DD. Sets updated_at on replace."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """INSERT INTO daily_reports (report_date, content, created_at, updated_at)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT(report_date) DO UPDATE SET
                     content = excluded.content,
                     updated_at = %s""",
                (report_date, content, now, now, now),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_by_date(self, report_date: str) -> Optional[Dict]:
        """Get report by date (YYYY-MM-DD)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT report_date, content, created_at, updated_at FROM daily_reports WHERE report_date = %s",
                (report_date,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all(self, limit: int = 100) -> List[Dict]:
        """List all reports, newest first."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT report_date, content, created_at, updated_at FROM daily_reports ORDER BY report_date DESC LIMIT %s",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


class WeeklyReportStore:
    """Stores generated weekly reports (week_start = Monday YYYY-MM-DD, content markdown)."""

    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url

    def get_connection(self):
        conn = psycopg2.connect(self.db_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def insert(self, week_start: str, content: str) -> bool:
        """Insert or replace report for a week. week_start: Monday YYYY-MM-DD. Sets updated_at on replace."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """INSERT INTO weekly_reports (week_start, content, created_at, updated_at)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT(week_start) DO UPDATE SET
                     content = excluded.content,
                     updated_at = %s""",
                (week_start, content, now, now, now),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_by_week_start(self, week_start: str) -> Optional[Dict]:
        """Get report by week_start (Monday YYYY-MM-DD)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT week_start, content, created_at, updated_at FROM weekly_reports WHERE week_start = %s",
                (week_start,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all(self, limit: int = 52) -> List[Dict]:
        """List all reports, newest first (limit 52 = ~1 year)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT week_start, content, created_at, updated_at FROM weekly_reports ORDER BY week_start DESC LIMIT %s",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


class NotificationStore:
    """Stores in-app notifications when reports are updated. Read state per user."""

    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url

    def get_connection(self):
        conn = psycopg2.connect(self.db_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def insert(self, report_kind: str, report_date: str, message: Optional[str] = None) -> Optional[int]:
        """Insert a notification (report_kind: 'daily' | 'weekly', report_date: YYYY-MM-DD). Returns notification id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """INSERT INTO notifications (report_kind, report_date, message, created_at)
                   VALUES (%s, %s, %s, %s)""",
                (report_kind, report_date, message or "", now),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_all_for_user(self, user_id: int, limit: int = 50) -> List[Dict]:
        """List notifications for user with read flag. Newest first."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT n.id, n.report_kind, n.report_date, n.message, n.created_at,
                          nr.read_at IS NOT NULL AS read
                   FROM notifications n
                   LEFT JOIN notification_reads nr ON nr.notification_id = n.id AND nr.user_id = %s
                   ORDER BY n.created_at DESC LIMIT %s""",
                (user_id, limit),
            )
            results = []
            for row in cursor.fetchall():
                report_date = row["report_date"]
                if isinstance(report_date, datetime):
                    report_date = report_date.isoformat()
                
                created_at = row["created_at"]
                if isinstance(created_at, datetime):
                    created_at = created_at.isoformat()
                
                results.append({
                    "id": row["id"],
                    "report_kind": row["report_kind"],
                    "report_date": report_date,
                    "message": row["message"] or None,
                    "created_at": created_at,
                    "read": bool(row["read"]),
                })
            return results
        finally:
            conn.close()

    def get_unread_count(self, user_id: int) -> int:
        """Count unread notifications for user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT COUNT(*) as count FROM notifications n
                   WHERE NOT EXISTS (
                     SELECT 1 FROM notification_reads nr
                     WHERE nr.notification_id = n.id AND nr.user_id = %s
                   )""",
                (user_id,),
            )
            result = cursor.fetchone()
            return result['count'] if result else 0
        finally:
            conn.close()

    def mark_read(self, notification_id: int, user_id: int) -> bool:
        """Mark one notification as read for user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO notification_reads (notification_id, user_id, read_at)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (notification_id, user_id) DO NOTHING""",
                (notification_id, user_id, datetime.utcnow().isoformat()),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def mark_all_read(self, user_id: int) -> int:
        """Mark all notifications as read for user. Returns number of newly marked."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """INSERT INTO notification_reads (notification_id, user_id, read_at)
                   SELECT n.id, %s, %s FROM notifications n
                   WHERE NOT EXISTS (
                     SELECT 1 FROM notification_reads nr
                     WHERE nr.notification_id = n.id AND nr.user_id = %s
                   )
                   ON CONFLICT (notification_id, user_id) DO NOTHING""",
                (user_id, now, user_id),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


class DocumentInsightsStore:
    """Reporte/insights por archivo generado por LLM. Cola: pending → queued → generating → done | error."""

    STATUS_PENDING = "pending"
    STATUS_QUEUED = "queued"
    STATUS_GENERATING = "generating"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"

    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url

    def get_connection(self):
        conn = psycopg2.connect(self.db_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def enqueue(self, document_id: str, filename: str, content_hash: Optional[str] = None) -> bool:
        """Enqueue a document for insights generation. Idempotent: if already exists, no-op.

        content_hash: hash del contenido original del archivo (por ejemplo SHA-256 de los bytes).
        Se usa para deduplicar insights entre documentos con el mismo contenido.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """INSERT INTO document_insights (document_id, filename, status, created_at, content_hash)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (document_id) DO NOTHING""",
                (document_id, filename, self.STATUS_PENDING, now, content_hash),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_next_pending(self, limit: int = 1) -> List[Dict]:
        """Get next documents to process (pending, queued, or generating), oldest first.
        
        Includes STATUS_GENERATING to recover items that were interrupted mid-processing.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT document_id, filename, status, created_at FROM document_insights
                   WHERE status IN (%s, %s, %s) ORDER BY created_at ASC LIMIT %s""",
                (self.STATUS_PENDING, self.STATUS_QUEUED, self.STATUS_GENERATING, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def set_status(self, document_id: str, status: str, content: Optional[str] = None, error_message: Optional[str] = None) -> bool:
        """Update status (generating, done, error). Optionally set content or error_message."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.utcnow().isoformat()
            updates = ["status = %s", "updated_at = %s"]
            args = [status, now]
            if content is not None:
                updates.append("content = %s")
                args.append(content)
            if error_message is not None:
                updates.append("error_message = %s")
                args.append(error_message)
            args.append(document_id)
            cursor.execute(
                f"UPDATE document_insights SET {', '.join(updates)} WHERE document_id = %s",
                args,
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_by_document_id(self, document_id: str) -> Optional[Dict]:
        """Get insights row for a document."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            row = cursor.execute(
                "SELECT document_id, filename, status, content, error_message, created_at, updated_at FROM document_insights WHERE document_id = %s",
                (document_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_status_by_document_ids(self, document_ids: List[str]) -> Dict[str, Dict]:
        """Return map document_id -> {status, progress} for dashboard. progress e.g. '1/1' if done else '0/1'."""
        if not document_ids:
            return {}
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            placeholders = ",".join(["%s"] * len(document_ids))
            cursor.execute(
                f"SELECT document_id, status FROM document_insights WHERE document_id IN ({placeholders})",
                tuple(document_ids),
            )
            rows = cursor.fetchall()
            out = {}
            for row in rows:
                doc_id = row["document_id"]
                st = row["status"]
                out[doc_id] = {
                    "status": st,
                    "progress": "1/1" if st == self.STATUS_DONE else ("0/1" if st == self.STATUS_ERROR else "0/1"),
                }
            return out
        finally:
            conn.close()

    def get_done_by_content_hash(self, content_hash: str) -> Optional[Dict]:
        """Return one DONE insights row that matches the given content_hash, if any."""
        if not content_hash:
            return None
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            row = cursor.execute(
                """SELECT document_id, filename, status, content, error_message, created_at, updated_at
                   FROM document_insights
                   WHERE content_hash = %s AND status = %s
                   ORDER BY updated_at DESC NULLS LAST, created_at DESC
                   LIMIT 1""",
                (content_hash, self.STATUS_DONE),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete(self, document_id: str) -> bool:
        """Remove insights row when document is deleted."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM document_insights WHERE document_id = %s", (document_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


class NewsItemStore:
    """Una fila por noticia dentro de un PDF (news_item_id = document_id::idx)."""

    STATUS_PENDING = "pending"
    STATUS_INDEXED = "indexing_done"
    STATUS_ERROR = "error"

    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url

    def get_connection(self):
        conn = psycopg2.connect(self.db_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def upsert_items(self, document_id: str, filename: str, items: List[Dict]) -> int:
        """Insert/replace news items for a document. Returns number of rows written."""
        if not items:
            return 0
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.utcnow().isoformat()
            rows = 0
            for it in items:
                cursor.execute(
                    """INSERT INTO news_items (news_item_id, document_id, filename, item_index, title, status, text_hash, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT(news_item_id) DO UPDATE SET
                         title = excluded.title,
                         status = excluded.status,
                         text_hash = excluded.text_hash,
                         updated_at = excluded.updated_at""",
                    (
                        it["news_item_id"],
                        document_id,
                        filename,
                        int(it.get("item_index", 0)),
                        it.get("title") or None,
                        it.get("status") or self.STATUS_PENDING,
                        it.get("text_hash") or None,
                        now,
                        now,
                    ),
                )
                rows += 1
            conn.commit()
            return rows
        finally:
            conn.close()

    def list_by_document_id(self, document_id: str, limit: int = 500) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT news_item_id, document_id, filename, item_index, title, status, text_hash, created_at, updated_at
                   FROM news_items WHERE document_id = %s ORDER BY item_index ASC LIMIT %s""",
                (document_id, limit),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_counts_by_document_ids(self, document_ids: List[str]) -> Dict[str, int]:
        """Return {document_id: total_items}."""
        if not document_ids:
            return {}
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            placeholders = ",".join(["%s"] * len(document_ids))
            cursor.execute(
                f"""SELECT document_id, COUNT(*) as cnt FROM news_items
                    WHERE document_id IN ({placeholders})
                    GROUP BY document_id""",
                tuple(document_ids),
            )
            return {row["document_id"]: int(row["cnt"]) for row in cursor.fetchall()}
        finally:
            conn.close()

    def delete_by_document_id(self, document_id: str) -> int:
        """Delete all news_items rows for a document. Returns number of deleted rows."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM news_items WHERE document_id = %s", (document_id,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


class NewsItemInsightsStore:
    """Insights por noticia (news_item_id), con cola y deduplicación por text_hash."""

    STATUS_PENDING = "pending"
    STATUS_QUEUED = "queued"
    STATUS_GENERATING = "generating"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"

    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url

    def get_connection(self):
        conn = psycopg2.connect(self.db_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def enqueue(
        self,
        news_item_id: str,
        document_id: str,
        filename: str,
        item_index: int,
        title: Optional[str] = None,
        text_hash: Optional[str] = None,
    ) -> bool:
        """Enqueue an item for insights generation. Idempotent via PK."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """INSERT INTO news_item_insights
                   (news_item_id, document_id, filename, item_index, title, status, text_hash, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (news_item_id) DO NOTHING""",
                (
                    news_item_id,
                    document_id,
                    filename,
                    int(item_index),
                    title or None,
                    self.STATUS_PENDING,
                    text_hash or None,
                    now,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_next_pending(self, limit: int = 1) -> List[Dict]:
        """Get next items to process (pending, queued, or generating), oldest first.
        
        Includes STATUS_GENERATING to recover items that were interrupted mid-processing.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT news_item_id, document_id, filename, item_index, title, status, text_hash, created_at
                   FROM news_item_insights
                   WHERE status IN (%s, %s, %s)
                   ORDER BY created_at ASC
                   LIMIT %s""",
                (self.STATUS_PENDING, self.STATUS_QUEUED, self.STATUS_GENERATING, limit),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def set_status(
        self,
        news_item_id: str,
        status: str,
        content: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.utcnow().isoformat()
            updates = ["status = %s", "updated_at = %s"]
            args = [status, now]
            if content is not None:
                updates.append("content = %s")
                args.append(content)
            if error_message is not None:
                updates.append("error_message = %s")
                args.append(error_message)
            args.append(news_item_id)
            cursor.execute(
                f"UPDATE news_item_insights SET {', '.join(updates)} WHERE news_item_id = %s",
                args,
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_by_news_item_id(self, news_item_id: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            row = cursor.execute(
                """SELECT news_item_id, document_id, filename, item_index, title, status, content, error_message,
                          text_hash, created_at, updated_at
                   FROM news_item_insights WHERE news_item_id = %s""",
                (news_item_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_by_document_id(self, document_id: str, limit: int = 500) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT news_item_id, document_id, filename, item_index, title, status, error_message, created_at, updated_at
                   FROM news_item_insights WHERE document_id = %s ORDER BY item_index ASC LIMIT %s""",
                (document_id, limit),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_done_by_text_hash(self, text_hash: str) -> Optional[Dict]:
        """Return one DONE insights row that matches text_hash, if any."""
        if not text_hash:
            return None
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT news_item_id, content, updated_at, created_at
                   FROM news_item_insights
                   WHERE text_hash = %s AND status = %s
                   ORDER BY updated_at DESC NULLS LAST, created_at DESC
                   LIMIT 1""",
                (text_hash, self.STATUS_DONE),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_progress_by_document_ids(self, document_ids: List[str]) -> Dict[str, Dict[str, int]]:
        """Return {document_id: {total, done, generating, pending, queued, error}} for dashboard aggregation."""
        if not document_ids:
            return {}
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            placeholders = ",".join(["%s"] * len(document_ids))
            cursor.execute(
                f"""SELECT document_id, status, COUNT(*) as cnt
                    FROM news_item_insights
                    WHERE document_id IN ({placeholders})
                    GROUP BY document_id, status""",
                tuple(document_ids),
            )
            out: Dict[str, Dict[str, int]] = {}
            for row in cursor.fetchall():
                doc_id = row["document_id"]
                st = row["status"]
                cnt = int(row["cnt"])
                if doc_id not in out:
                    out[doc_id] = {"total": 0, "done": 0, "generating": 0, "pending": 0, "queued": 0, "error": 0}
                out[doc_id][st] = cnt
                out[doc_id]["total"] += cnt
            return out
        finally:
            conn.close()

    def delete_by_document_id(self, document_id: str) -> int:
        """Delete all insights rows for a document. Returns number of deleted rows."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM news_item_insights WHERE document_id = %s", (document_id,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


# Run migrations BEFORE initializing any database stores
# This is critical - application CANNOT start if migrations fail
try:
    from migration_runner import run_migrations
    logger.info("🔐 STARTING MIGRATION SYSTEM - Blocking until complete")
    
    if not run_migrations():
        logger.critical("❌ BLOCKING: Migrations failed - application cannot initialize!")
        import sys
        sys.exit(1)
    
    logger.info("✅ Migrations completed successfully - proceeding with app initialization")

except ImportError:
    # migration_runner not available - skip migrations (backward compatibility)
    logger.warning("⚠️  migration_runner not found, skipping Yoyo migrations")
    logger.info("✅ Proceeding without migrations (legacy mode)")
    
except Exception as e:
    logger.critical(f"❌ BLOCKING: Migration system error: {e}")
    import traceback
    logger.critical(traceback.format_exc())
    import sys
    sys.exit(1)

# Global instance - only initialized after migrations succeed
logger.info("🚀 Initializing database stores...")
db = UserDatabase()
document_status_store = DocumentStatusStore()
daily_report_store = DailyReportStore()
weekly_report_store = WeeklyReportStore()
notification_store = NotificationStore()
document_insights_store = DocumentInsightsStore()
news_item_store = NewsItemStore()
news_item_insights_store = NewsItemInsightsStore()
logger.info("✅ Database stores initialized successfully")
