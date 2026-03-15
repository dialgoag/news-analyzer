"""
Migration 011: Create OCR performance log for post-mortem analysis

Domain: OCR Performance & Learning
Description: Table for logging OCR successes, failures, and timeouts to enable adaptive timeout learning
Depends on: 003_event_driven_schema
"""

from yoyo import step

steps = [
    step(
        # OCR performance log - for adaptive timeout learning and post-mortem analysis
        """
        CREATE TABLE IF NOT EXISTS ocr_performance_log (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(500) NOT NULL,
            file_size_mb DECIMAL(10, 2) NOT NULL,
            success BOOLEAN NOT NULL,
            processing_time_sec DECIMAL(10, 2),
            timeout_used_sec INT NOT NULL,
            error_type VARCHAR(100),
            error_detail TEXT,
            timestamp TIMESTAMP DEFAULT NOW() NOT NULL
        )
        """,
        "DROP TABLE IF EXISTS ocr_performance_log"
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_ocr_perf_timestamp ON ocr_performance_log(timestamp)",
        "DROP INDEX IF EXISTS idx_ocr_perf_timestamp"
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_ocr_perf_success ON ocr_performance_log(success)",
        "DROP INDEX IF EXISTS idx_ocr_perf_success"
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_ocr_perf_error_type ON ocr_performance_log(error_type)",
        "DROP INDEX IF EXISTS idx_ocr_perf_error_type"
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_ocr_perf_file_size ON ocr_performance_log(file_size_mb)",
        "DROP INDEX IF EXISTS idx_ocr_perf_file_size"
    )
]
