"""Compatibility wrapper for legacy imports."""

from core.processing.errors import ProcessingPipelineError
from core.processing.regulatory import RegulatoryPipeline

__all__ = ["RegulatoryPipeline", "ProcessingPipelineError"]
