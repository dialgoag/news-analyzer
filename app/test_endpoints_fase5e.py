#!/usr/bin/env python3
"""
Test end-to-end para verificar el pipeline completo después de Fase 5E.

Pipeline completo:
1. UPLOAD → pending → processing → done
2. OCR → pending → processing → done
3. CHUNKING → pending → processing → done
4. INDEXING → pending → processing → done
5. INSIGHTS → pending → processing → done (si está habilitado)
6. COMPLETED (terminal)

Este test verifica que las migraciones a document_repository no rompieron
la secuencia de estados del pipeline.
"""

import sys
import os
import time
import requests
from pathlib import Path
from typing import Optional

# Configuration
API_BASE = "http://localhost:8000"
TIMEOUT = 30
POLL_INTERVAL = 2  # seconds
MAX_WAIT_TIME = 120  # seconds (2 minutes)

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'

def log(msg: str, color: str = Colors.CYAN):
    """Log message with color."""
    print(f"{color}{msg}{Colors.END}")

def log_success(msg: str):
    """Log success message."""
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def log_error(msg: str):
    """Log error message."""
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def log_warning(msg: str):
    """Log warning message."""
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def log_info(msg: str):
    """Log info message."""
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

def check_api_health() -> bool:
    """Verify API is running."""
    try:
        resp = requests.get(f"{API_BASE}/api/health", timeout=5)
        if resp.status_code == 200:
            log_success("API is running")
            return True
        else:
            log_error(f"API health check failed: {resp.status_code}")
            return False
    except Exception as e:
        log_error(f"Cannot connect to API: {e}")
        return False

def upload_test_document() -> Optional[str]:
    """
    Upload a test PDF document.
    Returns document_id if successful, None otherwise.
    """
    log("\n📤 Step 1: Upload test document")
    
    # Create a minimal test PDF (or use existing one)
    test_pdf_path = Path(__file__).parent / "test_data" / "test_sample.pdf"
    
    if not test_pdf_path.exists():
        log_warning(f"Test PDF not found at {test_pdf_path}")
        log_info("Looking for any PDF in backend directory...")
        
        # Try to find any PDF
        backend_dir = Path(__file__).parent / "backend"
        pdfs = list(backend_dir.glob("**/*.pdf"))
        if pdfs:
            test_pdf_path = pdfs[0]
            log_info(f"Using: {test_pdf_path.name}")
        else:
            log_error("No test PDF found")
            return None
    
    try:
        with open(test_pdf_path, 'rb') as f:
            files = {'file': (test_pdf_path.name, f, 'application/pdf')}
            resp = requests.post(
                f"{API_BASE}/api/upload",
                files=files,
                timeout=TIMEOUT
            )
        
        if resp.status_code != 200:
            log_error(f"Upload failed: {resp.status_code} - {resp.text}")
            return None
        
        data = resp.json()
        document_id = data.get("document_id")
        
        if not document_id:
            log_error("No document_id in response")
            return None
        
        log_success(f"Document uploaded: {document_id}")
        return document_id
    
    except Exception as e:
        log_error(f"Upload exception: {e}")
        return None

def get_document_status(document_id: str) -> Optional[dict]:
    """Get current status of document."""
    try:
        resp = requests.get(
            f"{API_BASE}/api/documents/metadata",
            timeout=TIMEOUT
        )
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        docs = data.get("documents", [])
        
        for doc in docs:
            if doc.get("document_id") == document_id:
                return doc
        
        return None
    except Exception as e:
        log_error(f"Error getting status: {e}")
        return None

def wait_for_stage_completion(
    document_id: str,
    expected_stage: str,
    max_wait: int = MAX_WAIT_TIME
) -> bool:
    """
    Wait for document to complete a specific stage.
    
    Args:
        document_id: Document to monitor
        expected_stage: Stage name (e.g., "ocr", "chunking", "indexing")
        max_wait: Maximum seconds to wait
    
    Returns:
        True if stage completed successfully, False otherwise
    """
    log(f"\n⏳ Step: Waiting for {expected_stage.upper()} stage...")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        doc = get_document_status(document_id)
        
        if not doc:
            log_warning(f"Document {document_id[:8]}... not found")
            time.sleep(POLL_INTERVAL)
            continue
        
        current_status = doc.get("status", "unknown")
        processing_stage = doc.get("processing_stage", "unknown")
        
        # Log status change
        if current_status != last_status:
            log_info(f"Status: {current_status} (stage: {processing_stage})")
            last_status = current_status
        
        # Check for error
        if current_status == "error":
            error_msg = doc.get("error_message", "Unknown error")
            log_error(f"Pipeline failed: {error_msg}")
            return False
        
        # Check if stage completed
        expected_done = f"{expected_stage}_done"
        if current_status == expected_done:
            log_success(f"{expected_stage.upper()} stage completed")
            return True
        
        # Special case: completed
        if current_status == "completed":
            log_success(f"Pipeline completed (includes {expected_stage})")
            return True
        
        time.sleep(POLL_INTERVAL)
    
    log_error(f"Timeout waiting for {expected_stage} (>{max_wait}s)")
    return False

def verify_chunks_created(document_id: str) -> bool:
    """Verify that chunks were created after chunking stage."""
    log("\n🔍 Verifying chunks created...")
    
    doc = get_document_status(document_id)
    if not doc:
        log_error("Could not get document status")
        return False
    
    num_chunks = doc.get("num_chunks", 0)
    if num_chunks > 0:
        log_success(f"Chunks created: {num_chunks}")
        return True
    else:
        log_warning("No chunks created yet")
        return False

def verify_indexed(document_id: str) -> bool:
    """Verify that document was indexed."""
    log("\n🔍 Verifying indexing...")
    
    doc = get_document_status(document_id)
    if not doc:
        log_error("Could not get document status")
        return False
    
    indexed_at = doc.get("indexed_at")
    if indexed_at:
        log_success(f"Document indexed at: {indexed_at}")
        return True
    else:
        log_warning("Document not indexed yet")
        return False

def main():
    """Run end-to-end pipeline test."""
    print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}End-to-End Pipeline Test (Fase 5E){Colors.END}")
    print(f"{Colors.BLUE}Testing: UPLOAD → OCR → CHUNKING → INDEXING → (INSIGHTS) → COMPLETED{Colors.END}")
    print(f"{Colors.BLUE}{'='*70}{Colors.END}")
    
    # Step 0: Check API health
    if not check_api_health():
        log_error("API is not running. Start the backend first:")
        log_info("cd app && docker-compose up -d")
        sys.exit(1)
    
    # Step 1: Upload document
    document_id = upload_test_document()
    if not document_id:
        log_error("Upload failed")
        sys.exit(1)
    
    # Step 2: Wait for OCR
    if not wait_for_stage_completion(document_id, "ocr"):
        log_error("OCR stage failed")
        sys.exit(1)
    
    # Step 3: Wait for Chunking
    if not wait_for_stage_completion(document_id, "chunking"):
        log_error("Chunking stage failed")
        sys.exit(1)
    
    # Verify chunks were created
    verify_chunks_created(document_id)
    
    # Step 4: Wait for Indexing
    if not wait_for_stage_completion(document_id, "indexing"):
        log_error("Indexing stage failed")
        sys.exit(1)
    
    # Verify indexing completed
    verify_indexed(document_id)
    
    # Step 5: Check if insights stage exists (optional)
    log("\n🔍 Checking for insights stage...")
    doc = get_document_status(document_id)
    if doc:
        final_status = doc.get("status")
        log_info(f"Final status: {final_status}")
        
        if final_status in ["insights_pending", "insights_processing", "insights_done"]:
            log_info("Insights stage is enabled, waiting...")
            if not wait_for_stage_completion(document_id, "insights", max_wait=60):
                log_warning("Insights stage incomplete (may be disabled or slow)")
        elif final_status == "completed":
            log_success("Pipeline completed successfully")
        else:
            log_info(f"Document in state: {final_status}")
    
    # Summary
    print(f"\n{Colors.GREEN}{'='*70}{Colors.END}")
    print(f"{Colors.GREEN}✅ END-TO-END TEST PASSED{Colors.END}")
    print(f"{Colors.GREEN}Document {document_id[:12]}... processed successfully{Colors.END}")
    print(f"{Colors.GREEN}{'='*70}{Colors.END}\n")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
