"""
Unit Tests for LangMem InsightMemory Cache.

Tests cache operations, statistics, TTL, and eviction policies.
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from adapters.driven.memory.insight_memory import (
    InsightMemory,
    CachedInsight,
    CacheStats,
    compute_text_hash,
    normalize_text_for_hash
)


# ============================================================================
# Test Utilities
# ============================================================================

class TestUtilities:
    """Test utility functions."""
    
    def test_compute_text_hash(self):
        """Test that same text produces same hash."""
        text1 = "Hello world"
        text2 = "Hello world"
        
        hash1 = compute_text_hash(text1)
        hash2 = compute_text_hash(text2)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex chars
    
    def test_compute_text_hash_different(self):
        """Test that different text produces different hash."""
        text1 = "Hello world"
        text2 = "Goodbye world"
        
        hash1 = compute_text_hash(text1)
        hash2 = compute_text_hash(text2)
        
        assert hash1 != hash2
    
    def test_normalize_text_for_hash(self):
        """Test text normalization for consistent hashing."""
        # Different whitespace
        text1 = "Hello  world\n\n"
        text2 = "hello world"
        
        norm1 = normalize_text_for_hash(text1)
        norm2 = normalize_text_for_hash(text2)
        
        assert norm1 == norm2
        
        # Verify hash is same after normalization
        hash1 = compute_text_hash(norm1)
        hash2 = compute_text_hash(norm2)
        assert hash1 == hash2


# ============================================================================
# Test CachedInsight
# ============================================================================

class TestCachedInsight:
    """Test CachedInsight dataclass."""
    
    def test_cached_insight_creation(self):
        """Test creating CachedInsight."""
        cached = CachedInsight(
            text_hash="abc123",
            extracted_data="## Metadata\nTest",
            analysis="## Significance\nTest",
            full_text="Combined",
            provider_used="openai",
            model_used="gpt-4o",
            extraction_tokens=100,
            analysis_tokens=50,
            total_tokens=150,
            cached_at=datetime.now()
        )
        
        assert cached.text_hash == "abc123"
        assert cached.total_tokens == 150
        assert isinstance(cached.cached_at, datetime)
        assert cached.hit_count == 0
    
    def test_cached_insight_to_dict(self):
        """Test serialization to dict."""
        now = datetime.now()
        cached = CachedInsight(
            text_hash="abc123",
            extracted_data="data",
            analysis="analysis",
            full_text="full",
            provider_used="openai",
            model_used="gpt-4o",
            extraction_tokens=100,
            analysis_tokens=50,
            total_tokens=150,
            cached_at=now
        )
        
        data = cached.to_dict()
        
        assert data['text_hash'] == "abc123"
        assert data['total_tokens'] == 150
        assert isinstance(data['cached_at'], str)  # Should be ISO string
        assert data.get('hit_count', 0) == 0
    
    def test_cached_insight_from_dict(self):
        """Test deserialization from dict."""
        data = {
            'text_hash': 'abc123',
            'extracted_data': 'data',
            'analysis': 'analysis',
            'full_text': 'full',
            'provider_used': 'openai',
            'model_used': 'gpt-4o',
            'extraction_tokens': 100,
            'analysis_tokens': 50,
            'total_tokens': 150,
            'cached_at': '2026-03-31T10:00:00',
            'hit_count': 3
        }
        
        cached = CachedInsight.from_dict(data)
        
        assert cached.text_hash == 'abc123'
        assert cached.total_tokens == 150
        assert isinstance(cached.cached_at, datetime)
        assert cached.hit_count == 3


# ============================================================================
# Test InsightMemory Basic Operations
# ============================================================================

class TestInsightMemoryBasic:
    """Test basic cache operations."""
    
    @pytest.fixture
    def memory(self):
        """Create fresh memory instance for each test."""
        return InsightMemory(ttl_days=7, max_cache_size=100, backend="memory")
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, memory):
        """Test cache miss returns None."""
        result = await memory.get("nonexistent_hash")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_store_and_get(self, memory):
        """Test storing and retrieving from cache."""
        text_hash = "abc123"
        
        await memory.store(
            text_hash=text_hash,
            extracted_data="## Metadata\nTest",
            analysis="## Significance\nTest",
            full_text="Combined",
            provider_used="openai",
            model_used="gpt-4o",
            extraction_tokens=100,
            analysis_tokens=50
        )
        
        # Retrieve
        cached = await memory.get(text_hash)
        
        assert cached is not None
        assert cached.text_hash == text_hash
        assert cached.total_tokens == 150
        assert cached.provider_used == "openai"
    
    @pytest.mark.asyncio
    async def test_invalidate(self, memory):
        """Test invalidating cache entry."""
        text_hash = "abc123"
        
        # Store
        await memory.store(
            text_hash=text_hash,
            extracted_data="data",
            analysis="analysis",
            full_text="full",
            provider_used="openai",
            model_used="gpt-4o",
            extraction_tokens=100,
            analysis_tokens=50
        )
        
        # Verify stored
        cached = await memory.get(text_hash)
        assert cached is not None
        
        # Invalidate
        await memory.invalidate(text_hash)
        
        # Verify removed
        cached = await memory.get(text_hash)
        assert cached is None
    
    @pytest.mark.asyncio
    async def test_clear(self, memory):
        """Test clearing all cache."""
        # Store multiple entries
        for i in range(5):
            await memory.store(
                text_hash=f"hash_{i}",
                extracted_data="data",
                analysis="analysis",
                full_text="full",
                provider_used="openai",
                model_used="gpt-4o",
                extraction_tokens=100,
                analysis_tokens=50
            )
        
        # Clear
        await memory.clear()
        
        # Verify all removed
        for i in range(5):
            cached = await memory.get(f"hash_{i}")
            assert cached is None


# ============================================================================
# Test TTL (Time-To-Live)
# ============================================================================

class TestInsightMemoryTTL:
    """Test TTL expiration."""
    
    @pytest.mark.asyncio
    async def test_expired_entry_returns_none(self):
        """Test that expired entries are automatically invalidated."""
        memory = InsightMemory(ttl_days=7, backend="memory")
        text_hash = "abc123"
        
        # Store entry
        await memory.store(
            text_hash=text_hash,
            extracted_data="data",
            analysis="analysis",
            full_text="full",
            provider_used="openai",
            model_used="gpt-4o",
            extraction_tokens=100,
            analysis_tokens=50
        )
        
        # Manually set cached_at to 8 days ago (expired)
        cached = memory._cache[text_hash]
        cached.cached_at = datetime.now() - timedelta(days=8)
        
        # Try to retrieve (should return None and auto-invalidate)
        result = await memory.get(text_hash)
        
        assert result is None
        # Verify removed from cache
        assert text_hash not in memory._cache


# ============================================================================
# Test Statistics
# ============================================================================

class TestInsightMemoryStatistics:
    """Test cache statistics tracking."""
    
    @pytest.fixture
    def memory(self):
        """Create fresh memory instance."""
        return InsightMemory(ttl_days=7, backend="memory")
    
    @pytest.mark.asyncio
    async def test_cache_hit_statistics(self, memory):
        """Test that cache hits are tracked."""
        text_hash = "abc123"
        
        # Store
        await memory.store(
            text_hash=text_hash,
            extracted_data="data",
            analysis="analysis",
            full_text="full",
            provider_used="openai",
            model_used="gpt-4o",
            extraction_tokens=100,
            analysis_tokens=50
        )
        
        # Get (cache hit)
        await memory.get(text_hash)
        
        stats = memory.get_stats()
        assert stats.total_requests == 1
        assert stats.cache_hits == 1
        assert stats.cache_misses == 0
        assert stats.hit_rate == 1.0
        assert stats.tokens_saved == 150
    
    @pytest.mark.asyncio
    async def test_cache_miss_statistics(self, memory):
        """Test that cache misses are tracked."""
        # Get non-existent (cache miss)
        await memory.get("nonexistent")
        
        stats = memory.get_stats()
        assert stats.total_requests == 1
        assert stats.cache_hits == 0
        assert stats.cache_misses == 1
        assert stats.hit_rate == 0.0
    
    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self, memory):
        """Test hit rate calculation."""
        text_hash = "abc123"
        
        # Store
        await memory.store(
            text_hash=text_hash,
            extracted_data="data",
            analysis="analysis",
            full_text="full",
            provider_used="openai",
            model_used="gpt-4o",
            extraction_tokens=100,
            analysis_tokens=50
        )
        
        # 2 hits, 1 miss
        await memory.get(text_hash)  # Hit
        await memory.get(text_hash)  # Hit
        await memory.get("nonexistent")  # Miss
        
        stats = memory.get_stats()
        assert stats.total_requests == 3
        assert stats.cache_hits == 2
        assert stats.cache_misses == 1
        assert abs(stats.hit_rate - 0.666666) < 0.01  # ~66.7%
    
    def test_reset_statistics(self, memory):
        """Test resetting statistics."""
        # Manually set some stats
        memory._stats['total_requests'] = 10
        memory._stats['cache_hits'] = 5
        
        # Reset
        memory.reset_stats()
        
        # Verify reset
        stats = memory.get_stats()
        assert stats.total_requests == 0
        assert stats.cache_hits == 0


# ============================================================================
# Test Eviction Policy (LRU)
# ============================================================================

class TestInsightMemoryEviction:
    """Test LRU eviction when exceeding max size."""
    
    @pytest.mark.asyncio
    async def test_eviction_when_exceeding_max_size(self):
        """Test that oldest entry is evicted when max_size exceeded."""
        memory = InsightMemory(ttl_days=7, max_cache_size=3, backend="memory")
        
        # Store 3 entries (at max)
        for i in range(3):
            await memory.store(
                text_hash=f"hash_{i}",
                extracted_data="data",
                analysis="analysis",
                full_text="full",
                provider_used="openai",
                model_used="gpt-4o",
                extraction_tokens=100,
                analysis_tokens=50
            )
            # Small delay to ensure different timestamps
            await asyncio.sleep(0.01)
        
        # Store 4th entry (should evict oldest)
        await memory.store(
            text_hash="hash_3",
            extracted_data="data",
            analysis="analysis",
            full_text="full",
            provider_used="openai",
            model_used="gpt-4o",
            extraction_tokens=100,
            analysis_tokens=50
        )
        
        # Verify oldest (hash_0) was evicted
        cached = await memory.get("hash_0")
        assert cached is None
        
        # Verify others still exist
        for i in range(1, 4):
            cached = await memory.get(f"hash_{i}")
            assert cached is not None


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
