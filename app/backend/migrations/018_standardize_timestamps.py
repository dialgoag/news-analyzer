"""
Migration 018: Standardize timestamps with document_stage_timing table

Domain: Data Governance & Pipeline Audit Trail
Description: Comprehensive timestamp system with dedicated stage timing table
Depends on: 017_insight_cache_table

DESIGN DECISION: Separate Table for Stage Timing (Scalable Architecture)
Instead of adding 10+ timestamp columns to document_status, we create a dedicated
table to track timing for each pipeline stage. This enables:
- Adding new stages without schema changes (just INSERT new rows)
- Flexible metadata per stage
- Easy performance analysis queries
- Clean separation of concerns

Schema Design:

1. document_status (existing):
   - created_at, updated_at (document-level timestamps)

2. document_stage_timing (NEW):
   - Tracks each stage independently
   - Pattern: created_at = stage STARTS, updated_at = stage ENDS
   - One row per document per stage
   - Stages: upload, ocr, chunking, indexing, insights

Usage Pattern:
  Worker starts stage  → INSERT (document_id, stage, created_at=NOW, status='processing')
  Worker ends stage    → UPDATE (updated_at=NOW, status='done'/'error')

Query Examples:
  -- Average time per stage:
  SELECT stage, AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) 
  FROM document_stage_timing WHERE updated_at IS NOT NULL GROUP BY stage;
  
  -- Document timeline:
  SELECT stage, created_at, updated_at, status 
  FROM document_stage_timing WHERE document_id = 'doc-123' ORDER BY created_at;

Changes:
1. document_status: Add document-level created_at/updated_at
2. document_stage_timing: NEW table for stage-level timing
3. users: Add updated_at (audit trail)
4. pipeline_runtime_kv: Add created_at (audit trail)
5. Auto-update triggers for updated_at columns

Impact:
- Scalable pipeline stage tracking
- Full audit trail without schema changes for new stages
- Performance analysis per stage
- Clean separation: document state vs stage timing
"""

from yoyo import step

steps = [
    # ========================================
    # 1. CRITICAL: document_status - Document-level timestamps
    # ========================================
    step(
        """
        ALTER TABLE document_status 
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        """,
        """
        ALTER TABLE document_status 
        DROP COLUMN IF EXISTS created_at,
        DROP COLUMN IF EXISTS updated_at
        """
    ),
    
    # ========================================
    # 2. NEW TABLE: document_stage_timing (unified for documents + news_items)
    # ========================================
    step(
        """
        CREATE TABLE IF NOT EXISTS document_stage_timing (
            id SERIAL PRIMARY KEY,
            document_id VARCHAR(255) NOT NULL,
            news_item_id VARCHAR(255) NULL,
            stage VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            error_message TEXT,
            metadata JSONB DEFAULT '{}'::jsonb,
            
            -- Constraints
            FOREIGN KEY (document_id) REFERENCES document_status(document_id) ON DELETE CASCADE,
            
            -- Validations
            -- Document-level stages (news_item_id IS NULL): upload, ocr, chunking, indexing
            -- News-level stages (news_item_id IS NOT NULL): insights, insights_indexing, etc.
            CHECK (stage IN ('upload', 'ocr', 'chunking', 'indexing', 'insights', 'insights_indexing')),
            CHECK (status IN ('pending', 'processing', 'done', 'error', 'skipped'))
        )
        """,
        "DROP TABLE IF EXISTS document_stage_timing CASCADE"
    ),
    
    # Unique index instead of constraint (supports COALESCE expression)
    step(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_document_stage_timing_unique
        ON document_stage_timing(document_id, COALESCE(news_item_id, ''), stage)
        """,
        "DROP INDEX IF EXISTS idx_document_stage_timing_unique"
    ),
    
    step(
        """
        COMMENT ON TABLE document_stage_timing IS 
        'Unified timing table: tracks both document-level stages (news_item_id=NULL) and news-level stages (news_item_id!=NULL)'
        """,
        "-- No rollback"
    ),
    
    step(
        """
        COMMENT ON COLUMN document_stage_timing.news_item_id IS 
        'NULL for document-level stages (upload/ocr/chunking/indexing), NOT NULL for news-level stages (insights)'
        """,
        "-- No rollback"
    ),
    
    # ========================================
    # 3. Backfill existing data from document_status
    # ========================================
    # Backfill: Create upload stage entries for existing documents
    step(
        """
        INSERT INTO document_stage_timing (document_id, news_item_id, stage, status, created_at, updated_at)
        SELECT 
            document_id,
            NULL as news_item_id,
            'upload' as stage,
            CASE 
                WHEN status LIKE 'upload_%' THEN 'processing'
                ELSE 'done'
            END as status,
            ingested_at as created_at,
            ingested_at as updated_at
        FROM document_status
        WHERE ingested_at IS NOT NULL
        ON CONFLICT (document_id, COALESCE(news_item_id, ''), stage) DO NOTHING
        """,
        "-- No rollback for data migration"
    ),
    
    # Backfill: Create indexing stage entries for indexed documents
    step(
        """
        INSERT INTO document_stage_timing (document_id, news_item_id, stage, status, created_at, updated_at)
        SELECT 
            document_id,
            NULL as news_item_id,
            'indexing' as stage,
            'done' as status,
            indexed_at as created_at,
            indexed_at as updated_at
        FROM document_status
        WHERE indexed_at IS NOT NULL
        ON CONFLICT (document_id, COALESCE(news_item_id, ''), stage) DO NOTHING
        """,
        "-- No rollback for data migration"
    ),
    
    # ========================================
    # 4. users: Add updated_at for audit
    # ========================================
    step(
        """
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        """,
        "ALTER TABLE users DROP COLUMN IF EXISTS updated_at"
    ),
    
    # ========================================
    # 5. pipeline_runtime_kv: Add created_at
    # ========================================
    step(
        """
        ALTER TABLE pipeline_runtime_kv 
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()
        """,
        "ALTER TABLE pipeline_runtime_kv DROP COLUMN IF EXISTS created_at"
    ),
    
    # ========================================
    # 6. Create reusable trigger function for updated_at
    # ========================================
    step(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
           NEW.updated_at = NOW();
           RETURN NEW;
        END;
        $$ language 'plpgsql'
        """,
        "DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE"
    ),
    
    # ========================================
    # 7. Apply triggers to document_status
    # ========================================
    step(
        """
        DROP TRIGGER IF EXISTS update_document_status_updated_at ON document_status;
        CREATE TRIGGER update_document_status_updated_at 
        BEFORE UPDATE ON document_status 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """,
        "DROP TRIGGER IF EXISTS update_document_status_updated_at ON document_status"
    ),
    
    # ========================================
    # 8. Apply trigger to document_stage_timing
    # ========================================
    step(
        """
        DROP TRIGGER IF EXISTS update_document_stage_timing_updated_at ON document_stage_timing;
        CREATE TRIGGER update_document_stage_timing_updated_at 
        BEFORE UPDATE ON document_stage_timing 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """,
        "DROP TRIGGER IF EXISTS update_document_stage_timing_updated_at ON document_stage_timing"
    ),
    
    # ========================================
    # 9. Apply triggers to other tables
    # ========================================
    step(
        """
        DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        CREATE TRIGGER update_users_updated_at 
        BEFORE UPDATE ON users 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """,
        "DROP TRIGGER IF EXISTS update_users_updated_at ON users"
    ),
    
    step(
        """
        DROP TRIGGER IF EXISTS update_news_items_updated_at ON news_items;
        CREATE TRIGGER update_news_items_updated_at 
        BEFORE UPDATE ON news_items 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """,
        "DROP TRIGGER IF EXISTS update_news_items_updated_at ON news_items"
    ),
    
    step(
        """
        DROP TRIGGER IF EXISTS update_news_item_insights_updated_at ON news_item_insights;
        CREATE TRIGGER update_news_item_insights_updated_at 
        BEFORE UPDATE ON news_item_insights 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """,
        "DROP TRIGGER IF EXISTS update_news_item_insights_updated_at ON news_item_insights"
    ),
    
    step(
        """
        DROP TRIGGER IF EXISTS update_document_insights_updated_at ON document_insights;
        CREATE TRIGGER update_document_insights_updated_at 
        BEFORE UPDATE ON document_insights 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """,
        "DROP TRIGGER IF EXISTS update_document_insights_updated_at ON document_insights"
    ),
    
    step(
        """
        DROP TRIGGER IF EXISTS update_daily_reports_updated_at ON daily_reports;
        CREATE TRIGGER update_daily_reports_updated_at 
        BEFORE UPDATE ON daily_reports 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """,
        "DROP TRIGGER IF EXISTS update_daily_reports_updated_at ON daily_reports"
    ),
    
    step(
        """
        DROP TRIGGER IF EXISTS update_weekly_reports_updated_at ON weekly_reports;
        CREATE TRIGGER update_weekly_reports_updated_at 
        BEFORE UPDATE ON weekly_reports 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """,
        "DROP TRIGGER IF EXISTS update_weekly_reports_updated_at ON weekly_reports"
    ),
    
    # ========================================
    # 10. Performance indexes
    # ========================================
    step(
        "CREATE INDEX IF NOT EXISTS idx_document_status_created ON document_status(created_at DESC)",
        "DROP INDEX IF EXISTS idx_document_status_created"
    ),
    
    step(
        "CREATE INDEX IF NOT EXISTS idx_document_status_updated ON document_status(updated_at DESC)",
        "DROP INDEX IF EXISTS idx_document_status_updated"
    ),
    
    step(
        "CREATE INDEX IF NOT EXISTS idx_users_updated ON users(updated_at DESC)",
        "DROP INDEX IF EXISTS idx_users_updated"
    ),
    
    step(
        "CREATE INDEX IF NOT EXISTS idx_pipeline_runtime_kv_created ON pipeline_runtime_kv(created_at DESC)",
        "DROP INDEX IF EXISTS idx_pipeline_runtime_kv_created"
    ),
    
    # Indexes for document_stage_timing
    step(
        """
        CREATE INDEX IF NOT EXISTS idx_document_stage_timing_doc 
        ON document_stage_timing(document_id, stage)
        WHERE news_item_id IS NULL
        """,
        "DROP INDEX IF EXISTS idx_document_stage_timing_doc"
    ),
    
    step(
        """
        CREATE INDEX IF NOT EXISTS idx_document_stage_timing_news 
        ON document_stage_timing(document_id, news_item_id, stage)
        WHERE news_item_id IS NOT NULL
        """,
        "DROP INDEX IF EXISTS idx_document_stage_timing_news"
    ),
    
    step(
        """
        CREATE INDEX IF NOT EXISTS idx_document_stage_timing_stage 
        ON document_stage_timing(stage, status, created_at)
        """,
        "DROP INDEX IF EXISTS idx_document_stage_timing_stage"
    ),
    
    step(
        """
        CREATE INDEX IF NOT EXISTS idx_document_stage_timing_performance 
        ON document_stage_timing(stage, news_item_id, created_at, updated_at) 
        WHERE status = 'done'
        """,
        "DROP INDEX IF EXISTS idx_document_stage_timing_performance"
    ),
]
