"""
Base PostgreSQL Repository - Common functionality for all repositories.

Provides:
- Connection pooling
- Status mapping (DB str <-> Domain PipelineStatus)
- Common database operations
"""

import logging
import psycopg2
from psycopg2 import pool
from typing import Optional, Dict, Any
from datetime import datetime
import os
import threading

from core.domain.value_objects.pipeline_status import (
    PipelineStatus,
    StageEnum,
    StateEnum,
    TerminalStateEnum,
    InsightStatusEnum,
    WorkerStatusEnum
)


class BasePostgresRepository:
    """
    Base class for PostgreSQL repositories.
    
    Provides:
    - Connection pooling (lazy initialization)
    - Status mapping helpers
    - Common query patterns
    """
    
    _connection_pool: Optional[pool.ThreadedConnectionPool] = None
    _pool_lock = threading.Lock()
    _logger = logging.getLogger(__name__)
    
    @classmethod
    def get_connection_pool(cls) -> pool.ThreadedConnectionPool:
        """
        Get or create connection pool (singleton pattern).
        
        Returns:
            PostgreSQL connection pool
        """
        # Keep ONE shared pool for all repositories to avoid
        # cross-class return mismatches under concurrent workers.
        if BasePostgresRepository._connection_pool is None:
            with BasePostgresRepository._pool_lock:
                if BasePostgresRepository._connection_pool is None:
                    BasePostgresRepository._connection_pool = pool.ThreadedConnectionPool(
                        minconn=2,
                        maxconn=20,
                        host=os.getenv("POSTGRES_HOST", "localhost"),
                        port=int(os.getenv("POSTGRES_PORT", "5432")),
                        database=os.getenv("POSTGRES_DB", "news_analyzer"),
                        user=os.getenv("POSTGRES_USER", "postgres"),
                        password=os.getenv("POSTGRES_PASSWORD", "postgres")
                    )
        return BasePostgresRepository._connection_pool
    
    def get_connection(self):
        """Get connection from pool."""
        return self.get_connection_pool().getconn()
    
    def release_connection(self, conn):
        """Release connection back to pool."""
        if conn is None:
            return
        try:
            self.get_connection_pool().putconn(conn)
        except pool.PoolError as e:
            # Defensive fallback: if a connection isn't tracked by the pool
            # (e.g. stale/unkeyed), close it to avoid crashing worker flow.
            self._logger.warning("PoolError on putconn; closing connection: %s", e)
            try:
                conn.close()
            except Exception:
                pass
    
    # ========================================
    # STATUS MAPPING: DB (str) <-> Domain (PipelineStatus)
    # ========================================
    
    @staticmethod
    def map_status_to_domain(status_str: str, status_type: str = "document") -> PipelineStatus:
        """
        Map database status string to domain PipelineStatus.
        
        Args:
            status_str: Status from database (e.g., "ocr_processing", "completed", "insight_pending")
            status_type: Type of status ("document", "insight", "worker")
        
        Returns:
            PipelineStatus domain object
        
        Examples:
            >>> map_status_to_domain("ocr_processing", "document")
            PipelineStatus(stage=StageEnum.OCR, state=StateEnum.PROCESSING)
            
            >>> map_status_to_domain("completed", "document")
            PipelineStatus(terminal_state=TerminalStateEnum.COMPLETED)
            
            >>> map_status_to_domain("insight_pending", "insight")
            PipelineStatus.for_insight(InsightStatusEnum.PENDING)
        """
        # Try parsing with from_string (handles all cases)
        try:
            return PipelineStatus.from_string(status_str, status_type=status_type)
        except ValueError as e:
            # Fallback: raw status if parsing fails
            return PipelineStatus(_raw_status=status_str, status_type=status_type)
    
    @staticmethod
    def map_status_from_domain(status: PipelineStatus) -> str:
        """
        Map domain PipelineStatus to database status string.
        
        Args:
            status: PipelineStatus domain object
        
        Returns:
            Status string for database (e.g., "ocr_processing", "completed")
        
        Examples:
            >>> status = PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING)
            >>> map_status_from_domain(status)
            "ocr_processing"
            
            >>> status = PipelineStatus.terminal(TerminalStateEnum.COMPLETED)
            >>> map_status_from_domain(status)
            "completed"
        """
        return status.full_status()
    
    # ========================================
    # COMMON QUERY HELPERS
    # ========================================
    
    def execute_query(
        self, 
        query: str, 
        params: tuple = (), 
        fetch_one: bool = False,
        fetch_all: bool = False
    ) -> Optional[Any]:
        """
        Execute query with connection pooling.
        
        Args:
            query: SQL query
            params: Query parameters
            fetch_one: If True, return single row
            fetch_all: If True, return all rows
        
        Returns:
            Query result or None
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            else:
                conn.commit()
                return None
        finally:
            self.release_connection(conn)
    
    def execute_with_return(
        self, 
        query: str, 
        params: tuple = ()
    ) -> Optional[Any]:
        """
        Execute INSERT/UPDATE with RETURNING clause.
        
        Args:
            query: SQL query with RETURNING clause
            params: Query parameters
        
        Returns:
            Returned value from query
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            conn.commit()
            return result[0] if result else None
        finally:
            self.release_connection(conn)
    
    @staticmethod
    def map_row_to_dict(cursor, row) -> Dict[str, Any]:
        """
        Map database row to dictionary.
        
        Args:
            cursor: Database cursor (has column names)
            row: Database row tuple
        
        Returns:
            Dictionary with column names as keys
        """
        if row is None:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
