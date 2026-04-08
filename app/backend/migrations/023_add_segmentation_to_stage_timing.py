"""
Add 'segmentation' stage to document_stage_timing check constraint

Migration: 023_add_segmentation_to_stage_timing
"""

from yoyo import step

__depends__ = ['022_add_segmentation_columns']

steps = [
    step(
        """
        ALTER TABLE document_stage_timing 
        DROP CONSTRAINT IF EXISTS document_stage_timing_stage_check;
        
        ALTER TABLE document_stage_timing
        ADD CONSTRAINT document_stage_timing_stage_check 
        CHECK (stage IN ('upload', 'ocr', 'segmentation', 'chunking', 'indexing', 'insights', 'insights_indexing'));
        """,
        """
        ALTER TABLE document_stage_timing 
        DROP CONSTRAINT IF EXISTS document_stage_timing_stage_check;
        
        ALTER TABLE document_stage_timing
        ADD CONSTRAINT document_stage_timing_stage_check 
        CHECK (stage IN ('upload', 'ocr', 'chunking', 'indexing', 'insights', 'insights_indexing'));
        """
    ),
]
