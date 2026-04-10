#!/usr/bin/env python3
"""
Script to mark all existing documents as legacy and prepare for migration.

This script should be run ONCE before starting the Orchestrator Agent migration.
It will:
1. Mark all documents in document_status as data_source='legacy'
2. Parse filename metadata (date, newspaper, sha8) where possible
3. Create initial migration_tracking records
4. Generate report

Usage:
    python scripts/mark_documents_as_legacy.py

Related: REQ-027_ORCHESTRATOR_MIGRATION.md, Migration 021
Date: 2026-04-10
"""

import asyncio
import asyncpg
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from adapters.driven.persistence.migration_models import DocumentMetadata


# ============================================================================
# Filename Parser
# ============================================================================

def parse_pdf_filename(filename: str) -> dict:
    """
    Parse filename with pattern: {sha8}_{DD-MM-YY}-{Newspaper}.pdf
    
    Returns:
        {
            'is_valid': bool,
            'sha8': str,
            'date': datetime,
            'newspaper': str
        }
    """
    # Remove .pdf extension if present
    base_filename = filename.replace('.pdf', '')
    
    # Pattern: {sha8}_{DD-MM-YY}-{Newspaper}
    pattern = r'^([a-f0-9]{8})_(\d{2}-\d{2}-\d{2})-(.+)$'
    match = re.match(pattern, base_filename, re.IGNORECASE)
    
    if not match:
        return {
            'is_valid': False,
            'sha8': None,
            'date': None,
            'newspaper': None
        }
    
    sha8, date_str, newspaper = match.groups()
    
    try:
        # Parse date: DD-MM-YY
        date = datetime.strptime(date_str, '%d-%m-%y')
    except ValueError:
        return {
            'is_valid': False,
            'sha8': sha8,
            'date': None,
            'newspaper': newspaper
        }
    
    return {
        'is_valid': True,
        'sha8': sha8.lower(),
        'date': date,
        'newspaper': newspaper.strip()
    }


# ============================================================================
# Main Script
# ============================================================================

async def main():
    print("=" * 80)
    print("LEGACY MIGRATION PREPARATION SCRIPT")
    print("=" * 80)
    print()
    
    # Connect to database
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ ERROR: DATABASE_URL not set in environment")
        return 1
    
    print(f"📡 Connecting to database...")
    pool = await asyncpg.create_pool(db_url)
    
    try:
        # Step 1: Check if migration 021 was applied
        print("\n✅ Step 1: Verify migration 021 is applied")
        
        tables_exist = await pool.fetchval(
            """
            SELECT COUNT(*) = 3
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('migration_tracking', 'document_processing_log', 'pipeline_results')
            """
        )
        
        if not tables_exist:
            print("❌ ERROR: Migration 021 not applied. Run migration first:")
            print("   psql -U user -d db -f backend/migrations/021_legacy_migration_tracking.sql")
            return 1
        
        print("   ✓ Migration tables exist")
        
        # Step 2: Get all documents
        print("\n✅ Step 2: Fetch all documents from document_status")
        
        documents = await pool.fetch(
            """
            SELECT document_id, filename, created_at, data_source, migration_status
            FROM document_status
            ORDER BY created_at
            """
        )
        
        total_docs = len(documents)
        print(f"   ✓ Found {total_docs} documents")
        
        if total_docs == 0:
            print("   ℹ️  No documents to migrate")
            return 0
        
        # Step 3: Mark as legacy and parse metadata
        print("\n✅ Step 3: Mark documents as legacy + parse metadata")
        
        parsed_count = 0
        failed_parse_count = 0
        already_legacy = 0
        
        for doc in documents:
            document_id = doc['document_id']
            filename = doc['filename']
            data_source = doc['data_source']
            
            # Skip if already processed
            if data_source == 'orchestrator':
                continue
            
            if data_source == 'legacy':
                already_legacy += 1
            
            # Parse filename
            metadata = parse_pdf_filename(filename)
            
            # Update document_status
            await pool.execute(
                """
                UPDATE document_status
                SET 
                    data_source = 'legacy',
                    migration_status = 'pending',
                    publication_date = $2,
                    newspaper_name = $3,
                    sha8_prefix = $4,
                    metadata_parsed = $5
                WHERE document_id = $1
                """,
                document_id,
                metadata['date'],
                metadata['newspaper'],
                metadata['sha8'],
                metadata['is_valid']
            )
            
            if metadata['is_valid']:
                parsed_count += 1
            else:
                failed_parse_count += 1
        
        print(f"   ✓ Marked {total_docs - already_legacy} documents as legacy")
        print(f"   ✓ Parsed metadata: {parsed_count} successful, {failed_parse_count} failed")
        
        # Step 4: Generate report
        print("\n✅ Step 4: Generate migration report")
        
        # Count by newspaper
        newspapers = await pool.fetch(
            """
            SELECT newspaper_name, COUNT(*) as count
            FROM document_status
            WHERE data_source = 'legacy' AND metadata_parsed = true
            GROUP BY newspaper_name
            ORDER BY count DESC
            LIMIT 10
            """
        )
        
        print("\n   📊 Documents by Newspaper:")
        for row in newspapers:
            print(f"      • {row['newspaper_name']}: {row['count']}")
        
        # Count by date range
        date_range = await pool.fetchrow(
            """
            SELECT 
                MIN(publication_date) as first_date,
                MAX(publication_date) as last_date,
                COUNT(DISTINCT publication_date) as unique_dates
            FROM document_status
            WHERE data_source = 'legacy' AND metadata_parsed = true
            """
        )
        
        if date_range['first_date']:
            print(f"\n   📅 Date Range:")
            print(f"      • First: {date_range['first_date']}")
            print(f"      • Last: {date_range['last_date']}")
            print(f"      • Unique dates: {date_range['unique_dates']}")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total documents: {total_docs}")
        print(f"Marked as legacy: {total_docs - already_legacy}")
        print(f"Already legacy: {already_legacy}")
        print(f"Metadata parsed successfully: {parsed_count}")
        print(f"Metadata parse failed: {failed_parse_count}")
        print()
        print("✅ All documents prepared for migration!")
        print()
        print("Next steps:")
        print("1. Start Orchestrator Agent (FASE 2)")
        print("2. Process documents with validation")
        print("3. Monitor migration progress in dashboard")
        print()
        
        return 0
        
    finally:
        await pool.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
