"""
Migration 017: Create insight_cache table for LangMem persistence.

Enables persistent caching of LLM-generated insights with TTL support.
"""

import logging

logger = logging.getLogger(__name__)


def apply(cursor):
    """
    Create insight_cache table for storing cached insights.
    
    Schema:
    - text_hash: SHA256 hash of normalized text (unique key for deduplication)
    - extracted_data: Structured extraction output (## Metadata, ## Actors, etc.)
    - analysis: Analysis output (## Significance, ## Context, etc.)
    - full_text: Combined extraction + analysis
    - provider_used: LLM provider name (openai, ollama, perplexity)
    - model_used: Model name (gpt-4o, mistral, etc.)
    - extraction_tokens: Tokens used in extraction step
    - analysis_tokens: Tokens used in analysis step
    - total_tokens: Sum of extraction + analysis tokens
    - cached_at: Timestamp when cached (for TTL)
    - last_accessed_at: Timestamp of last cache hit (for LRU)
    - hit_count: Number of times this entry was retrieved
    """
    
    logger.info("Creating insight_cache table...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insight_cache (
            -- Primary key: text hash (SHA256)
            text_hash VARCHAR(64) PRIMARY KEY,
            
            -- Cached insight content
            extracted_data TEXT NOT NULL,
            analysis TEXT NOT NULL,
            full_text TEXT NOT NULL,
            
            -- Provider metadata
            provider_used VARCHAR(50) NOT NULL,
            model_used VARCHAR(100) NOT NULL,
            
            -- Token usage (for cost tracking)
            extraction_tokens INTEGER NOT NULL DEFAULT 0,
            analysis_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            
            -- Cache management
            cached_at TIMESTAMP NOT NULL DEFAULT NOW(),
            last_accessed_at TIMESTAMP NOT NULL DEFAULT NOW(),
            hit_count INTEGER NOT NULL DEFAULT 0,
            
            -- Indexes for performance
            CONSTRAINT insight_cache_tokens_check CHECK (total_tokens >= 0),
            CONSTRAINT insight_cache_hit_count_check CHECK (hit_count >= 0)
        );
    """)
    
    logger.info("Creating indexes on insight_cache...")
    
    # Index for TTL queries (find expired entries)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_insight_cache_cached_at 
        ON insight_cache(cached_at);
    """)
    
    # Index for LRU queries (find least recently used)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_insight_cache_last_accessed 
        ON insight_cache(last_accessed_at);
    """)
    
    # Index for provider statistics
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_insight_cache_provider 
        ON insight_cache(provider_used);
    """)
    
    logger.info("✅ insight_cache table created successfully")


def rollback(cursor):
    """
    Drop insight_cache table.
    """
    logger.info("Rolling back: Dropping insight_cache table...")
    
    cursor.execute("DROP TABLE IF EXISTS insight_cache CASCADE;")
    
    logger.info("✅ insight_cache table dropped")


# Migration metadata
__depends__ = ['016_pipeline_runtime_kv']
