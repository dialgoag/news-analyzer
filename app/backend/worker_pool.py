"""
Generic Worker Pool Manager - Maintains persistent worker threads for ALL task types.

A single worker pool handles all pipeline tasks (OCR, chunking, indexing, insights).
Each worker can process any task type, providing automatic load balancing.

Architecture:
1. Create ONE pool of generic workers (e.g., 20 workers)
2. Each worker checks DB for ANY pending task (any type)
3. When found, worker dispatches to appropriate handler
4. After completion, goes back to waiting for next task (any type)

Benefits:
- Single pool to manage (simpler code)
- Automatic load balancing across task types
- No idle workers when one task type has backlog
- Easy to scale up/down globally
"""

import asyncio
import logging
import time
import os
from threading import Thread, Event, Lock
from datetime import datetime

logger = logging.getLogger(__name__)

# Lock to serialize OCR task claims - prevents race condition where multiple workers
# pass can_assign_ocr() before any commits, exceeding OCR_PARALLEL_WORKERS
_ocr_claim_lock = Lock()
_insights_claim_lock = Lock()


class GenericWorkerPool:
    """Manages a pool of generic workers that handle ALL task types."""
    
    def __init__(self, pool_size: int, task_dispatcher_func, db_connection_factory):
        """
        Args:
            pool_size: Number of generic workers to create
            task_dispatcher_func: Async function that dispatches tasks (generic_task_dispatcher)
            db_connection_factory: Function that returns DB connection
        """
        self.pool_size = pool_size
        self.task_dispatcher_func = task_dispatcher_func
        self.db_connection_factory = db_connection_factory
        
        self.workers = []
        self.stop_event = Event()
        self.running = False
    
    def start(self):
        """Start the generic worker pool."""
        if self.running:
            logger.warning("Generic worker pool already running")
            return
        
        logger.info(f"🚀 Starting generic worker pool with {self.pool_size} workers...")
        self.running = True
        self.stop_event.clear()
        
        for i in range(self.pool_size):
            worker_id = f"pipeline_worker_{i}"
            worker_thread = Thread(
                target=self._generic_worker_loop,
                args=(worker_id,),
                name=f"pool-{worker_id}",
                daemon=True
            )
            worker_thread.start()
            self.workers.append(worker_thread)
            logger.info(f"  ✅ {worker_id} started")
    
    def stop(self):
        """Stop all workers in the pool."""
        logger.info("🛑 Stopping generic worker pool...")
        self.running = False
        self.stop_event.set()
        
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers = []
        logger.info("  ✅ Pool stopped")
    
    def _generic_worker_loop(self, worker_id: str):
        """
        Main loop for a generic worker - continuously listens for ANY task type.
        This worker can process OCR, chunking, indexing, or insights tasks.
        """
        logger.info(f"{worker_id}: Starting generic main loop...")
        
        while self.running and not self.stop_event.is_set():
            try:
                conn = self.db_connection_factory()
                cursor = conn.cursor()
                
                # INTELLIGENT TASK ASSIGNMENT - COMPLETE DOCUMENTS FIRST
                # Strategy:
                # 1. PRIORITY: Finish pipeline stages (Insights > Indexing > Chunking > OCR)
                # 2. DYNAMIC: More workers to stages with MORE pending tasks
                # 3. MINIMUM: Guarantee at least 2 workers per stage IF pending tasks exist
                # Goal: Complete full documents instead of having many in OCR but none reaching insights
                
                task_found = False
                task_type = None
                task_data = {}
                
                # Check current worker distribution
                cursor.execute("""
                    SELECT task_type, COUNT(*) 
                    FROM processing_queue 
                    WHERE status = 'processing'
                    GROUP BY task_type
                """)
                # PostgreSQL returns dict-like rows, not tuples
                current_workers = {row['task_type']: row['count'] for row in cursor.fetchall()}
                
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM news_item_insights 
                    WHERE status = 'generating'
                """)
                # PostgreSQL returns dict row
                result = cursor.fetchone()
                current_workers['insights'] = result['count'] if result else 0
                
                # Check pending tasks (this determines priority)
                cursor.execute("""
                    SELECT task_type, COUNT(*) 
                    FROM processing_queue 
                    WHERE status = 'pending'
                    GROUP BY task_type
                """)
                # PostgreSQL returns dict-like rows
                pending_tasks = {row['task_type']: row['count'] for row in cursor.fetchall()}
                
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM news_item_insights 
                    WHERE status IN ('pending', 'queued')
                """)
                result = cursor.fetchone()
                pending_tasks['insights'] = result['count'] if result else 0
                
                # Priority order: COMPLETE PIPELINE (reverse order)
                priority_order = ['insights', 'indexing', 'chunking', 'ocr']
                
                # Minimum workers per stage (only if pending > 0)
                min_workers_per_stage = 2
                # OCR limit: max concurrent OCR workers (prevents Tika saturation)
                ocr_parallel_limit = int(os.getenv("OCR_PARALLEL_WORKERS", "5"))
                # Insights limit: max concurrent insights workers (prevents OpenAI 429)
                insights_parallel_limit = int(os.getenv("INSIGHTS_PARALLEL_WORKERS", "3"))
                
                def can_assign_ocr():
                    return current_workers.get('ocr', 0) < ocr_parallel_limit
                
                def can_assign_insights():
                    return current_workers.get('insights', 0) < insights_parallel_limit
                
                selected_task_type = None
                
                # PASS 1: Ensure minimum workers for stages with pending (prioritized by pipeline order)
                for task_type_check in priority_order:
                    current = current_workers.get(task_type_check, 0)
                    pending = pending_tasks.get(task_type_check, 0)
                    if task_type_check == 'ocr' and not can_assign_ocr():
                        continue
                    if task_type_check == 'insights' and not can_assign_insights():
                        continue
                    if pending > 0 and current < min_workers_per_stage:
                        selected_task_type = task_type_check
                        logger.debug(f"{worker_id}: Priority assignment to {task_type_check} (below min: {current}/{min_workers_per_stage}, {pending} pending)")
                        break
                
                # PASS 2: If all stages have minimum workers, assign to stage with MOST pending
                if not selected_task_type:
                    max_pending = 0
                    for task_type_check in priority_order:
                        pending = pending_tasks.get(task_type_check, 0)
                        if task_type_check == 'ocr' and not can_assign_ocr():
                            continue
                        if task_type_check == 'insights' and not can_assign_insights():
                            continue
                        if pending > max_pending:
                            max_pending = pending
                            selected_task_type = task_type_check
                    
                    if selected_task_type:
                        logger.debug(f"{worker_id}: Dynamic assignment to {selected_task_type} ({max_pending} pending - highest load)")
                
                # 1. Claim pipeline task (OCR, chunking, indexing)
                if selected_task_type in ['ocr', 'chunking', 'indexing']:
                    pipeline_task = None
                    ocr_lock_held = selected_task_type == 'ocr'
                    if ocr_lock_held:
                        _ocr_claim_lock.acquire()
                    try:
                        if ocr_lock_held:
                            cursor.execute("""
                                SELECT COUNT(*) FROM processing_queue
                                WHERE status = 'processing' AND task_type = 'ocr'
                            """)
                            result = cursor.fetchone()
                            count = result['count'] if result else 0
                            if count >= ocr_parallel_limit:
                                selected_task_type = None
                                task_found = False
                        if selected_task_type in ['ocr', 'chunking', 'indexing']:
                            cursor.execute("""
                                UPDATE processing_queue
                                SET status = 'processing'
                                WHERE id = (
                                    SELECT id FROM processing_queue
                                    WHERE status = 'pending' AND task_type = %s
                                    ORDER BY priority DESC, created_at ASC
                                    LIMIT 1
                                )
                                RETURNING task_type, document_id, filename, priority
                            """, (selected_task_type,))
                            pipeline_task = cursor.fetchone()
                    finally:
                        if ocr_lock_held:
                            _ocr_claim_lock.release()
                    
                    if pipeline_task:
                        task_type = pipeline_task['task_type']
                        task_data = {
                            'document_id': pipeline_task['document_id'],
                            'filename': pipeline_task['filename'],
                        }
                        task_found = True
                        conn.commit()
                        logger.info(f"{worker_id}: Claimed {task_type} task for {task_data['filename']} (Priority: complete pipeline)")
                
                # 2. Claim insights task (with concurrency lock, like OCR)
                elif selected_task_type == 'insights':
                    _insights_claim_lock.acquire()
                    try:
                        cursor.execute("""
                            SELECT COUNT(*) FROM news_item_insights
                            WHERE status = 'generating'
                        """)
                        result = cursor.fetchone()
                        generating_count = result['count'] if result else 0
                        if generating_count >= insights_parallel_limit:
                            selected_task_type = None
                            task_found = False
                        else:
                            cursor.execute("""
                                UPDATE news_item_insights
                                SET status = 'generating'
                                WHERE news_item_id = (
                                    SELECT news_item_id FROM news_item_insights
                                    WHERE status IN ('pending', 'queued')
                                    ORDER BY news_item_id ASC
                                    LIMIT 1
                                )
                                RETURNING news_item_id, document_id, filename, title
                            """)
                            insights_task = cursor.fetchone()
                            
                            if insights_task:
                                task_type = 'insights'
                                task_data = {
                                    'news_item_id': insights_task['news_item_id'],
                                    'document_id': insights_task['document_id'],
                                    'filename': insights_task['filename'],
                                    'title': insights_task['title'],
                                }
                                task_found = True
                                conn.commit()
                                logger.info(f"{worker_id}: Claimed insights task for {task_data.get('title') or task_data['filename']} (Priority: complete pipeline)")
                    finally:
                        _insights_claim_lock.release()
                
                conn.close()
                
                # 3. If no task found, sleep and retry
                if not task_found:
                    time.sleep(2)
                    continue
                
                # 4. Dispatch task to appropriate handler
                try:
                    # Create a new event loop for this thread (worker threads don't have one by default)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self.task_dispatcher_func(
                            task_type=task_type,
                            task_data=task_data,
                            worker_id=worker_id
                        ))
                    finally:
                        loop.close()
                except Exception as e:
                    logger.error(f"{worker_id}: Task {task_type} failed: {e}", exc_info=True)
                
            except Exception as e:
                logger.error(f"{worker_id}: Loop error: {e}", exc_info=True)
                time.sleep(1)
                continue


# Legacy WorkerPool class for backward compatibility (deprecated)
class WorkerPool(GenericWorkerPool):
    """
    Legacy WorkerPool - now wraps GenericWorkerPool.
    Kept for backward compatibility but discouraged.
    """
    def __init__(self, worker_type: str, pool_size: int, worker_task_func, db_connection_factory):
        logger.warning(f"WorkerPool with worker_type='{worker_type}' is deprecated. Use GenericWorkerPool instead.")
        super().__init__(pool_size, worker_task_func, db_connection_factory)
        self.worker_type = worker_type

