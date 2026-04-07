"""
Unit tests for Domain Entities.

Tests Document, NewsItem, Worker entities and their business logic with composable status system.
"""

import pytest
from datetime import datetime, timedelta

from core.domain.entities import Document, DocumentType, NewsItem, Worker, WorkerType
from core.domain.value_objects import (
    DocumentId, NewsItemId, TextHash, 
    PipelineStatus, StageEnum, StateEnum, TerminalStateEnum,
    InsightStatusEnum, WorkerStatusEnum
)


# ============================================================================
# Document Entity Tests
# ============================================================================

class TestDocument:
    """Test Document entity with composable status."""
    
    def test_create_document(self):
        """Test creating a new document."""
        doc = Document.create(
            filename="test.pdf",
            sha256="a" * 64,
            file_size=1024000
        )
        
        assert doc.filename == "test.pdf"
        assert doc.sha256 == "a" * 64
        assert doc.file_size == 1024000
        assert doc.document_type == DocumentType.PDF
        assert doc.get_production_status() == "upload_pending"
    
    def test_infer_document_type(self):
        """Test document type inference from filename."""
        pdf_doc = Document.create("file.pdf", "a" * 64, 1000)
        txt_doc = Document.create("file.txt", "b" * 64, 1000)
        docx_doc = Document.create("file.docx", "c" * 64, 1000)
        unknown_doc = Document.create("file.xyz", "d" * 64, 1000)
        
        assert pdf_doc.document_type == DocumentType.PDF
        assert txt_doc.document_type == DocumentType.TEXT
        assert docx_doc.document_type == DocumentType.DOCX
        assert unknown_doc.document_type == DocumentType.UNKNOWN
    
    def test_advance_within_stage(self):
        """Test advancing states within same stage."""
        doc = Document.create("test.pdf", "a" * 64, 1000)
        
        # upload_pending → upload_processing
        doc.advance_to(StageEnum.UPLOAD, StateEnum.PROCESSING)
        assert doc.get_production_status() == "upload_processing"
        
        # upload_processing → upload_done
        doc.advance_to(StageEnum.UPLOAD, StateEnum.DONE)
        assert doc.get_production_status() == "upload_done"
    
    def test_advance_to_new_stage(self):
        """Test advancing to new stage."""
        doc = Document.create("test.pdf", "a" * 64, 1000)
        
        # Complete upload stage
        doc.advance_to(StageEnum.UPLOAD, StateEnum.PROCESSING)
        doc.advance_to(StageEnum.UPLOAD, StateEnum.DONE)
        
        # Advance to OCR stage (must start at PENDING)
        doc.advance_to(StageEnum.OCR, StateEnum.PENDING)
        assert doc.get_production_status() == "ocr_pending"
        assert doc.current_stage() == StageEnum.OCR
    
    def test_cannot_skip_stages(self):
        """Test that can't skip stages."""
        doc = Document.create("test.pdf", "a" * 64, 1000)
        doc.advance_to(StageEnum.UPLOAD, StateEnum.PROCESSING)
        doc.advance_to(StageEnum.UPLOAD, StateEnum.DONE)
        
        # Can't skip OCR and go to CHUNKING
        with pytest.raises(ValueError, match="Invalid stage transition"):
            doc.advance_to(StageEnum.CHUNKING, StateEnum.PENDING)
    
    def test_cannot_advance_stage_without_completing_current(self):
        """Test must complete current stage before advancing."""
        doc = Document.create("test.pdf", "a" * 64, 1000)
        doc.advance_to(StageEnum.UPLOAD, StateEnum.PROCESSING)
        
        # Can't advance to next stage while still PROCESSING
        with pytest.raises(ValueError, match="Must complete current stage"):
            doc.advance_to(StageEnum.OCR, StateEnum.PENDING)
    
    def test_new_stage_must_start_at_pending(self):
        """Test new stage must start at PENDING."""
        doc = Document.create("test.pdf", "a" * 64, 1000)
        doc.advance_to(StageEnum.UPLOAD, StateEnum.PROCESSING)
        doc.advance_to(StageEnum.UPLOAD, StateEnum.DONE)
        
        # New stage must start at PENDING
        with pytest.raises(ValueError, match="must start at PENDING"):
            doc.advance_to(StageEnum.OCR, StateEnum.PROCESSING)
    
    def test_mark_terminal_completed(self):
        """Test marking document as completed."""
        doc = Document.create("test.pdf", "a" * 64, 1000)
        
        # Go through pipeline to indexing_done
        doc.advance_to(StageEnum.UPLOAD, StateEnum.PROCESSING)
        doc.advance_to(StageEnum.UPLOAD, StateEnum.DONE)
        doc.advance_to(StageEnum.OCR, StateEnum.PENDING)
        doc.advance_to(StageEnum.OCR, StateEnum.PROCESSING)
        doc.advance_to(StageEnum.OCR, StateEnum.DONE)
        doc.advance_to(StageEnum.CHUNKING, StateEnum.PENDING)
        doc.advance_to(StageEnum.CHUNKING, StateEnum.PROCESSING)
        doc.advance_to(StageEnum.CHUNKING, StateEnum.DONE)
        doc.advance_to(StageEnum.INDEXING, StateEnum.PENDING)
        doc.advance_to(StageEnum.INDEXING, StateEnum.PROCESSING)
        doc.advance_to(StageEnum.INDEXING, StateEnum.DONE)
        
        # Can complete from indexing_done
        doc.mark_terminal(TerminalStateEnum.COMPLETED)
        assert doc.is_completed()
        assert doc.get_production_status() == "completed"
    
    def test_mark_terminal_error(self):
        """Test marking document as error."""
        doc = Document.create("test.pdf", "a" * 64, 1000)
        doc.mark_terminal(TerminalStateEnum.ERROR, error_message="OCR failed")
        
        assert doc.is_error()
        assert doc.error_message == "OCR failed"
    
    def test_error_requires_message(self):
        """Test that ERROR requires error_message."""
        doc = Document.create("test.pdf", "a" * 64, 1000)
        
        with pytest.raises(ValueError, match="error_message required"):
            doc.mark_terminal(TerminalStateEnum.ERROR)
    
    def test_update_ocr_results(self):
        """Test updating OCR results metadata."""
        doc = Document.create("test.pdf", "a" * 64, 1000)
        doc.update_ocr_results(total_pages=10, total_news_items=5, ocr_text_length=5000)
        
        assert doc.total_pages == 10
        assert doc.total_news_items == 5
        assert doc.ocr_text_length == 5000
    
    def test_equality_based_on_id(self):
        """Test that documents are equal based on ID, not attributes."""
        doc_id = DocumentId.from_string("doc_123")
        
        doc1 = Document.create("file1.pdf", "a" * 64, 1000)
        doc1.id = doc_id
        
        doc2 = Document.create("file2.pdf", "b" * 64, 2000)
        doc2.id = doc_id
        
        assert doc1 == doc2  # Same ID = same document


# ============================================================================
# NewsItem Entity Tests
# ============================================================================

class TestNewsItem:
    """Test NewsItem entity."""
    
    def test_create_news_item(self):
        """Test creating a new news item."""
        doc_id = DocumentId.from_string("doc_123")
        item = NewsItem.create(
            document_id=doc_id,
            item_index=0,
            title="Test Article",
            content="Article content here"
        )
        
        assert item.document_id == doc_id
        assert item.item_index == 0
        assert item.title == "Test Article"
        assert item.content == "Article content here"
        assert item.insight_status.full_status() == "insights_pending"
        assert item.text_hash is not None
    
    def test_text_hash_computed_from_content(self):
        """Test that text hash is computed from content."""
        doc_id = DocumentId.from_string("doc_123")
        item = NewsItem.create(
            document_id=doc_id,
            item_index=0,
            content="Test content"
        )
        
        assert item.text_hash is not None
        expected_hash = TextHash.compute("Test content")
        assert item.text_hash == expected_hash
    
    def test_queue_for_insights(self):
        """Test queueing item for insights."""
        doc_id = DocumentId.from_string("doc_123")
        item = NewsItem.create(doc_id, 0)
        item.queue_for_insights()
        
        assert item.insight_status.full_status() == "insights_queued"
    
    def test_start_generating_insights(self):
        """Test starting insights generation."""
        doc_id = DocumentId.from_string("doc_123")
        item = NewsItem.create(doc_id, 0)
        item.queue_for_insights()
        item.start_generating_insights()
        
        assert item.insight_status.full_status() == "insights_generating"
    
    def test_mark_insights_done(self):
        """Test marking insights as completed."""
        doc_id = DocumentId.from_string("doc_123")
        item = NewsItem.create(doc_id, 0)
        item.queue_for_insights()
        item.start_generating_insights()
        item.mark_insights_done(
            insight_content="Generated insights",
            llm_source="openai/gpt-4o-mini"
        )
        
        assert item.has_insights()
        assert item.insight_content == "Generated insights"
        assert item.llm_source == "openai/gpt-4o-mini"
    
    def test_mark_insights_error(self):
        """Test marking insights as error."""
        doc_id = DocumentId.from_string("doc_123")
        item = NewsItem.create(doc_id, 0)
        item.mark_insights_error("Generation failed")
        
        assert item.insight_status.full_status() == "insights_error"
        assert item.error_message == "Generation failed"
        assert item.can_retry_insights()
    
    def test_indexing_lifecycle(self):
        """Test indexing lifecycle (generating → indexing → done)."""
        doc_id = DocumentId.from_string("doc_123")
        item = NewsItem.create(doc_id, 0)
        item.queue_for_insights()
        item.start_generating_insights()
        
        # Correct flow: generating → indexing → done
        assert not item.is_indexed()
        
        item.start_indexing()
        assert item.insight_status.full_status() == "insights_indexing"
        
        # Mark insights done AFTER indexing
        item.mark_insights_done("Generated insights", "openai")
        assert item.has_insights()
        
        item.mark_indexed()
        assert item.is_indexed()


# ============================================================================
# Worker Entity Tests
# ============================================================================

class TestWorker:
    """Test Worker entity."""
    
    def test_create_worker(self):
        """Test creating a new worker."""
        worker = Worker.create(
            worker_type=WorkerType.INSIGHTS,
            task_id="insight_123",
            document_id="doc_456"
        )
        
        assert worker.worker_type == WorkerType.INSIGHTS
        assert worker.task_id == "insight_123"
        assert worker.document_id == "doc_456"
        assert worker.status.full_status() == "assigned"
        assert worker.worker_id.startswith("insights_")
    
    def test_worker_lifecycle(self):
        """Test complete worker lifecycle."""
        worker = Worker.create(WorkerType.OCR, "ocr_123", "doc_456")
        
        # Initially assigned (this IS active state)
        assert worker.is_active()
        assert worker.status.full_status() == "assigned"
        
        # Start
        worker.start()
        assert worker.is_active()
        assert worker.started_at is not None
        
        # Complete
        worker.complete()
        assert worker.is_completed()
        assert worker.completed_at is not None
        assert not worker.is_active()
    
    def test_worker_error(self):
        """Test worker error handling."""
        worker = Worker.create(WorkerType.INSIGHTS, "task_123", "doc_456")
        worker.start()
        worker.mark_error("Processing failed")
        
        assert worker.is_error()
        assert worker.error_message == "Processing failed"
        assert not worker.is_active()
    
    def test_duration_calculation(self):
        """Test worker duration calculation."""
        worker = Worker.create(WorkerType.OCR, "task_123", "doc_456")
        worker.start()
        
        # Simulate 5 second delay
        worker.started_at = datetime.utcnow() - timedelta(seconds=5)
        worker.complete()
        
        duration = worker.duration_seconds()
        assert duration is not None
        assert duration >= 4.0  # At least 4 seconds (small margin)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
