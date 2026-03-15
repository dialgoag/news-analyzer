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
