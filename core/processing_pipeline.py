#!/usr/bin/env python3
"""Compatibility wrapper for legacy imports."""

from core.processing.ingestion import IngestionPipeline
from core.processing.regulatory import RegulatoryPipeline
from core.processing.unified import UnifiedDocumentProcessor
from core.processing.errors import ProcessingPipelineError
from core.infrastructure_suite import DocumentType

__all__ = [
    "IngestionPipeline",
    "RegulatoryPipeline",
    "UnifiedDocumentProcessor",
    "ProcessingPipelineError",
    "DocumentType",
]
