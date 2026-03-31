"""
Insights Worker Service - Application Service for Insights Generation.

This service orchestrates the complete insights generation workflow:
- LangMem cache check (PostgreSQL-backed)
- Text hash deduplication
- LangGraph workflow execution
- Provider fallback handling
- Metrics tracking (tokens, provider, cache hits)

Following Hexagonal Architecture:
- Core application service (use case orchestration)
- Uses ports for external dependencies
- Coordinates LangGraph workflow + LangMem cache
"""

import logging
import hashlib
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from adapters.driven.llm.graphs.insights_graph import run_insights_workflow
from adapters.driven.memory.insight_memory import InsightMemory, compute_text_hash

logger = logging.getLogger(__name__)


@dataclass
class InsightResult:
    """
    Result from insights generation workflow.
    
    Contains insights text, metadata, and cache/dedup information.
    """
    # Content
    content: str  # Full insights text (extraction + analysis combined)
    
    # Provider metadata
    provider_used: str
    model_used: str
    extraction_tokens: int
    analysis_tokens: int
    total_tokens: int
    
    # Cache/dedup information
    from_cache: bool  # True if retrieved from LangMem cache
    from_dedup: bool  # True if reused from existing news_item via text_hash
    text_hash: str    # SHA256 hash of context (for deduplication)
    
    # Structured data (optional, for future knowledge graph)
    extracted_data: Optional[str] = None
    analysis: Optional[str] = None


class InsightsWorkerService:
    """
    Application service for insights generation.
    
    Orchestrates the complete workflow:
    1. Check LangMem cache (PostgreSQL-backed)
    2. If cache miss, run LangGraph workflow
    3. Store result in cache
    4. Return structured result with metrics
    
    Usage:
        service = InsightsWorkerService()
        result = await service.generate_insights(
            news_item_id="123",
            document_id="doc_456",
            context="Article text...",
            title="Article title",
            max_attempts=3
        )
    """
    
    def __init__(
        self,
        cache_backend: str = "postgres",
        cache_ttl_days: int = 30,  # TTL in days
        cache_max_size: int = 10000
    ):
        """
        Initialize insights worker service.
        
        Args:
            cache_backend: Cache backend ("memory", "postgres", "redis")
            cache_ttl_days: Time-to-live for cache entries (days)
            cache_max_size: Maximum number of entries in cache
        """
        self.cache = InsightMemory(
            backend=cache_backend,
            ttl_days=cache_ttl_days,
            max_cache_size=cache_max_size
        )
        logger.info(
            f"✅ InsightsWorkerService initialized: "
            f"backend={cache_backend}, ttl={cache_ttl_days}d, max_size={cache_max_size}"
        )
    
    async def generate_insights(
        self,
        news_item_id: str,
        document_id: str,
        context: str,
        title: str = "",
        max_attempts: int = 3
    ) -> InsightResult:
        """
        Generate insights for a news article.
        
        Workflow:
        1. Compute text_hash (for deduplication)
        2. Check LangMem cache (saves API calls + $)
        3. If cache miss, run LangGraph workflow
        4. Store result in cache
        5. Return structured result with metrics
        
        Args:
            news_item_id: Unique ID for news item
            document_id: Document ID
            context: Article text (from Qdrant chunks)
            title: Article title
            max_attempts: Maximum retry attempts per step
        
        Returns:
            InsightResult with content, metadata, and cache info
        
        Raises:
            Exception: If workflow fails after max retries
        """
        # Compute text hash for cache key
        text_hash = compute_text_hash(context)
        
        logger.info(
            f"📋 [InsightsWorkerService] Starting workflow: "
            f"news_item={news_item_id}, doc={document_id}, "
            f"context_len={len(context)}, hash={text_hash[:16]}..."
        )
        
        # STEP 1: Check LangMem cache
        cached = await self.cache.get(text_hash)
        if cached:
            logger.info(
                f"♻️ [InsightsWorkerService] Cache HIT: "
                f"provider={cached.provider_used}, model={cached.model_used}, "
                f"total_tokens={cached.total_tokens}, hit_count={cached.hit_count}"
            )
            
            return InsightResult(
                content=cached.full_text,
                provider_used=cached.provider_used,
                model_used=cached.model_used,
                extraction_tokens=cached.extraction_tokens,
                analysis_tokens=cached.analysis_tokens,
                total_tokens=cached.total_tokens,
                from_cache=True,
                from_dedup=False,
                text_hash=text_hash,
                extracted_data=cached.extracted_data,
                analysis=cached.analysis
            )
        
        logger.info(f"💾 [InsightsWorkerService] Cache MISS - running workflow")
        
        # STEP 2: Run LangGraph workflow (extraction + analysis + validation + retry)
        workflow_result = await run_insights_workflow(
            news_item_id=news_item_id,
            document_id=document_id,
            context=context,
            title=title,
            max_attempts=max_attempts
        )
        
        # Check if workflow succeeded
        if not workflow_result['success']:
            error_step = workflow_result.get('error_step', 'unknown')
            error_msg = workflow_result.get('error', 'Workflow failed')
            logger.error(
                f"❌ [InsightsWorkerService] Workflow failed: "
                f"step={error_step}, error={error_msg}"
            )
            raise Exception(f"Workflow failed at {error_step}: {error_msg}")
        
        # Extract results
        extracted_data = workflow_result['extracted_data']
        analysis = workflow_result['analysis']
        full_text = workflow_result['full_text']
        provider_used = workflow_result['provider_used']
        model_used = workflow_result['model_used']
        extraction_tokens = workflow_result['extraction_tokens']
        analysis_tokens = workflow_result['analysis_tokens']
        total_tokens = extraction_tokens + analysis_tokens
        
        logger.info(
            f"✅ [InsightsWorkerService] Workflow complete: "
            f"provider={provider_used}, model={model_used}, "
            f"tokens={total_tokens} (extract={extraction_tokens}, analyze={analysis_tokens})"
        )
        
        # STEP 3: Store in cache for future reuse
        try:
            await self.cache.store(
                text_hash=text_hash,
                extracted_data=extracted_data,
                analysis=analysis,
                full_text=full_text,
                provider_used=provider_used,
                model_used=model_used,
                extraction_tokens=extraction_tokens,
                analysis_tokens=analysis_tokens
            )
            logger.info(f"💾 [InsightsWorkerService] Stored in cache: hash={text_hash[:16]}...")
        except Exception as e:
            # Cache storage failure shouldn't fail the workflow
            logger.warning(f"⚠️ [InsightsWorkerService] Cache storage failed: {e}")
        
        # Return structured result
        return InsightResult(
            content=full_text,
            provider_used=provider_used,
            model_used=model_used,
            extraction_tokens=extraction_tokens,
            analysis_tokens=analysis_tokens,
            total_tokens=total_tokens,
            from_cache=False,
            from_dedup=False,
            text_hash=text_hash,
            extracted_data=extracted_data,
            analysis=analysis
        )
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with hits, misses, hit_rate, total_entries
        """
        return self.cache.get_stats()
    
    async def cleanup_expired_cache(self) -> int:
        """
        Cleanup expired cache entries.
        
        Returns:
            Number of entries cleaned up
        """
        return await self.cache.cleanup_expired()


# Singleton instance (lazy initialization)
_insights_worker_service: Optional[InsightsWorkerService] = None


def get_insights_worker_service(
    cache_backend: str = "postgres",
    cache_ttl_days: int = 30,
    cache_max_size: int = 10000
) -> InsightsWorkerService:
    """
    Get or create singleton InsightsWorkerService instance.
    
    Args:
        cache_backend: Cache backend ("memory", "postgres", "redis")
        cache_ttl_days: Cache TTL in days (default: 30 days)
        cache_max_size: Max cache entries (default: 10000)
    
    Returns:
        InsightsWorkerService instance
    """
    global _insights_worker_service
    if _insights_worker_service is None:
        _insights_worker_service = InsightsWorkerService(
            cache_backend=cache_backend,
            cache_ttl_days=cache_ttl_days,
            cache_max_size=cache_max_size
        )
    return _insights_worker_service
