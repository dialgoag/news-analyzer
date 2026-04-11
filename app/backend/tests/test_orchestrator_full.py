"""
Test End-to-End del Orchestrator Agent con documento real
Procesa un documento completo y registra todos los eventos en document_processing_log
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.driven.llm.graphs.pipeline_orchestrator_graph import build_orchestrator_workflow

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def process_document_with_orchestrator(document_id: str, filename: str, filepath: str):
    """
    Procesa un documento con el Orchestrator Agent completo.
    Registra todos los eventos en document_processing_log.
    """
    logger.info("=" * 80)
    logger.info(f"🚀 PROCESANDO DOCUMENTO CON ORCHESTRATOR")
    logger.info("=" * 80)
    logger.info(f"Document ID: {document_id}")
    logger.info(f"Filename: {filename}")
    logger.info(f"Path: {filepath}")
    logger.info("")
    
    # Build workflow
    logger.info("📦 Building Orchestrator workflow...")
    workflow = build_orchestrator_workflow()
    
    # Initial state
    initial_state = {
        "document_id": document_id,
        "filename": filename,
        "filepath": filepath,
        "mode": "orchestrator",  # NOT migration mode
        "current_stage": "upload",
        "errors": [],
        "metadata": {}
    }
    
    logger.info("▶️  Starting Orchestrator Agent...")
    logger.info("")
    
    # Run workflow
    result = await workflow.ainvoke(initial_state)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ ORCHESTRATOR COMPLETADO")
    logger.info("=" * 80)
    logger.info(f"Final stage: {result.get('current_stage')}")
    logger.info(f"Status: {result.get('status', 'unknown')}")
    logger.info(f"Errors: {len(result.get('errors', []))}")
    
    if result.get('errors'):
        logger.error("⚠️  ERRORES ENCONTRADOS:")
        for err in result['errors']:
            logger.error(f"  - {err}")
    
    logger.info("")
    logger.info("📊 Verifica el timeline en la UI:")
    logger.info(f"   Document ID: {document_id}")
    logger.info(f"   Buscar: {filename}")
    logger.info("")
    
    return result


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python test_orchestrator_full.py <document_id> <filename> <filepath>")
        print("")
        print("Example:")
        print("  python test_orchestrator_full.py \\")
        print("    test-elpais-13feb \\")
        print("    '13-02-26-El Pais.pdf' \\")
        print("    '/app/inbox/processed/c35ba0f3_13-02-26-El Pais.pdf'")
        sys.exit(1)
    
    document_id = sys.argv[1]
    filename = sys.argv[2]
    filepath = sys.argv[3]
    
    asyncio.run(process_document_with_orchestrator(document_id, filename, filepath))
