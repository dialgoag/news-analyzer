"""
Test Pipeline Orchestrator Agent

Basic tests to verify the orchestrator workflow.

Date: 2026-04-10
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import asyncpg

from adapters.driven.llm.graphs.pipeline_orchestrator_graph import (
    PipelineOrchestratorAgent,
    create_orchestrator_agent,
    OrchestratorState
)


@pytest.fixture
async def mock_db_pool():
    """Mock AsyncPG pool"""
    pool = AsyncMock(spec=asyncpg.Pool)
    
    # Mock fetchrow for check_legacy
    pool.fetchrow = AsyncMock(return_value={
        'data_source': 'legacy',
        'migration_status': 'pending',
        'publication_date': None,
        'newspaper_name': 'Test Paper',
        'sha8_prefix': 'abc12345'
    })
    
    # Mock execute for event persistence
    pool.execute = AsyncMock(return_value=None)
    
    return pool


@pytest.fixture
def sample_document():
    """Sample document for testing"""
    return {
        'document_id': 'test-doc-123',
        'filename': '01-01-26-Test.pdf',
        'filepath': '/tmp/test.pdf'
    }


@pytest.mark.asyncio
async def test_orchestrator_agent_creation(mock_db_pool):
    """Test that orchestrator agent can be created"""
    agent = create_orchestrator_agent(mock_db_pool)
    
    assert agent is not None
    assert isinstance(agent, PipelineOrchestratorAgent)
    assert agent.db_pool == mock_db_pool
    assert agent.workflow is not None


@pytest.mark.asyncio
async def test_check_legacy_node(mock_db_pool, sample_document):
    """Test check_if_legacy_node"""
    from adapters.driven.llm.graphs.pipeline_orchestrator_graph import check_if_legacy_node
    
    initial_state: OrchestratorState = {
        'document_id': sample_document['document_id'],
        'filename': sample_document['filename'],
        'filepath': sample_document['filepath'],
        'metadata': {},
        'pipeline_context': {},
        'current_stage': None,
        'migration_mode': False,
        'legacy_data': {},
        'new_data': {},
        'validation_results': {},
        'merged_data': {},
        'events': [],
        'errors': [],
        'skip_insights': False,
        'retry_ocr_with_tika': False
    }
    
    result_state = await check_if_legacy_node(initial_state, mock_db_pool)
    
    # Should set migration_mode to True
    assert result_state['migration_mode'] == True
    
    # Should populate metadata
    assert result_state['metadata']['newspaper'] == 'Test Paper'
    assert result_state['metadata']['data_source'] == 'legacy'


@pytest.mark.asyncio
@patch('os.path.exists', return_value=True)
@patch('os.path.getsize', return_value=1000000)
async def test_validation_node(mock_getsize, mock_exists, mock_db_pool, sample_document):
    """Test validation_node"""
    from adapters.driven.llm.graphs.pipeline_orchestrator_graph import validation_node
    
    initial_state: OrchestratorState = {
        'document_id': sample_document['document_id'],
        'filename': sample_document['filename'],
        'filepath': sample_document['filepath'],
        'metadata': {},
        'pipeline_context': {},
        'current_stage': None,
        'migration_mode': False,
        'legacy_data': {},
        'new_data': {},
        'validation_results': {},
        'merged_data': {},
        'events': [],
        'errors': [],
        'skip_insights': False,
        'retry_ocr_with_tika': False
    }
    
    result_state = await validation_node(initial_state, mock_db_pool)
    
    # Should set current_stage
    assert result_state['current_stage'] == 'validation'
    
    # Should have validation result in pipeline_context
    assert 'validation' in result_state['pipeline_context']
    assert result_state['pipeline_context']['validation']['valid'] == True
    
    # Should have new_data for validation
    assert 'validation' in result_state['new_data']
    
    # Should have persisted events
    assert mock_db_pool.execute.called


@pytest.mark.asyncio
async def test_orchestrator_state_structure():
    """Test that OrchestratorState has all required fields"""
    state: OrchestratorState = {
        'document_id': 'test',
        'filename': 'test.pdf',
        'filepath': '/tmp/test.pdf',
        'metadata': {},
        'pipeline_context': {},
        'current_stage': None,
        'migration_mode': False,
        'legacy_data': {},
        'new_data': {},
        'validation_results': {},
        'merged_data': {},
        'events': [],
        'errors': [],
        'skip_insights': False,
        'retry_ocr_with_tika': False
    }
    
    # Should have all required keys
    required_keys = [
        'document_id', 'filename', 'filepath', 'metadata', 'pipeline_context',
        'current_stage', 'migration_mode', 'legacy_data', 'new_data',
        'validation_results', 'merged_data', 'events', 'errors',
        'skip_insights', 'retry_ocr_with_tika'
    ]
    
    for key in required_keys:
        assert key in state, f"Missing required key: {key}"


@pytest.mark.asyncio
async def test_persist_event_helper(mock_db_pool):
    """Test _persist_event helper function"""
    from adapters.driven.llm.graphs.pipeline_orchestrator_graph import _persist_event
    
    await _persist_event(
        document_id='test-123',
        stage='validation',
        status='completed',
        duration=1.5,
        metadata={'test': 'data'},
        db_pool=mock_db_pool
    )
    
    # Should have called execute
    assert mock_db_pool.execute.called
    call_args = mock_db_pool.execute.call_args
    
    # Verify SQL includes document_processing_log
    assert 'document_processing_log' in call_args[0][0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
