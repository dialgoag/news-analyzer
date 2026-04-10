"""
Test End-to-End del Pipeline Orchestrator Agent

Este script prueba el Orchestrator Agent completo con un documento real:
1. Inicializa el agent
2. Procesa un documento de prueba
3. Valida que todas las etapas se ejecuten correctamente
4. Muestra el resultado final

Usage:
    python test_orchestrator_e2e.py <document_id> <filename> <filepath>
"""

import asyncio
import asyncpg
import sys
import os
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from adapters.driven.llm.graphs.pipeline_orchestrator_graph import (
    create_orchestrator_agent
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def test_orchestrator_e2e(document_id: str, filename: str, filepath: str):
    """
    Test end-to-end del Orchestrator Agent.
    """
    logger.info("=" * 80)
    logger.info("🚀 TEST END-TO-END: Pipeline Orchestrator Agent")
    logger.info("=" * 80)
    
    # Build database URL
    user = os.getenv("POSTGRES_USER", "raguser")
    password = os.getenv("POSTGRES_PASSWORD", "ragpassword")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "rag_enterprise")
    
    db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    
    # Create DB pool
    logger.info(f"📡 Connecting to database: {host}:{port}/{db}")
    db_pool = await asyncpg.create_pool(
        db_url,
        min_size=2,
        max_size=10,
        command_timeout=120
    )
    
    try:
        # Verify document exists
        logger.info(f"📄 Verifying document exists: {filepath}")
        if not os.path.exists(filepath):
            logger.error(f"❌ Document not found: {filepath}")
            return False
        
        file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
        logger.info(f"   Size: {file_size:.2f} MB")
        
        # Initialize Orchestrator Agent
        logger.info("🤖 Initializing Orchestrator Agent...")
        agent = create_orchestrator_agent(db_pool)
        logger.info("   ✅ Agent ready")
        
        # Process document
        logger.info("=" * 80)
        logger.info(f"⚙️  Processing document: {document_id}")
        logger.info(f"   Filename: {filename}")
        logger.info("=" * 80)
        
        result = await agent.process_document(
            document_id=document_id,
            filename=filename,
            filepath=filepath
        )
        
        # Print results
        logger.info("=" * 80)
        logger.info("📊 RESULTS")
        logger.info("=" * 80)
        
        # Success?
        success = result.get('success', False)
        if success:
            logger.info("✅ PIPELINE COMPLETED SUCCESSFULLY")
        else:
            logger.error("❌ PIPELINE FAILED")
        
        # Errors
        errors = result.get('errors', [])
        if errors:
            logger.error(f"\n🚨 ERRORS ({len(errors)}):")
            for error in errors:
                logger.error(f"   Stage: {error['stage']}")
                logger.error(f"   Error: {error['error']}")
        
        # Pipeline Context (results from each stage)
        pipeline_context = result.get('pipeline_context', {})
        logger.info(f"\n📦 PIPELINE CONTEXT:")
        
        for stage, stage_result in pipeline_context.items():
            logger.info(f"\n   [{stage.upper()}]")
            if isinstance(stage_result, dict):
                for key, value in stage_result.items():
                    if key in ('text', 'articles', 'chunks'):
                        # Summarize large data
                        if isinstance(value, str):
                            logger.info(f"      {key}: {len(value)} chars")
                        elif isinstance(value, list):
                            logger.info(f"      {key}: {len(value)} items")
                    else:
                        logger.info(f"      {key}: {value}")
        
        # Events
        events = result.get('events', [])
        logger.info(f"\n📝 EVENTS ({len(events)}):")
        for event in events:
            logger.info(f"   {event}")
        
        # Query database for verification
        logger.info("\n=" * 80)
        logger.info("🔍 DATABASE VERIFICATION")
        logger.info("=" * 80)
        
        async with db_pool.acquire() as conn:
            # Check document_processing_log
            log_count = await conn.fetchval(
                "SELECT COUNT(*) FROM document_processing_log WHERE document_id = $1",
                document_id
            )
            logger.info(f"   Processing log events: {log_count}")
            
            # Check pipeline_results
            results_count = await conn.fetchval(
                "SELECT COUNT(*) FROM pipeline_results WHERE document_id = $1",
                document_id
            )
            logger.info(f"   Pipeline results: {results_count}")
            
            # Check document_status
            doc_status = await conn.fetchrow(
                "SELECT data_source, migration_status FROM document_status WHERE document_id = $1",
                document_id
            )
            if doc_status:
                logger.info(f"   Data source: {doc_status['data_source']}")
                logger.info(f"   Migration status: {doc_status['migration_status']}")
        
        logger.info("=" * 80)
        logger.info(f"✅ TEST COMPLETED: {'SUCCESS' if success else 'FAILED'}")
        logger.info("=" * 80)
        
        return success
    
    finally:
        # Close pool
        await db_pool.close()


async def main():
    if len(sys.argv) < 4:
        print("Usage: python test_orchestrator_e2e.py <document_id> <filename> <filepath>")
        print()
        print("Example:")
        print("  python test_orchestrator_e2e.py test-doc-001 sample.pdf /app/local-data/uploads/sample.pdf")
        sys.exit(1)
    
    document_id = sys.argv[1]
    filename = sys.argv[2]
    filepath = sys.argv[3]
    
    success = await test_orchestrator_e2e(document_id, filename, filepath)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
