#!/usr/bin/env python3
"""
Script to verify deduplication in worker processing.
Checks if:
1. No documento appears twice en worker_tasks
2. Los workers no duplican trabajo
3. El sistema respeta UNIQUE constraints en processing_queue
"""

import sqlite3
import sys
from collections import defaultdict

def check_deduplication(db_path="/app/data/rag_users.db"):
    """Check if there's duplicate work being assigned to workers."""
    
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
    except Exception as e:
        print(f"❌ Cannot connect to DB: {e}")
        sys.exit(1)
    
    print("=" * 90)
    print("🔍 VERIFICACIÓN DE DEDUPLICACIÓN DE TRABAJO")
    print("=" * 90)
    
    # 1. Check processing_queue for duplicates
    print("\n1️⃣ PROCESSING QUEUE - Verificar UNIQUE constraint")
    print("-" * 90)
    
    c.execute("""
        SELECT document_id, task_type, COUNT(*) as cnt 
        FROM processing_queue 
        GROUP BY document_id, task_type 
        HAVING cnt > 1
    """)
    
    duplicates = c.fetchall()
    if duplicates:
        print("⚠️  DUPLICADOS ENCONTRADOS en processing_queue:")
        for doc_id, task_type, cnt in duplicates:
            print(f"   - {doc_id}: {cnt} entradas (task_type: {task_type})")
    else:
        print("✅ Sin duplicados en processing_queue (UNIQUE constraint ok)")
    
    # 2. Check worker_tasks for same document in multiple workers (same task_type)
    print("\n2️⃣ WORKER TASKS - Un documento NO puede estar en 2+ workers con mismo task_type")
    print("-" * 90)
    
    c.execute("""
        SELECT document_id, task_type, COUNT(DISTINCT worker_id) as worker_count
        FROM worker_tasks
        WHERE status IN ('assigned', 'started')
        GROUP BY document_id, task_type
        HAVING worker_count > 1
    """)
    
    multi_worker = c.fetchall()
    if multi_worker:
        print("⚠️  DOCUMENTO en múltiples workers:")
        for doc_id, task_type, worker_count in multi_worker:
            print(f"   - {doc_id}: {worker_count} workers procesando task_type={task_type}")
            c.execute("""
                SELECT worker_id, status 
                FROM worker_tasks
                WHERE document_id = ? AND task_type = ?
            """, (doc_id, task_type))
            for w_id, status in c.fetchall():
                print(f"      → {w_id}: {status}")
    else:
        print("✅ Cada documento está en máximo 1 worker por task_type")
    
    # 3. Check for El Pais document specifically
    print("\n3️⃣ DOCUMENTO ESPECÍFICO: 29-01-26-El Pais.pdf")
    print("-" * 90)
    
    c.execute("""
        SELECT document_id, filename FROM processing_queue 
        WHERE filename LIKE '%29-01-26%' OR filename LIKE '%Pais%'
        LIMIT 3
    """)
    
    pais_docs = c.fetchall()
    if pais_docs:
        for doc_id, filename in pais_docs:
            print(f"\n   Documento: {filename}")
            print(f"   ID: {doc_id}")
            
            # Check queue status
            c.execute("""
                SELECT status, COUNT(*) FROM processing_queue
                WHERE document_id = ?
                GROUP BY status
            """, (doc_id,))
            queue_status = c.fetchall()
            print(f"   En queue: {dict(queue_status)}")
            
            # Check worker_tasks
            c.execute("""
                SELECT worker_id, task_type, status 
                FROM worker_tasks
                WHERE document_id = ?
            """, (doc_id,))
            workers = c.fetchall()
            if workers:
                print(f"   Asignado a workers:")
                for w_id, task_type, status in workers:
                    print(f"      - {w_id}: {task_type} ({status})")
            else:
                print(f"   ℹ️  No asignado a ningún worker")
            
            # Check document_status
            c.execute("""
                SELECT status, num_chunks FROM document_status
                WHERE document_id = ?
            """, (doc_id,))
            doc_status = c.fetchone()
            if doc_status:
                print(f"   Document Status: {doc_status[0]}, Chunks: {doc_status[1]}")
    else:
        print("   ℹ️  Documento 29-01-26-El Pais.pdf no encontrado en queue")
    
    # 4. Summary statistics
    print("\n4️⃣ RESUMEN ESTADÍSTICO")
    print("-" * 90)
    
    c.execute("SELECT COUNT(*) FROM processing_queue WHERE status = 'pending'")
    pending = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM processing_queue WHERE status = 'completed'")
    completed = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM worker_tasks WHERE status IN ('assigned', 'started')")
    active_workers = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT worker_id) FROM worker_tasks")
    total_workers_ever = c.fetchone()[0]
    
    print(f"   Tareas pendientes: {pending}")
    print(f"   Tareas completadas: {completed}")
    print(f"   Workers activos (assigned/started): {active_workers}")
    print(f"   Total workers (histórico): {total_workers_ever}")
    
    conn.close()
    
    print("\n" + "=" * 90)
    if not duplicates and not multi_worker:
        print("✅ DEDUPLICACIÓN OK - No hay duplicación de trabajo detectada")
    else:
        print("⚠️  DEDUPLICACIÓN CON ADVERTENCIAS - Revisar arriba")
    print("=" * 90)

if __name__ == "__main__":
    check_deduplication()
