#!/usr/bin/env python3
"""
Re-segment existing documents using NewsSegmentationAgent

This script re-processes documents that were already OCR'd using the old
heuristic segmentation, replacing them with LLM-based intelligent segmentation.

Usage:
    python re_segment_existing.py --dry-run          # Preview changes
    python re_segment_existing.py --execute          # Apply changes
    python re_segment_existing.py --document-id XXX  # Process specific document
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.driven.persistence.postgres.base import BasePostgresRepository
from news_segmentation_agent import get_segmentation_agent
from qdrant_connector import QdrantConnector
import hashlib
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _normalize_text_for_hash(text: str) -> str:
    """Normalize text for consistent hashing (same as app.py)."""
    import re
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


# Helper repository for DB access
class ScriptRepository(BasePostgresRepository):
    pass


_repo = ScriptRepository()


def get_documents_with_ocr_text(document_id: str = None):
    """Get documents that have OCR text and can be re-segmented."""
    conn = _repo.get_connection()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if document_id:
            cursor.execute(
                """
                SELECT document_id, filename, ocr_text, processing_stage, 
                       segmentation_items_count, segmentation_avg_confidence
                FROM document_status
                WHERE document_id = %s 
                  AND ocr_text IS NOT NULL
                  AND LENGTH(ocr_text) > 500
                """,
                (document_id,)
            )
        else:
            cursor.execute(
                """
                SELECT document_id, filename, ocr_text, processing_stage,
                       segmentation_items_count, segmentation_avg_confidence
                FROM document_status
                WHERE ocr_text IS NOT NULL
                  AND LENGTH(ocr_text) > 500
                  AND processing_stage >= 'chunking'
                ORDER BY created_at DESC
                """
            )
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        _repo.release_connection(conn)


def get_current_news_items(document_id: str):
    """Get current news items for a document."""
    conn = _repo.get_connection()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """
            SELECT news_item_id, title, text_hash, segmentation_confidence
            FROM news_items
            WHERE document_id = %s
            ORDER BY item_index
            """,
            (document_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        _repo.release_connection(conn)


def delete_news_items_and_chunks(document_id: str, dry_run: bool = True):
    """Delete news items from DB and chunks from Qdrant for a document."""
    if dry_run:
        logger.info(f"   [DRY-RUN] Would delete news items and chunks for {document_id}")
        return
    
    conn = _repo.get_connection()
    try:
        cursor = conn.cursor()
        
        # Delete from news_item_insights first (FK constraint)
        cursor.execute("DELETE FROM news_item_insights WHERE document_id = %s", (document_id,))
        deleted_insights = cursor.rowcount
        
        # Delete from news_items
        cursor.execute("DELETE FROM news_items WHERE document_id = %s", (document_id,))
        deleted_items = cursor.rowcount
        
        conn.commit()
        logger.info(f"   Deleted {deleted_items} news items and {deleted_insights} insights from DB")
        
        # Delete chunks from Qdrant
        try:
            qdrant = QdrantConnector(host="qdrant", port=6333)
            qdrant.connect()
            
            # Delete all points with this document_id
            qdrant.client.delete(
                collection_name="rag_documents",
                points_selector={
                    "filter": {
                        "must": [
                            {"key": "document_id", "match": {"value": document_id}}
                        ]
                    }
                }
            )
            logger.info(f"   Deleted chunks from Qdrant for {document_id}")
        except Exception as e:
            logger.error(f"   ⚠️ Failed to delete Qdrant chunks: {e}")
    finally:
        _repo.release_connection(conn)


def re_segment_document(doc: dict, dry_run: bool = True, min_confidence: float = 0.7):
    """
    Re-segment a single document using NewsSegmentationAgent.
    
    Returns:
        Dict with results: {success: bool, old_count: int, new_count: int, ...}
    """
    document_id = doc['document_id']
    filename = doc['filename']
    ocr_text = doc['ocr_text']
    
    logger.info("=" * 80)
    logger.info(f"📄 Processing: {filename}")
    logger.info(f"   Document ID: {document_id}")
    logger.info(f"   OCR text length: {len(ocr_text)} chars")
    
    # Get current items
    current_items = get_current_news_items(document_id)
    old_count = len(current_items)
    old_avg_conf = doc.get('segmentation_avg_confidence') or 0.0
    
    logger.info(f"   Current: {old_count} items (avg confidence: {old_avg_conf:.2f})")
    
    # Segment with LLM
    segmentation_agent = get_segmentation_agent()
    
    try:
        new_items = segmentation_agent.segment_document(ocr_text, min_confidence=min_confidence)
        new_count = len(new_items)
        new_avg_conf = sum(it['confidence'] for it in new_items) / new_count if new_count > 0 else 0.0
        
        logger.info(f"   New segmentation: {new_count} items (avg confidence: {new_avg_conf:.2f})")
        
        # Decision: Should we replace?
        should_replace = (
            new_count > 0 and
            (new_avg_conf > old_avg_conf + 0.1 or old_avg_conf == 0.0)  # Significant improvement or first time
        )
        
        if not should_replace:
            logger.info(f"   ⏭️  SKIP: New segmentation not significantly better")
            return {
                "success": False,
                "reason": "No improvement",
                "old_count": old_count,
                "new_count": new_count,
                "old_confidence": old_avg_conf,
                "new_confidence": new_avg_conf
            }
        
        logger.info(f"   ✅ REPLACE: New segmentation is better")
        
        if not dry_run:
            # Delete old data
            delete_news_items_and_chunks(document_id, dry_run=False)
            
            # Insert new items
            conn = _repo.get_connection()
            try:
                cursor = conn.cursor()
                now = datetime.utcnow().isoformat()
                
                for idx, it in enumerate(new_items):
                    title = it['title']
                    body = it['text']
                    confidence = it['confidence']
                    
                    body_norm = _normalize_text_for_hash(body)
                    text_hash = hashlib.sha256(body_norm.encode("utf-8")).hexdigest() if body_norm else None
                    news_item_id = f"{document_id}::{idx}"
                    
                    cursor.execute(
                        """
                        INSERT INTO news_items 
                        (news_item_id, document_id, filename, item_index, title, status, text_hash, segmentation_confidence, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, 'indexing_done', %s, %s, %s, %s)
                        """,
                        (news_item_id, document_id, filename, idx, title, text_hash, confidence, now, now)
                    )
                
                # Update document_status with segmentation metrics
                cursor.execute(
                    """
                    UPDATE document_status
                    SET segmentation_items_count = %s,
                        segmentation_avg_confidence = %s,
                        processing_stage = 'chunking'
                    WHERE document_id = %s
                    """,
                    (new_count, new_avg_conf, document_id)
                )
                
                conn.commit()
                logger.info(f"   ✅ Database updated with {new_count} new items")
                
                # TODO: Re-chunk and re-index to Qdrant
                # For now, just mark as needing re-processing
                cursor.execute(
                    """
                    UPDATE document_status
                    SET status = 'chunking_pending',
                        processing_stage = 'chunking'
                    WHERE document_id = %s
                    """,
                    (document_id,)
                )
                conn.commit()
                logger.info(f"   📋 Marked for re-chunking and re-indexing")
                
            finally:
                _repo.release_connection(conn)
        
        return {
            "success": True,
            "replaced": not dry_run,
            "old_count": old_count,
            "new_count": new_count,
            "old_confidence": old_avg_conf,
            "new_confidence": new_avg_conf
        }
        
    except Exception as e:
        logger.error(f"   ❌ Segmentation failed: {e}", exc_info=True)
        return {
            "success": False,
            "reason": str(e),
            "old_count": old_count
        }


def main():
    parser = argparse.ArgumentParser(description="Re-segment existing documents with LLM")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--execute", action="store_true", help="Apply changes to database")
    parser.add_argument("--document-id", type=str, help="Process specific document ID")
    parser.add_argument("--min-confidence", type=float, default=0.7, help="Minimum confidence threshold")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to process")
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        logger.error("Must specify either --dry-run or --execute")
        sys.exit(1)
    
    dry_run = args.dry_run
    
    logger.info("=" * 80)
    logger.info(f"🔄 Re-segmentation Script")
    logger.info(f"   Mode: {'DRY-RUN (preview only)' if dry_run else 'EXECUTE (will modify database)'}")
    logger.info(f"   Min confidence: {args.min_confidence}")
    logger.info("=" * 80)
    
    # Get documents
    documents = get_documents_with_ocr_text(args.document_id)
    
    if args.limit:
        documents = documents[:args.limit]
    
    logger.info(f"📊 Found {len(documents)} documents to process")
    
    if len(documents) == 0:
        logger.info("✅ No documents to process")
        return
    
    # Process each document
    results = {
        "total": len(documents),
        "replaced": 0,
        "skipped": 0,
        "failed": 0
    }
    
    for i, doc in enumerate(documents, 1):
        logger.info(f"\n[{i}/{len(documents)}] {doc['filename']}")
        
        result = re_segment_document(doc, dry_run=dry_run, min_confidence=args.min_confidence)
        
        if result['success']:
            if result.get('replaced'):
                results['replaced'] += 1
            else:
                results['skipped'] += 1
        else:
            results['failed'] += 1
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 SUMMARY")
    logger.info(f"   Total documents: {results['total']}")
    logger.info(f"   Replaced: {results['replaced']}")
    logger.info(f"   Skipped: {results['skipped']}")
    logger.info(f"   Failed: {results['failed']}")
    logger.info("=" * 80)
    
    if dry_run:
        logger.info("\n💡 This was a dry-run. Use --execute to apply changes.")


if __name__ == "__main__":
    main()
