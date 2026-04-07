"""
Unit tests for Domain Value Objects.

Tests DocumentId, NewsItemId, TextHash, PipelineStatus (composable system).
"""

import pytest
from core.domain.value_objects import (
    DocumentId,
    NewsItemId,
    TextHash,
    PipelineStatus,
    StageEnum,
    StateEnum,
    TerminalStateEnum,
    InsightStatusEnum,
    WorkerStatusEnum,
)


# ============================================================================
# DocumentId Tests
# ============================================================================

class TestDocumentId:
    """Test DocumentId value object."""
    
    def test_create_from_string(self):
        """Test creating DocumentId from string."""
        doc_id = DocumentId.from_string("doc_123")
        assert str(doc_id) == "doc_123"
        assert doc_id.value == "doc_123"
    
    def test_generate(self):
        """Test generating new DocumentId."""
        doc_id = DocumentId.generate()
        assert doc_id.value.startswith("doc_")
        assert len(doc_id.value) > 10  # Has UUID
    
    def test_generate_with_custom_prefix(self):
        """Test generating with custom prefix."""
        doc_id = DocumentId.generate(prefix="test")
        assert doc_id.value.startswith("test_")
    
    def test_equality(self):
        """Test equality comparison."""
        id1 = DocumentId.from_string("doc_123")
        id2 = DocumentId.from_string("doc_123")
        id3 = DocumentId.from_string("doc_456")
        
        assert id1 == id2
        assert id1 != id3
        assert id1 == "doc_123"  # Can compare with string
    
    def test_immutable(self):
        """Test that DocumentId is immutable."""
        doc_id = DocumentId.from_string("doc_123")
        with pytest.raises(AttributeError):
            doc_id.value = "doc_456"  # Should raise (frozen dataclass)
    
    def test_empty_value_raises(self):
        """Test that empty value raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            DocumentId.from_string("")
    
    def test_hash(self):
        """Test that DocumentId can be used in sets/dicts."""
        id1 = DocumentId.from_string("doc_123")
        id2 = DocumentId.from_string("doc_123")
        id3 = DocumentId.from_string("doc_456")
        
        id_set = {id1, id2, id3}
        assert len(id_set) == 2  # id1 and id2 are same


# ============================================================================
# NewsItemId Tests
# ============================================================================

class TestNewsItemId:
    """Test NewsItemId value object."""
    
    def test_generate_from_document_and_index(self):
        """Test generating NewsItemId from document ID and index."""
        news_id = NewsItemId.generate("doc_123", 0)
        assert news_id.value == "doc_123_item_0"
    
    def test_equality(self):
        """Test equality comparison."""
        id1 = NewsItemId.from_string("doc_123_item_0")
        id2 = NewsItemId.from_string("doc_123_item_0")
        
        assert id1 == id2
        assert id1 == "doc_123_item_0"


# ============================================================================
# TextHash Tests
# ============================================================================

class TestTextHash:
    """Test TextHash value object."""
    
    def test_compute_hash(self):
        """Test computing hash from text."""
        text = "This is a test"
        text_hash = TextHash.compute(text)
        
        assert len(text_hash.value) == 64  # SHA256 hex
        assert text_hash.is_valid()
    
    def test_same_text_same_hash(self):
        """Test that same text produces same hash."""
        text = "Test content"
        hash1 = TextHash.compute(text)
        hash2 = TextHash.compute(text)
        
        assert hash1 == hash2
    
    def test_normalization(self):
        """Test that text normalization produces same hash."""
        text1 = "  Test   Content  "
        text2 = "test content"
        text3 = "TEST CONTENT"
        
        hash1 = TextHash.compute(text1)
        hash2 = TextHash.compute(text2)
        hash3 = TextHash.compute(text3)
        
        assert hash1 == hash2 == hash3
    
    def test_different_text_different_hash(self):
        """Test that different text produces different hash."""
        hash1 = TextHash.compute("Text A")
        hash2 = TextHash.compute("Text B")
        
        assert hash1 != hash2
    
    def test_from_string(self):
        """Test creating TextHash from existing hash."""
        hash_value = "a" * 64  # Valid SHA256 hex
        text_hash = TextHash.from_string(hash_value)
        
        assert text_hash.value == hash_value
        assert text_hash.is_valid()
    
    def test_invalid_hash_raises(self):
        """Test that invalid hash raises error."""
        with pytest.raises(ValueError, match="Invalid SHA256"):
            TextHash.from_string("not_a_hash")
    
    def test_short_form(self):
        """Test shortened hash for display."""
        text_hash = TextHash.compute("Test")
        short = text_hash.short_form(8)
        
        assert len(short) == 8
        assert text_hash.value.startswith(short)
    
    def test_immutable(self):
        """Test that TextHash is immutable."""
        text_hash = TextHash.compute("Test")
        with pytest.raises(AttributeError):
            text_hash.value = "new_hash"


# ============================================================================
# PipelineStatus Tests - Composable System
# ============================================================================

class TestPipelineStatusComposable:
    """Test composable PipelineStatus (stage + state)."""
    
    def test_create_composable_status(self):
        """Test creating composable status."""
        status = PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING)
        
        assert status.current_stage() == StageEnum.OCR
        assert status.current_state() == StateEnum.PROCESSING
        assert status.full_status() == "ocr_processing"
    
    def test_immutable(self):
        """Test that PipelineStatus is immutable."""
        status = PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING)
        
        with pytest.raises(AttributeError):
            status.stage = StageEnum.CHUNKING  # Should raise (frozen dataclass)
        
        with pytest.raises(AttributeError):
            status.state = StateEnum.DONE
    
    def test_terminal_status(self):
        """Test creating terminal status."""
        status = PipelineStatus.terminal(TerminalStateEnum.COMPLETED)
        
        assert status.full_status() == "completed"
        assert status.is_terminal()
    
    def test_from_string_composable(self):
        """Test parsing composable status from string."""
        status = PipelineStatus.from_string("chunking_done", "document")
        
        assert status.current_stage() == StageEnum.CHUNKING
        assert status.current_state() == StateEnum.DONE
    
    def test_from_string_terminal(self):
        """Test parsing terminal status from string."""
        status = PipelineStatus.from_string("error", "document")
        
        assert status.is_terminal()
        assert status.full_status() == "error"
    
    def test_is_processing(self):
        """Test processing status detection."""
        status = PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING)
        assert status.is_processing()
        
        status_done = PipelineStatus.create(StageEnum.OCR, StateEnum.DONE)
        assert not status_done.is_processing()
    
    def test_can_transition_to_state(self):
        """Test state transition validation within same stage."""
        status = PipelineStatus.create(StageEnum.OCR, StateEnum.PENDING)
        
        # Can go pending → processing
        assert status.can_transition_to_state(StateEnum.PROCESSING)
        
        # Cannot skip to done
        assert not status.can_transition_to_state(StateEnum.DONE)
    
    def test_can_transition_to_stage(self):
        """Test stage transition validation."""
        # Must be DONE before advancing stage
        status_pending = PipelineStatus.create(StageEnum.OCR, StateEnum.PENDING)
        assert not status_pending.can_transition_to_stage(StageEnum.CHUNKING)
        
        # Can advance when DONE
        status_done = PipelineStatus.create(StageEnum.OCR, StateEnum.DONE)
        assert status_done.can_transition_to_stage(StageEnum.CHUNKING)
    
    def test_can_transition_to_terminal(self):
        """Test terminal transition validation."""
        status = PipelineStatus.create(StageEnum.INDEXING, StateEnum.DONE)
        
        # Can complete from indexing_done
        assert status.can_transition_to_terminal(TerminalStateEnum.COMPLETED)
        
        # Can always error
        assert status.can_transition_to_terminal(TerminalStateEnum.ERROR)


class TestInsightStatus:
    """Test insight-specific statuses."""
    
    def test_create_insight_status(self):
        """Test creating insight status."""
        status = PipelineStatus.for_insight(InsightStatusEnum.GENERATING)
        
        assert status.full_status() == "insights_generating"
        assert status.is_processing()
    
    def test_insight_from_string(self):
        """Test parsing insight status."""
        status = PipelineStatus.from_string("insights_generating", "insight")
        assert status.full_status() == "insights_generating"
    
    def test_insight_terminal(self):
        """Test insight terminal state."""
        status = PipelineStatus.for_insight(InsightStatusEnum.DONE)
        assert status.is_terminal()


class TestWorkerStatus:
    """Test worker-specific statuses."""
    
    def test_create_worker_status(self):
        """Test creating worker status."""
        status = PipelineStatus.for_worker(WorkerStatusEnum.STARTED)
        
        assert status.full_status() == "started"
        assert status.is_processing()
    
    def test_worker_from_string(self):
        """Test parsing worker status."""
        status = PipelineStatus.from_string("completed", "worker")
        assert status.full_status() == "completed"
        assert status.is_terminal()


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
