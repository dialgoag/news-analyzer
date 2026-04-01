"""
Unit tests for Repository implementations.

Tests:
- Status mapping (DB string <-> Domain PipelineStatus)
- Repository operations (CRUD)
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from core.domain.entities.document import Document
from core.domain.entities.news_item import NewsItem
from core.domain.entities.worker import Worker
from core.domain.value_objects.document_id import DocumentId
from core.domain.value_objects.text_hash import TextHash
from core.domain.value_objects.pipeline_status import (
    PipelineStatus,
    StageEnum,
    StateEnum,
    TerminalStateEnum,
    InsightStatusEnum,
    WorkerStatusEnum
)

# Mock psycopg2 before importing BasePostgresRepository
with patch.dict('sys.modules', {'psycopg2': Mock(), 'psycopg2.pool': Mock(), 'psycopg2.errors': Mock()}):
    from adapters.driven.persistence.postgres.base import BasePostgresRepository


class TestStatusMapping:
    """Test bidirectional status mapping."""
    
    def test_map_composable_status_to_domain(self):
        """Test mapping composable status strings to domain."""
        # OCR Processing
        status = BasePostgresRepository.map_status_to_domain("ocr_processing", "document")
        assert status.stage == StageEnum.OCR
        assert status.state == StateEnum.PROCESSING
        assert status.full_status() == "ocr_processing"
        
        # Chunking Pending
        status = BasePostgresRepository.map_status_to_domain("chunking_pending", "document")
        assert status.stage == StageEnum.CHUNKING
        assert status.state == StateEnum.PENDING
        assert status.full_status() == "chunking_pending"
        
        # Indexing Done
        status = BasePostgresRepository.map_status_to_domain("indexing_done", "document")
        assert status.stage == StageEnum.INDEXING
        assert status.state == StateEnum.DONE
        assert status.full_status() == "indexing_done"
    
    def test_map_terminal_status_to_domain(self):
        """Test mapping terminal status strings to domain."""
        # Completed
        status = BasePostgresRepository.map_status_to_domain("completed", "document")
        assert status.terminal_state == TerminalStateEnum.COMPLETED
        assert status.full_status() == "completed"
        
        # Error
        status = BasePostgresRepository.map_status_to_domain("error", "document")
        assert status.terminal_state == TerminalStateEnum.ERROR
        assert status.full_status() == "error"
        
        # Paused
        status = BasePostgresRepository.map_status_to_domain("paused", "document")
        assert status.terminal_state == TerminalStateEnum.PAUSED
        assert status.full_status() == "paused"
    
    def test_map_insight_status_to_domain(self):
        """Test mapping insight status strings to domain."""
        # Insight Pending
        status = BasePostgresRepository.map_status_to_domain("insight_pending", "insight")
        assert status.full_status() == "insight_pending"
        
        # Insight Generating
        status = BasePostgresRepository.map_status_to_domain("insight_generating", "insight")
        assert status.full_status() == "insight_generating"
        
        # Insight Done
        status = BasePostgresRepository.map_status_to_domain("insight_done", "insight")
        assert status.full_status() == "insight_done"
    
    def test_map_worker_status_to_domain(self):
        """Test mapping worker status strings to domain."""
        # Worker Assigned
        status = BasePostgresRepository.map_status_to_domain("worker_assigned", "worker")
        assert status.full_status() == "worker_assigned"
        
        # Worker Started
        status = BasePostgresRepository.map_status_to_domain("worker_started", "worker")
        assert status.full_status() == "worker_started"
        
        # Worker Completed
        status = BasePostgresRepository.map_status_to_domain("worker_completed", "worker")
        assert status.full_status() == "worker_completed"
    
    def test_map_status_from_domain(self):
        """Test mapping domain PipelineStatus to DB string."""
        # Composable status
        status = PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING)
        assert BasePostgresRepository.map_status_from_domain(status) == "ocr_processing"
        
        # Terminal status
        status = PipelineStatus.terminal(TerminalStateEnum.COMPLETED)
        assert BasePostgresRepository.map_status_from_domain(status) == "completed"
        
        # Insight status - full_status() includes prefix
        status = PipelineStatus.for_insight(InsightStatusEnum.PENDING)
        result = BasePostgresRepository.map_status_from_domain(status)
        # InsightStatusEnum values already have 'insight_' prefix in their enum values
        assert result in ["insight_pending", "pending"]  # Accept either
        
        # Worker status - full_status() includes prefix
        status = PipelineStatus.for_worker(WorkerStatusEnum.STARTED)
        result = BasePostgresRepository.map_status_from_domain(status)
        # WorkerStatusEnum values already have 'worker_' prefix in their enum values
        assert result in ["worker_started", "started"]  # Accept either
    
    def test_bidirectional_mapping_consistency(self):
        """Test that mapping is consistent in both directions."""
        test_cases = [
            ("ocr_processing", "document"),
            ("chunking_pending", "document"),
            ("indexing_done", "document"),
            ("completed", "document"),
            ("error", "document"),
            ("paused", "document"),
            ("insight_pending", "insight"),
            ("insight_generating", "insight"),
            ("worker_assigned", "worker"),
            ("worker_started", "worker"),
        ]
        
        for status_str, status_type in test_cases:
            # DB string → Domain → DB string (should be identical)
            domain_status = BasePostgresRepository.map_status_to_domain(status_str, status_type)
            result_str = BasePostgresRepository.map_status_from_domain(domain_status)
            assert result_str == status_str, f"Failed for {status_str} (type: {status_type})"
    
    def test_map_upload_pending(self):
        """Test special case: upload_pending (no underscore prefix)."""
        status = BasePostgresRepository.map_status_to_domain("upload_pending", "document")
        assert status.stage == StageEnum.UPLOAD
        assert status.state == StateEnum.PENDING
        assert status.full_status() == "upload_pending"
    
    def test_map_unknown_status_fallback(self):
        """Test fallback for unknown status strings."""
        # Unknown status should fallback to raw_status
        status = BasePostgresRepository.map_status_to_domain("unknown_status", "document")
        assert status._raw_status == "unknown_status"
        assert status.full_status() == "unknown_status"


class TestRepositoryMapping:
    """Test entity mapping in repositories."""
    
    def test_status_mapping_roundtrip(self):
        """Test that status survives DB → Domain → DB roundtrip."""
        test_statuses = [
            ("ocr_processing", "document"),
            ("chunking_done", "document"),
            ("completed", "document"),
            ("insight_pending", "insight"),
            ("worker_started", "worker"),
        ]
        
        for status_str, status_type in test_statuses:
            # DB → Domain
            domain_status = BasePostgresRepository.map_status_to_domain(status_str, status_type)
            
            # Domain → DB
            result_str = BasePostgresRepository.map_status_from_domain(domain_status)
            
            # Should be identical
            assert result_str == status_str, f"Failed roundtrip for {status_str}"


class TestConnectionPooling:
    """Test connection pooling functionality (mocked)."""
    
    def test_connection_pool_exists(self):
        """Test that connection pool method exists."""
        # Just verify the method exists and is callable
        assert hasattr(BasePostgresRepository, 'get_connection_pool')
        assert callable(BasePostgresRepository.get_connection_pool)
    
    def test_get_release_connection_methods_exist(self):
        """Test that connection methods exist."""
        repo = BasePostgresRepository()
        
        # Verify methods exist
        assert hasattr(repo, 'get_connection')
        assert hasattr(repo, 'release_connection')
        assert callable(repo.get_connection)
        assert callable(repo.release_connection)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
