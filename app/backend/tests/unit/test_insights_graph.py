"""
Unit Tests for LangGraph Insights Workflow.

Tests state machine, validation, retry logic, and error handling.
"""

import pytest
from unittest.mock import AsyncMock, patch

import sys
sys.path.insert(0, '/Users/diego.a/Workspace/Experiments/news-analyzer/app/backend')

from adapters.driven.llm.graphs.insights_graph import (
    InsightState,
    extract_node,
    validate_extraction_node,
    analyze_node,
    validate_analysis_node,
    finalize_node,
    error_node,
    should_retry_extraction,
    should_retry_analysis,
    run_insights_workflow
)
from tests.fixtures.mock_providers import (
    MockExtractionProvider,
    MockAnalysisProvider,
    FailingMockProvider
)


# ============================================================================
# Test Validation Nodes
# ============================================================================

class TestValidationNodes:
    """Test validation logic for extraction and analysis."""
    
    @pytest.mark.asyncio
    async def test_validate_extraction_valid(self):
        """Test that valid extraction passes validation."""
        state: InsightState = {
            'news_item_id': 'test_123',
            'document_id': 'doc_456',
            'context': 'context',
            'title': 'title',
            'extracted_data': """## Metadata
Date: 2026-03-31

## Actors
- Name: Test Actor | Type: person

## Events
- Event: Test Event
""",
            'extraction_tokens': 100,
            'analysis': None,
            'analysis_tokens': 0,
            'extraction_valid': False,
            'analysis_valid': False,
            'extraction_attempts': 1,
            'analysis_attempts': 0,
            'max_attempts': 3,
            'provider_used': 'mock',
            'model_used': 'mock-model',
            'full_text': None,
            'success': False,
            'error': None,
            'error_step': None
        }
        
        result = await validate_extraction_node(state)
        
        assert result['extraction_valid'] is True
    
    @pytest.mark.asyncio
    async def test_validate_extraction_invalid_no_metadata(self):
        """Test that extraction without metadata fails validation."""
        state: InsightState = {
            'news_item_id': 'test_123',
            'document_id': 'doc_456',
            'context': 'context',
            'title': 'title',
            'extracted_data': """## Actors
- Name: Test Actor
""",  # Missing metadata
            'extraction_tokens': 100,
            'analysis': None,
            'analysis_tokens': 0,
            'extraction_valid': False,
            'analysis_valid': False,
            'extraction_attempts': 1,
            'analysis_attempts': 0,
            'max_attempts': 3,
            'provider_used': 'mock',
            'model_used': 'mock-model',
            'full_text': None,
            'success': False,
            'error': None,
            'error_step': None
        }
        
        result = await validate_extraction_node(state)
        
        assert result['extraction_valid'] is False
    
    @pytest.mark.asyncio
    async def test_validate_extraction_invalid_too_short(self):
        """Test that too-short extraction fails validation."""
        state: InsightState = {
            'news_item_id': 'test_123',
            'document_id': 'doc_456',
            'context': 'context',
            'title': 'title',
            'extracted_data': "## Metadata\nShort",  # Too short (<100 chars)
            'extraction_tokens': 100,
            'analysis': None,
            'analysis_tokens': 0,
            'extraction_valid': False,
            'analysis_valid': False,
            'extraction_attempts': 1,
            'analysis_attempts': 0,
            'max_attempts': 3,
            'provider_used': 'mock',
            'model_used': 'mock-model',
            'full_text': None,
            'success': False,
            'error': None,
            'error_step': None
        }
        
        result = await validate_extraction_node(state)
        
        assert result['extraction_valid'] is False
    
    @pytest.mark.asyncio
    async def test_validate_analysis_valid(self):
        """Test that valid analysis passes validation."""
        state: InsightState = {
            'news_item_id': 'test_123',
            'document_id': 'doc_456',
            'context': 'context',
            'title': 'title',
            'extracted_data': 'data',
            'extraction_tokens': 100,
            'analysis': """## Significance
This is a significant event that demonstrates important trends.

## Context
Historical context shows this is part of a larger pattern.

## Implications
The implications are far-reaching and will impact multiple sectors.
""",
            'analysis_tokens': 50,
            'extraction_valid': True,
            'analysis_valid': False,
            'extraction_attempts': 1,
            'analysis_attempts': 1,
            'max_attempts': 3,
            'provider_used': 'mock',
            'model_used': 'mock-model',
            'full_text': None,
            'success': False,
            'error': None,
            'error_step': None
        }
        
        result = await validate_analysis_node(state)
        
        assert result['analysis_valid'] is True
    
    @pytest.mark.asyncio
    async def test_validate_analysis_invalid_no_significance(self):
        """Test that analysis without significance fails validation."""
        state: InsightState = {
            'news_item_id': 'test_123',
            'document_id': 'doc_456',
            'context': 'context',
            'title': 'title',
            'extracted_data': 'data',
            'extraction_tokens': 100,
            'analysis': """## Context
Some context but no significance section.
""",
            'analysis_tokens': 50,
            'extraction_valid': True,
            'analysis_valid': False,
            'extraction_attempts': 1,
            'analysis_attempts': 1,
            'max_attempts': 3,
            'provider_used': 'mock',
            'model_used': 'mock-model',
            'full_text': None,
            'success': False,
            'error': None,
            'error_step': None
        }
        
        result = await validate_analysis_node(state)
        
        assert result['analysis_valid'] is False


# ============================================================================
# Test Conditional Edges (Retry Logic)
# ============================================================================

class TestConditionalEdges:
    """Test retry routing logic."""
    
    def test_should_retry_extraction_continue(self):
        """Test that valid extraction continues to analysis."""
        state: InsightState = {
            'extraction_valid': True,
            'extraction_attempts': 1,
            'max_attempts': 3,
            # ... other fields not needed for this test
        }
        
        decision = should_retry_extraction(state)
        
        assert decision == "continue"
    
    def test_should_retry_extraction_retry(self):
        """Test that invalid extraction retries if attempts remain."""
        state: InsightState = {
            'extraction_valid': False,
            'extraction_attempts': 1,
            'max_attempts': 3,
        }
        
        decision = should_retry_extraction(state)
        
        assert decision == "retry"
    
    def test_should_retry_extraction_fail(self):
        """Test that extraction fails after max attempts."""
        state: InsightState = {
            'extraction_valid': False,
            'extraction_attempts': 3,
            'max_attempts': 3,
        }
        
        decision = should_retry_extraction(state)
        
        assert decision == "fail"
    
    def test_should_retry_analysis_continue(self):
        """Test that valid analysis continues to finalize."""
        state: InsightState = {
            'analysis_valid': True,
            'analysis_attempts': 1,
            'max_attempts': 3,
        }
        
        decision = should_retry_analysis(state)
        
        assert decision == "continue"
    
    def test_should_retry_analysis_retry(self):
        """Test that invalid analysis retries if attempts remain."""
        state: InsightState = {
            'analysis_valid': False,
            'analysis_attempts': 1,
            'max_attempts': 3,
        }
        
        decision = should_retry_analysis(state)
        
        assert decision == "retry"
    
    def test_should_retry_analysis_fail(self):
        """Test that analysis fails after max attempts."""
        state: InsightState = {
            'analysis_valid': False,
            'analysis_attempts': 3,
            'max_attempts': 3,
        }
        
        decision = should_retry_analysis(state)
        
        assert decision == "fail"


# ============================================================================
# Test Finalize Node
# ============================================================================

class TestFinalizeNode:
    """Test finalization of workflow."""
    
    @pytest.mark.asyncio
    async def test_finalize_combines_results(self):
        """Test that finalize combines extraction and analysis."""
        state: InsightState = {
            'news_item_id': 'test_123',
            'document_id': 'doc_456',
            'context': 'context',
            'title': 'title',
            'extracted_data': '## Metadata\nExtracted data here',
            'extraction_tokens': 100,
            'analysis': '## Significance\nAnalysis here',
            'analysis_tokens': 50,
            'extraction_valid': True,
            'analysis_valid': True,
            'extraction_attempts': 1,
            'analysis_attempts': 1,
            'max_attempts': 3,
            'provider_used': 'mock',
            'model_used': 'mock-model',
            'full_text': None,
            'success': False,
            'error': None,
            'error_step': None
        }
        
        result = await finalize_node(state)
        
        assert result['success'] is True
        assert result['full_text'] is not None
        assert '## Metadata' in result['full_text']
        assert '## Significance' in result['full_text']


# ============================================================================
# Test Error Node
# ============================================================================

class TestErrorNode:
    """Test error handling."""
    
    @pytest.mark.asyncio
    async def test_error_node_marks_failed(self):
        """Test that error node marks workflow as failed."""
        state: InsightState = {
            'news_item_id': 'test_123',
            'document_id': 'doc_456',
            'context': 'context',
            'title': 'title',
            'extracted_data': None,
            'extraction_tokens': 0,
            'analysis': None,
            'analysis_tokens': 0,
            'extraction_valid': False,
            'analysis_valid': False,
            'extraction_attempts': 3,
            'analysis_attempts': 0,
            'max_attempts': 3,
            'provider_used': None,
            'model_used': None,
            'full_text': None,
            'success': False,
            'error': 'Extraction failed after 3 attempts',
            'error_step': 'extraction'
        }
        
        result = await error_node(state)
        
        assert result['success'] is False
        assert result['error'] is not None


# ============================================================================
# Test Full Workflow (Integration-style)
# ============================================================================

class TestFullWorkflow:
    """Test complete workflow execution."""
    
    @pytest.mark.asyncio
    async def test_successful_workflow_with_mock_providers(self):
        """Test complete successful workflow with mock providers."""
        # Mock the provider getter to return our mocks
        with patch('adapters.driven.llm.graphs.insights_graph._get_providers') as mock_get_providers:
            mock_get_providers.return_value = [
                MockExtractionProvider(),
                MockAnalysisProvider()
            ]
            
            result = await run_insights_workflow(
                news_item_id="test_123",
                document_id="doc_456",
                context="This is a test news article about an important event.",
                title="Test News Article",
                max_attempts=3
            )
            
            assert result['success'] is True
            assert result['full_text'] is not None
            assert result['provider_used'] is not None
            assert result['extraction_tokens'] > 0
            assert result['analysis_tokens'] > 0
    
    @pytest.mark.asyncio
    async def test_workflow_failure_after_max_retries(self):
        """Test workflow fails after max extraction attempts."""
        # Mock provider that always returns invalid extraction
        class InvalidExtractionProvider(MockExtractionProvider):
            def __init__(self):
                super().__init__(responses={'default': 'Too short'})  # <100 chars, fails validation
        
        with patch('adapters.driven.llm.graphs.insights_graph._get_providers') as mock_get_providers:
            mock_get_providers.return_value = [InvalidExtractionProvider()]
            
            result = await run_insights_workflow(
                news_item_id="test_123",
                document_id="doc_456",
                context="Test context",
                title="Test Title",
                max_attempts=2  # Lower for faster test
            )
            
            assert result['success'] is False
            assert result['extraction_attempts'] == 2
            assert not result['extraction_valid']


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
