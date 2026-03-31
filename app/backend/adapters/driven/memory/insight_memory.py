"""
LangMem Memory Management for Insights Caching.

This module implements memory and caching strategies for LLM-generated insights,
reducing token usage and improving response times.

Architecture: Hexagonal (Adapter - Driven - Memory)
Integration: Uses PostgreSQL as cache backend, future support for Redis
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class CachedInsight:
    """
    Cached insight result.
    
    Stores the complete insight data for reuse.
    """
    text_hash: str
    extracted_data: str
    analysis: str
    full_text: str
    provider_used: str
    model_used: str
    extraction_tokens: int
    analysis_tokens: int
    total_tokens: int
    cached_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert datetime to ISO string
        data['cached_at'] = self.cached_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CachedInsight':
        """Create from dictionary (deserialization)."""
        # Convert ISO string to datetime
        if isinstance(data.get('cached_at'), str):
            data['cached_at'] = datetime.fromisoformat(data['cached_at'])
        return cls(**data)


@dataclass
class CacheStats:
    """
    Cache statistics for monitoring.
    """
    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    tokens_saved: int
    
    def __str__(self) -> str:
        return (
            f"CacheStats(total={self.total_requests}, "
            f"hits={self.cache_hits}, misses={self.cache_misses}, "
            f"hit_rate={self.hit_rate:.1%}, tokens_saved={self.tokens_saved})"
        )


# ============================================================================
# Memory Manager
# ============================================================================

class InsightMemory:
    """
    Memory manager for insight caching and deduplication.
    
    Features:
    - Text-based deduplication (sha256 hash of normalized text)
    - Configurable TTL (time-to-live) for cache entries
    - Cache statistics tracking
    - Token savings calculation
    
    Backend: PostgreSQL (current), Redis (future)
    
    Usage:
        >>> memory = InsightMemory(ttl_days=7)
        >>> 
        >>> # Check cache
        >>> cached = await memory.get("abc123...")
        >>> if cached:
        ...     return cached  # Cache hit
        >>> 
        >>> # Generate new
        >>> result = await chain.run(...)
        >>> 
        >>> # Store in cache
        >>> await memory.store("abc123...", result)
    """
    
    def __init__(
        self,
        ttl_days: int = 7,
        max_cache_size: int = 10000,
        backend: str = "memory"  # "memory", "postgres", or "redis"
    ):
        """
        Initialize memory manager.
        
        Args:
            ttl_days: Time-to-live for cache entries (days)
            max_cache_size: Maximum number of cached entries
            backend: Cache backend ("memory", "postgres", "redis")
        """
        self.ttl_days = ttl_days
        self.max_cache_size = max_cache_size
        self.backend = backend
        
        # In-memory cache (fallback)
        self._cache: Dict[str, CachedInsight] = {}
        
        # Statistics
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'tokens_saved': 0
        }
        
        logger.info(
            f"📦 InsightMemory initialized: "
            f"ttl={ttl_days}d, max_size={max_cache_size}, backend={backend}"
        )
    
    async def get(self, text_hash: str) -> Optional[CachedInsight]:
        """
        Get cached insight by text hash.
        
        Args:
            text_hash: SHA256 hash of normalized text
        
        Returns:
            CachedInsight if found and not expired, None otherwise
        """
        self._stats['total_requests'] += 1
        
        # Try backend
        if self.backend == "postgres":
            cached = await self._get_from_postgres(text_hash)
        elif self.backend == "redis":
            cached = await self._get_from_redis(text_hash)
        else:
            # In-memory fallback
            cached = self._cache.get(text_hash)
        
        if cached:
            # Check expiration
            age = datetime.now() - cached.cached_at
            if age > timedelta(days=self.ttl_days):
                logger.debug(f"⏰ Cache expired for hash={text_hash[:8]}... (age={age})")
                await self.invalidate(text_hash)
                self._stats['cache_misses'] += 1
                return None
            
            # Cache hit
            self._stats['cache_hits'] += 1
            self._stats['tokens_saved'] += cached.total_tokens
            
            logger.info(
                f"✅ Cache HIT for hash={text_hash[:8]}...: "
                f"saved {cached.total_tokens} tokens, "
                f"provider={cached.provider_used}"
            )
            return cached
        
        # Cache miss
        self._stats['cache_misses'] += 1
        logger.debug(f"❌ Cache MISS for hash={text_hash[:8]}...")
        return None
    
    async def store(
        self,
        text_hash: str,
        extracted_data: str,
        analysis: str,
        full_text: str,
        provider_used: str,
        model_used: str,
        extraction_tokens: int,
        analysis_tokens: int
    ) -> None:
        """
        Store insight in cache.
        
        Args:
            text_hash: SHA256 hash of normalized text
            extracted_data: Structured extraction output
            analysis: Analysis output
            full_text: Combined extraction + analysis
            provider_used: LLM provider name
            model_used: LLM model name
            extraction_tokens: Tokens used in extraction
            analysis_tokens: Tokens used in analysis
        """
        cached = CachedInsight(
            text_hash=text_hash,
            extracted_data=extracted_data,
            analysis=analysis,
            full_text=full_text,
            provider_used=provider_used,
            model_used=model_used,
            extraction_tokens=extraction_tokens,
            analysis_tokens=analysis_tokens,
            total_tokens=extraction_tokens + analysis_tokens,
            cached_at=datetime.now()
        )
        
        # Store in backend
        if self.backend == "postgres":
            await self._store_in_postgres(cached)
        elif self.backend == "redis":
            await self._store_in_redis(cached)
        else:
            # In-memory fallback
            self._cache[text_hash] = cached
            
            # Evict oldest if exceeds max size
            if len(self._cache) > self.max_cache_size:
                # Remove oldest entry
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].cached_at)
                del self._cache[oldest_key]
                logger.debug(f"🗑️ Evicted oldest cache entry: {oldest_key[:8]}...")
        
        logger.info(
            f"💾 Stored in cache: hash={text_hash[:8]}..., "
            f"tokens={cached.total_tokens}, provider={provider_used}"
        )
    
    async def invalidate(self, text_hash: str) -> None:
        """
        Invalidate (remove) cached insight.
        
        Args:
            text_hash: SHA256 hash of normalized text
        """
        if self.backend == "postgres":
            await self._invalidate_in_postgres(text_hash)
        elif self.backend == "redis":
            await self._invalidate_in_redis(text_hash)
        else:
            # In-memory fallback
            self._cache.pop(text_hash, None)
        
        logger.debug(f"🗑️ Invalidated cache entry: {text_hash[:8]}...")
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        if self.backend == "postgres":
            await self._clear_postgres()
        elif self.backend == "redis":
            await self._clear_redis()
        else:
            # In-memory fallback
            self._cache.clear()
        
        logger.info("🗑️ Cache cleared")
    
    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.
        
        Returns:
            CacheStats with current metrics
        """
        total = self._stats['total_requests']
        hits = self._stats['cache_hits']
        misses = self._stats['cache_misses']
        hit_rate = (hits / total) if total > 0 else 0.0
        
        return CacheStats(
            total_requests=total,
            cache_hits=hits,
            cache_misses=misses,
            hit_rate=hit_rate,
            tokens_saved=self._stats['tokens_saved']
        )
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired cache entries.
        
        Removes entries older than TTL.
        
        Returns:
            Number of entries removed
        
        Example:
            >>> memory = InsightMemory(ttl_days=7, backend="postgres")
            >>> removed = await memory.cleanup_expired()
            >>> print(f"Removed {removed} expired entries")
        """
        if self.backend == "postgres":
            return await self._cleanup_expired_postgres()
        elif self.backend == "redis":
            # Redis handles TTL automatically
            return 0
        else:
            # In-memory: manually remove expired
            removed = 0
            now = datetime.now()
            expired_keys = []
            
            for text_hash, cached in self._cache.items():
                age = now - cached.cached_at
                if age > timedelta(days=self.ttl_days):
                    expired_keys.append(text_hash)
            
            for key in expired_keys:
                del self._cache[key]
                removed += 1
            
            if removed > 0:
                logger.info(f"🗑️ Cleaned up {removed} expired entries (TTL={self.ttl_days}d)")
            
            return removed
    
    async def _cleanup_expired_postgres(self) -> int:
        """Clean up expired entries in PostgreSQL."""
        import psycopg2
        import os
        
        try:
            # Get database connection
            db_url = os.getenv("DATABASE_URL") or self._build_database_url()
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            
            # Delete expired entries
            cursor.execute("""
                DELETE FROM insight_cache
                WHERE cached_at < NOW() - INTERVAL '%s days'
            """, (self.ttl_days,))
            
            rows_deleted = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            
            if rows_deleted > 0:
                logger.info(f"🗑️ Cleaned up {rows_deleted} expired entries from PostgreSQL (TTL={self.ttl_days}d)")
            
            return rows_deleted
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up expired entries: {e}", exc_info=True)
            return 0
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'tokens_saved': 0
        }
        logger.info("📊 Cache stats reset")
    
    # ========================================================================
    # Backend Implementations
    # ========================================================================
    
    async def _get_from_postgres(self, text_hash: str) -> Optional[CachedInsight]:
        """Get from PostgreSQL backend."""
        import psycopg2
        import psycopg2.extras
        import os
        
        try:
            # Get database connection
            db_url = os.getenv("DATABASE_URL") or self._build_database_url()
            conn = psycopg2.connect(db_url)
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            cursor = conn.cursor()
            
            # Query with TTL check
            cursor.execute("""
                SELECT 
                    text_hash,
                    extracted_data,
                    analysis,
                    full_text,
                    provider_used,
                    model_used,
                    extraction_tokens,
                    analysis_tokens,
                    total_tokens,
                    cached_at,
                    hit_count
                FROM insight_cache
                WHERE text_hash = %s
                  AND cached_at > NOW() - INTERVAL '%s days'
            """, (text_hash, self.ttl_days))
            
            row = cursor.fetchone()
            
            if row:
                # Update last_accessed_at and hit_count
                cursor.execute("""
                    UPDATE insight_cache
                    SET last_accessed_at = NOW(),
                        hit_count = hit_count + 1
                    WHERE text_hash = %s
                """, (text_hash,))
                conn.commit()
                
                # Convert to CachedInsight
                cached = CachedInsight(
                    text_hash=row['text_hash'],
                    extracted_data=row['extracted_data'],
                    analysis=row['analysis'],
                    full_text=row['full_text'],
                    provider_used=row['provider_used'],
                    model_used=row['model_used'],
                    extraction_tokens=row['extraction_tokens'],
                    analysis_tokens=row['analysis_tokens'],
                    total_tokens=row['total_tokens'],
                    cached_at=row['cached_at']
                )
                
                cursor.close()
                conn.close()
                
                logger.debug(f"📥 Retrieved from PostgreSQL: {text_hash[:8]}... (hit_count={row['hit_count']+1})")
                return cached
            
            cursor.close()
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting from PostgreSQL: {e}", exc_info=True)
            return None
    
    def _build_database_url(self) -> str:
        """Build database URL from environment variables."""
        import os
        from urllib.parse import quote_plus
        
        explicit = os.getenv("DATABASE_URL")
        if explicit:
            return explicit
        
        user = quote_plus(os.getenv("POSTGRES_USER", "raguser"))
        password = quote_plus(os.getenv("POSTGRES_PASSWORD", "ragpass"))
        host = os.getenv("POSTGRES_HOST", "postgres")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "rag_enterprise")
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"
    
    async def _store_in_postgres(self, cached: CachedInsight) -> None:
        """Store in PostgreSQL backend."""
        import psycopg2
        import psycopg2.extras
        import os
        
        try:
            # Get database connection
            db_url = os.getenv("DATABASE_URL") or self._build_database_url()
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            
            # Upsert (INSERT ... ON CONFLICT UPDATE)
            cursor.execute("""
                INSERT INTO insight_cache (
                    text_hash,
                    extracted_data,
                    analysis,
                    full_text,
                    provider_used,
                    model_used,
                    extraction_tokens,
                    analysis_tokens,
                    total_tokens,
                    cached_at,
                    last_accessed_at,
                    hit_count
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (text_hash) DO UPDATE SET
                    extracted_data = EXCLUDED.extracted_data,
                    analysis = EXCLUDED.analysis,
                    full_text = EXCLUDED.full_text,
                    provider_used = EXCLUDED.provider_used,
                    model_used = EXCLUDED.model_used,
                    extraction_tokens = EXCLUDED.extraction_tokens,
                    analysis_tokens = EXCLUDED.analysis_tokens,
                    total_tokens = EXCLUDED.total_tokens,
                    cached_at = EXCLUDED.cached_at,
                    last_accessed_at = EXCLUDED.last_accessed_at,
                    hit_count = 0
            """, (
                cached.text_hash,
                cached.extracted_data,
                cached.analysis,
                cached.full_text,
                cached.provider_used,
                cached.model_used,
                cached.extraction_tokens,
                cached.analysis_tokens,
                cached.total_tokens,
                cached.cached_at,
                cached.cached_at,  # last_accessed_at same as cached_at initially
                0  # hit_count starts at 0
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.debug(f"💾 Stored in PostgreSQL: {cached.text_hash[:8]}...")
            
        except Exception as e:
            logger.error(f"❌ Error storing in PostgreSQL: {e}", exc_info=True)
    
    async def _invalidate_in_postgres(self, text_hash: str) -> None:
        """Invalidate in PostgreSQL backend."""
        import psycopg2
        import os
        
        try:
            # Get database connection
            db_url = os.getenv("DATABASE_URL") or self._build_database_url()
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            
            # Delete entry
            cursor.execute("""
                DELETE FROM insight_cache
                WHERE text_hash = %s
            """, (text_hash,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.debug(f"🗑️ Invalidated in PostgreSQL: {text_hash[:8]}...")
            
        except Exception as e:
            logger.error(f"❌ Error invalidating in PostgreSQL: {e}", exc_info=True)
    
    async def _clear_postgres(self) -> None:
        """Clear PostgreSQL cache."""
        import psycopg2
        import os
        
        try:
            # Get database connection
            db_url = os.getenv("DATABASE_URL") or self._build_database_url()
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            
            # Delete all entries
            cursor.execute("DELETE FROM insight_cache")
            
            rows_deleted = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"🗑️ Cleared PostgreSQL cache: {rows_deleted} entries deleted")
            
        except Exception as e:
            logger.error(f"❌ Error clearing PostgreSQL cache: {e}", exc_info=True)
    
    async def _get_from_redis(self, text_hash: str) -> Optional[CachedInsight]:
        """Get from Redis backend."""
        # TODO: Implement Redis GET
        # redis.get(f"insight_cache:{text_hash}")
        logger.debug(f"TODO: _get_from_redis({text_hash[:8]}...)")
        return None
    
    async def _store_in_redis(self, cached: CachedInsight) -> None:
        """Store in Redis backend."""
        # TODO: Implement Redis SET with TTL
        # redis.setex(f"insight_cache:{text_hash}", ttl_seconds, json.dumps(cached.to_dict()))
        logger.debug(f"TODO: _store_in_redis({cached.text_hash[:8]}...)")
    
    async def _invalidate_in_redis(self, text_hash: str) -> None:
        """Invalidate in Redis backend."""
        # TODO: Implement Redis DEL
        # redis.delete(f"insight_cache:{text_hash}")
        logger.debug(f"TODO: _invalidate_in_redis({text_hash[:8]}...)")
    
    async def _clear_redis(self) -> None:
        """Clear Redis cache."""
        # TODO: Implement Redis pattern delete
        # for key in redis.scan_iter("insight_cache:*"):
        #     redis.delete(key)
        logger.debug("TODO: _clear_redis()")


# ============================================================================
# Utilities
# ============================================================================

def compute_text_hash(text: str) -> str:
    """
    Compute SHA256 hash of text for cache key.
    
    Args:
        text: Text to hash
    
    Returns:
        Hexadecimal SHA256 hash
    
    Example:
        >>> hash1 = compute_text_hash("Hello world")
        >>> hash2 = compute_text_hash("Hello world")
        >>> assert hash1 == hash2
    """
    # Normalize text (lowercase, strip whitespace)
    normalized = text.lower().strip()
    
    # Compute hash
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def normalize_text_for_hash(text: str) -> str:
    """
    Normalize text before hashing for better deduplication.
    
    Removes:
    - Extra whitespace
    - Leading/trailing spaces
    - Normalizes line breaks
    
    Args:
        text: Text to normalize
    
    Returns:
        Normalized text
    
    Example:
        >>> text1 = "Hello  world\\n\\n"
        >>> text2 = "hello world"
        >>> hash1 = compute_text_hash(normalize_text_for_hash(text1))
        >>> hash2 = compute_text_hash(normalize_text_for_hash(text2))
        >>> assert hash1 == hash2
    """
    import re
    
    # Lowercase
    text = text.lower()
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Strip
    text = text.strip()
    
    return text


# ============================================================================
# Global Instance (Singleton)
# ============================================================================

_global_memory: Optional[InsightMemory] = None


def get_insight_memory(
    ttl_days: int = 7,
    max_cache_size: int = 10000,
    backend: str = "memory"
) -> InsightMemory:
    """
    Get global insight memory instance (singleton pattern).
    
    Args:
        ttl_days: Time-to-live for cache entries (days)
        max_cache_size: Maximum number of cached entries
        backend: Cache backend ("memory", "postgres", "redis")
    
    Returns:
        InsightMemory singleton instance
    
    Example:
        >>> memory = get_insight_memory()
        >>> cached = await memory.get(text_hash)
    """
    global _global_memory
    
    if _global_memory is None:
        _global_memory = InsightMemory(
            ttl_days=ttl_days,
            max_cache_size=max_cache_size,
            backend=backend
        )
    
    return _global_memory
