#!/usr/bin/env python3
"""
Script para verificar estado de workers y tareas pendientes usando los repositorios hexagonales.
Ejecutar desde app/backend con: python check_workers_script.py
Requiere: POSTGRES_* o DATABASE_URL en .env
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

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

from adapters.driven.persistence.postgres import (
    PostgresWorkerRepository,
    PostgresNewsItemRepository,
)


def _minutes_running(started_at) -> float:
    if not started_at:
        return 0.0
    if isinstance(started_at, str):
        try:
            started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
    if isinstance(started_at, datetime):
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - started_at
        return max(delta.total_seconds() / 60.0, 0.0)
    return 0.0


async def main_async():
    worker_repo = PostgresWorkerRepository()
    news_repo = PostgresNewsItemRepository()

    print("=" * 70)
    print("VERIFICACIÓN DE WORKERS Y TAREAS PENDIENTES")
    print("=" * 70)

    worker_summary = await worker_repo.get_worker_status_summary()
    print("\n📊 WORKER_TASKS por estado:")
    for status, count in sorted(worker_summary.items()):
        print(f"   {status}: {count}")

    active = await worker_repo.list_active_with_documents()
    print(f"\n🔧 WORKERS ACTIVOS (assigned/started): {len(active)}")
    stuck = 0
    for row in active:
        minutes = row.get("minutes_running")
        if minutes is None:
            minutes = _minutes_running(row.get("started_at"))
        is_stuck = minutes > 20
        if is_stuck:
            stuck += 1
        flag = " ⚠️ STUCK (>20 min)" if is_stuck else ""
        filename = row.get("filename") or row.get("document_id") or "-"
        print(f"   {row.get('worker_id')} | {row.get('task_type')} | {filename[:40]} | {minutes:.1f} min{flag}")
    if stuck:
        print(f"\n   ⚠️ {stuck} worker(s) bloqueados (>20 min) - posible crash o deadlock")

    errors = await worker_repo.list_recent_errors_with_documents(hours=24, limit=15)
    print(f"\n❌ WORKERS CON ERROR (últimas 24h): {len(errors)}")
    for row in errors[:5]:
        filename = row.get("filename") or row.get("worker_id")
        error_message = (row.get("error_message") or "")[:60]
        print(f"   {row.get('task_type')} | {filename} | {error_message}...")

    queue_status = await worker_repo.get_processing_queue_status()
    print("\n📋 PROCESSING_QUEUE:")
    for task_type in sorted(queue_status.keys()):
        states = queue_status[task_type]
        pending = states.get("pending", 0)
        processing = states.get("processing", 0)
        completed = states.get("completed", 0)
        print(f"   {task_type}: pending={pending}, processing={processing}, completed={completed}")

    insight_counts = await news_repo.count_insights_by_status()
    print("\n📰 NEWS_ITEM_INSIGHTS:")
    for status, count in sorted(insight_counts.items()):
        print(f"   {status}: {count}")

    orphaned = await worker_repo.count_processing_orphans()
    if orphaned:
        print(f"\n⚠️ TAREAS HUÉRFANAS (processing sin worker): {orphaned}")

    pool_size = int(os.getenv("PIPELINE_WORKERS_COUNT", "20"))
    ocr_limit = int(os.getenv("OCR_PARALLEL_WORKERS", str(pool_size)))
    insights_limit = int(os.getenv("INSIGHTS_PARALLEL_WORKERS", str(pool_size)))
    indexing_limit = int(os.getenv("INDEXING_PARALLEL_WORKERS", "8"))
    indexing_insights_limit = int(os.getenv("INDEXING_INSIGHTS_PARALLEL_WORKERS", "8"))
    print(
        f"\n⚙️ LÍMITES (env): pool={pool_size}, OCR={ocr_limit}, "
        f"insights={insights_limit}, indexing={indexing_limit}, indexing_insights={indexing_insights_limit}"
    )

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main_async())
