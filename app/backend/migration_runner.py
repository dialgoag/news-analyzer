"""
Migration runner using Yoyo Python API
Ensures database is fully migrated before app initialization
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# PostgreSQL connection string (not SQLite!)
DB_HOST = os.getenv("DATABASE_HOST", os.getenv("POSTGRES_HOST", "postgres"))
DB_PORT = os.getenv("DATABASE_PORT", os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("DATABASE_NAME", os.getenv("POSTGRES_DB", "rag_enterprise"))
DB_USER = os.getenv("DATABASE_USER", os.getenv("POSTGRES_USER", "raguser"))
DB_PASSWORD = os.getenv("DATABASE_PASSWORD", os.getenv("POSTGRES_PASSWORD", "ragpassword"))

DB_CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
MIGRATIONS_DIR = os.getenv("MIGRATIONS_DIR", "/app/migrations")


def _patch_yoyo_for_idempotent_schema():
    """
    Patch yoyo backend to avoid PostgreSQL log errors on startup:
    - yoyo_lock: use CREATE TABLE IF NOT EXISTS (avoids "relation already exists")
    - yoyo_tmp_*: use DROP TABLE IF EXISTS (avoids "table does not exist" after rollback)
    """
    from yoyo.backends import base as yoyo_base
    from yoyo import utils

    def patched_create_lock_table(self):
        create_sql = (
            "CREATE TABLE IF NOT EXISTS {0.lock_table_quoted} ("
            "{quoted.locked} INT DEFAULT 1, "
            "{quoted.ctime} TIMESTAMP,"
            "{quoted.pid} INT NOT NULL,"
            "PRIMARY KEY ({quoted.locked}))"
        )
        try:
            with self.transaction():
                self.execute(self.format_sql(create_sql))
        except self.DatabaseError:
            pass

    def patched_check_transactional_ddl(self):
        table_name = "yoyo_tmp_{}".format(utils.get_random_string(10))
        table_name_quoted = self.quote_identifier(table_name)
        sql = self.format_sql(
            self.create_test_table_sql, table_name_quoted=table_name_quoted
        )
        try:
            with self.transaction(rollback_on_exit=True):
                self.execute(sql)
        except self.DatabaseError:
            return False
        try:
            with self.transaction():
                self.execute(f"DROP TABLE IF EXISTS {table_name_quoted}")
        except self.DatabaseError:
            return True
        return False

    yoyo_base.DatabaseBackend.create_lock_table = patched_create_lock_table
    yoyo_base.DatabaseBackend._check_transactional_ddl = patched_check_transactional_ddl


def run_migrations():
    """
    Run all pending migrations using Yoyo Python API.
    Blocks until all migrations complete successfully.
    Returns True if successful, False otherwise.
    """
    
    logger.info("=" * 80)
    logger.info("🔧 DATABASE MIGRATION SYSTEM (Yoyo-based)")
    logger.info("=" * 80)
    
    try:
        from yoyo import get_backend, read_migrations
    except ImportError as e:
        logger.critical(f"❌ yoyo-migrations not installed: {e}")
        return False

    _patch_yoyo_for_idempotent_schema()

    try:
        # Ensure migrations directory exists
        os.makedirs(MIGRATIONS_DIR, exist_ok=True)
        
        logger.info(f"📁 Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        logger.info(f"📁 Migrations path: {MIGRATIONS_DIR}")
        
        # Get Yoyo backend
        backend = get_backend(DB_CONNECTION_STRING)
        
        # Read migrations from directory
        migrations_path = Path(MIGRATIONS_DIR)
        if not migrations_path.exists():
            logger.warning(f"⚠️ Migrations directory not found: {MIGRATIONS_DIR}")
            return True
        
        # Get migration files
        migration_files = sorted([f for f in migrations_path.glob("*.py") if f.name != "__init__.py"])
        if not migration_files:
            logger.warning(f"⚠️ No migration files found in {MIGRATIONS_DIR}")
            return True
        
        logger.info(f"📋 Found {len(migration_files)} migration files:")
        for mf in migration_files:
            logger.info(f"   - {mf.name}")
        
        # Read and apply migrations
        logger.info("🚀 Applying migrations...")
        try:
            migrations = read_migrations(str(MIGRATIONS_DIR))
            logger.info(f"📋 Total migrations: {len(migrations)}")
            
            # Apply migrations (Yoyo handles checking what's already applied)
            with backend.lock():
                applied = backend.apply_migrations(backend.to_apply(migrations))
                
                if applied:
                    logger.info(f"✅ Applied {len(applied)} migrations:")
                    for migration in applied:
                        logger.info(f"   ✓ {migration.id}")
                else:
                    logger.info("✓ All migrations already applied")
            
            logger.info("=" * 80)
            logger.info("✅ MIGRATIONS COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            return True
            
        except Exception as e:
            logger.error(f"❌ Error applying migrations: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
    except Exception as e:
        logger.critical(f"❌ Migration system error: {e}")
        import traceback
        logger.critical(traceback.format_exc())
        return False
