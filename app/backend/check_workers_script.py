#!/usr/bin/env python3
"""
Script para verificar estado de workers y tareas pendientes.
Ejecutar desde app/backend con: python check_workers_script.py
Requiere: POSTGRES_* o DATABASE_URL en .env
"""
import os
import sys
from pathlib import Path

# Asegurar que el backend está en el path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

# Cargar .env si existe
env_file = backend_dir.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from database import document_status_store

def main():
    conn = document_status_store.get_connection()
    cursor = conn.cursor()

    print("=" * 70)
    print("VERIFICACIÓN DE WORKERS Y TAREAS PENDIENTES")
    print("=" * 70)

    # 1. Worker tasks por estado
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM worker_tasks
        GROUP BY status
        ORDER BY status
    """)
    wt_summary = cursor.fetchall()
    print("\n📊 WORKER_TASKS por estado:")
    for row in wt_summary:
        print(f"   {row['status']}: {row['count']}")

    # 2. Workers activos (assigned/started) con tiempo de ejecución
    cursor.execute("""
        SELECT 
            wt.worker_id, wt.task_type, wt.document_id, ds.filename,
            wt.status, wt.started_at, wt.error_message,
            EXTRACT(EPOCH FROM (NOW() - wt.started_at))/60 as minutes_running
        FROM worker_tasks wt
        LEFT JOIN document_status ds ON wt.document_id = ds.document_id
        WHERE wt.status IN ('assigned', 'started')
        ORDER BY wt.started_at ASC
    """)
    active = cursor.fetchall()
    print(f"\n🔧 WORKERS ACTIVOS (assigned/started): {len(active)}")
    stuck_count = 0
    for row in active:
        mins = row['minutes_running'] or 0
        is_stuck = mins > 20
        if is_stuck:
            stuck_count += 1
        flag = " ⚠️ STUCK (>20 min)" if is_stuck else ""
        fn = row['filename'] or row['document_id'] or "-"
        print(f"   {row['worker_id']} | {row['task_type']} | {fn[:40]} | {mins:.1f} min{flag}")

    if stuck_count > 0:
        print(f"\n   ⚠️ {stuck_count} worker(s) bloqueados (>20 min) - posible crash o deadlock")

    # 3. Workers con error (últimas 24h)
    cursor.execute("""
        SELECT wt.worker_id, wt.task_type, ds.filename, wt.error_message, wt.completed_at
        FROM worker_tasks wt
        LEFT JOIN document_status ds ON wt.document_id = ds.document_id
        WHERE wt.status = 'error'
        AND wt.completed_at > NOW() - INTERVAL '24 hours'
        ORDER BY wt.completed_at DESC
        LIMIT 15
    """)
    errors = cursor.fetchall()
    print(f"\n❌ WORKERS CON ERROR (últimas 24h): {len(errors)}")
    for row in errors[:5]:
        err = (row['error_message'] or "")[:60]
        print(f"   {row['task_type']} | {row['filename'] or row['worker_id']} | {err}...")

    # 4. Processing queue por tipo y estado
    cursor.execute("""
        SELECT task_type, status, COUNT(*) as count
        FROM processing_queue
        GROUP BY task_type, status
        ORDER BY task_type, status
    """)
    pq = cursor.fetchall()
    print("\n📋 PROCESSING_QUEUE:")
    by_type = {}
    for row in pq:
        t = row['task_type']
        if t not in by_type:
            by_type[t] = {}
        by_type[t][row['status']] = row['count']
    for t in sorted(by_type.keys()):
        s = by_type[t]
        pending = s.get('pending', 0)
        processing = s.get('processing', 0)
        completed = s.get('completed', 0)
        print(f"   {t}: pending={pending}, processing={processing}, completed={completed}")

    # 5. Insights pendientes
    cursor.execute("""
        SELECT status, COUNT(*) FROM news_item_insights
        GROUP BY status
    """)
    insights = cursor.fetchall()
    print("\n📰 NEWS_ITEM_INSIGHTS:")
    for row in insights:
        print(f"   {row['status']}: {row['count']}")

    # 6. Tareas huérfanas (processing sin worker activo)
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM processing_queue pq
        WHERE pq.status = 'processing'
        AND NOT EXISTS (
            SELECT 1 FROM worker_tasks wt
            WHERE wt.document_id = pq.document_id
            AND wt.task_type = pq.task_type
            AND wt.status IN ('assigned', 'started')
        )
    """)
    orphaned = cursor.fetchone()['count']
    if orphaned > 0:
        print(f"\n⚠️ TAREAS HUÉRFANAS (processing sin worker): {orphaned}")

    # 7. Límites de workers (env)
    pool_size = int(os.getenv("PIPELINE_WORKERS_COUNT", "20"))
    ocr_limit = int(os.getenv("OCR_PARALLEL_WORKERS", str(pool_size)))
    insights_limit = int(os.getenv("INSIGHTS_PARALLEL_WORKERS", str(pool_size)))
    indexing_limit = int(os.getenv("INDEXING_PARALLEL_WORKERS", "8"))
    indexing_insights_limit = int(os.getenv("INDEXING_INSIGHTS_PARALLEL_WORKERS", "8"))
    print(f"\n⚙️ LÍMITES (env): pool={pool_size}, OCR={ocr_limit}, insights={insights_limit}, indexing={indexing_limit}, indexing_insights={indexing_insights_limit}")

    conn.close()
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
