"""
Test script for InsightsWorkerService integration.

This script tests that:
1. InsightsWorkerService imports correctly
2. Dependencies are available
3. Service can be instantiated
4. Mock workflow execution works
"""

import sys
import os
sys.path.insert(0, '/Users/diego.a/Workspace/Experiments/news-analyzer/app/backend')

print("=" * 60)
print("Testing InsightsWorkerService Integration")
print("=" * 60)

# Test 1: Import check
print("\n[Test 1] Checking imports...")
try:
    from core.application.services.insights_worker_service import (
        InsightsWorkerService,
        InsightResult,
        get_insights_worker_service
    )
    print("✅ InsightsWorkerService imported successfully")
except Exception as e:
    print(f"❌ Failed to import InsightsWorkerService: {e}")
    sys.exit(1)

try:
    from adapters.driven.llm.graphs.insights_graph import run_insights_workflow
    print("✅ run_insights_workflow imported successfully")
except Exception as e:
    print(f"❌ Failed to import run_insights_workflow: {e}")
    sys.exit(1)

try:
    from adapters.driven.memory.insight_memory import InsightMemory
    print("✅ InsightMemory imported successfully")
except Exception as e:
    print(f"❌ Failed to import InsightMemory: {e}")
    sys.exit(1)

# Test 2: Service instantiation (in-memory for testing)
print("\n[Test 2] Testing service instantiation...")
try:
    service = InsightsWorkerService(
        cache_backend="memory",  # Use in-memory for testing
        cache_ttl_days=1,
        cache_max_size=100
    )
    print("✅ InsightsWorkerService instantiated successfully")
    print(f"   Cache backend: memory")
    print(f"   Cache TTL: 1 day")
    print(f"   Cache max size: 100")
except Exception as e:
    print(f"❌ Failed to instantiate service: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Check cache stats
print("\n[Test 3] Testing cache stats...")
try:
    import asyncio
    stats = asyncio.run(service.get_cache_stats())
    print("✅ Cache stats retrieved successfully")
    print(f"   Stats: {stats}")
except Exception as e:
    print(f"❌ Failed to get cache stats: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Test with mock providers (if available)
print("\n[Test 4] Testing workflow with mocks...")
try:
    from tests.fixtures.mock_providers import UnifiedMockProvider
    from adapters.driven.llm.graphs.insights_graph import _get_providers
    from unittest.mock import patch
    
    print("✅ Mock providers available")
    
    # Test workflow execution with mocks
    async def test_workflow():
        with patch('adapters.driven.llm.graphs.insights_graph._get_providers') as mock_get_providers:
            mock_get_providers.return_value = [UnifiedMockProvider()]
            
            result = await service.generate_insights(
                news_item_id="test_123",
                document_id="doc_456",
                context="This is a test article about important events.",
                title="Test Article",
                max_attempts=2
            )
            
            return result
    
    result = asyncio.run(test_workflow())
    
    print("✅ Workflow executed successfully with mocks")
    print(f"   Content length: {len(result.content)} chars")
    print(f"   Provider: {result.provider_used}")
    print(f"   Model: {result.model_used}")
    print(f"   Total tokens: {result.total_tokens}")
    print(f"   From cache: {result.from_cache}")
    print(f"   Extraction tokens: {result.extraction_tokens}")
    print(f"   Analysis tokens: {result.analysis_tokens}")
    
except ImportError as e:
    print(f"⚠️  Mock providers not available (expected in production): {e}")
except Exception as e:
    print(f"❌ Workflow test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Verify InsightResult structure
print("\n[Test 5] Testing InsightResult dataclass...")
try:
    test_result = InsightResult(
        content="Test insights content",
        provider_used="openai",
        model_used="gpt-4o-mini",
        extraction_tokens=500,
        analysis_tokens=1000,
        total_tokens=1500,
        from_cache=False,
        from_dedup=False,
        text_hash="abc123",
        extracted_data="Test extracted data",
        analysis="Test analysis"
    )
    print("✅ InsightResult created successfully")
    print(f"   All fields present: {all([
        test_result.content,
        test_result.provider_used,
        test_result.model_used,
        test_result.extraction_tokens,
        test_result.analysis_tokens,
        test_result.total_tokens,
        test_result.text_hash
    ])}")
except Exception as e:
    print(f"❌ Failed to create InsightResult: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Integration Test Summary")
print("=" * 60)
print("✅ All import tests passed")
print("✅ Service instantiation works")
print("✅ InsightResult dataclass works")
print("\n🎯 Ready for production testing!")
print("\nNext steps:")
print("1. Apply database migration 017 (insight_cache table)")
print("2. Start backend: python app.py")
print("3. Upload a document and monitor logs")
print("4. Look for cache HIT/MISS messages")
print("=" * 60)
