#!/usr/bin/env python3
"""
Test de endpoints migrados en Fase 5E (sin E2E upload).
Valida que los endpoints que usan document_repository funcionen correctamente.
"""

import sys
import requests

API_BASE = "http://localhost:8000"
TIMEOUT = 10

def test_health():
    """Test API health."""
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=TIMEOUT)
        passed = resp.status_code == 200
        print(f"{'✅' if passed else '❌'} API Health: {resp.status_code}")
        return passed
    except Exception as e:
        print(f"❌ API Health: {e}")
        return False

def test_documents_metadata():
    """Test GET /api/documents/metadata."""
    try:
        resp = requests.get(f"{API_BASE}/api/documents/metadata", timeout=TIMEOUT)
        passed = resp.status_code == 200
        if passed:
            data = resp.json()
            docs_count = len(data.get("documents", []))
            print(f"✅ GET /api/documents/metadata: {docs_count} documents")
        else:
            print(f"❌ GET /api/documents/metadata: {resp.status_code}")
        return passed
    except Exception as e:
        print(f"❌ GET /api/documents/metadata: {e}")
        return False

def test_workers_status():
    """Test GET /api/workers/status."""
    try:
        resp = requests.get(f"{API_BASE}/api/workers/status", timeout=TIMEOUT)
        passed = resp.status_code == 200
        if passed:
            data = resp.json()
            workers_count = len(data.get("workers", []))
            print(f"✅ GET /api/workers/status: {workers_count} workers")
        else:
            print(f"❌ GET /api/workers/status: {resp.status_code}")
        return passed
    except Exception as e:
        print(f"❌ GET /api/workers/status: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("Fase 5E: Tests de Endpoints Migrados")
    print("="*60 + "\n")
    
    results = []
    results.append(test_health())
    results.append(test_documents_metadata())
    results.append(test_workers_status())
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "="*60)
    print(f"Resultado: {passed}/{total} tests pasaron")
    print("="*60 + "\n")
    
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
