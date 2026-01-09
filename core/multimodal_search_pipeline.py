#!/usr/bin/env python3
"""
DEPRECATED: Backward Compatibility Wrapper
==========================================

This file provides backward compatibility for code that imports from:
    from core.multimodal_search_pipeline import MultimodalSearchPipeline, create_multimodal_search_pipeline

NEW LOCATION: Please update your imports to:
    from core.multimodal import MultimodalSearchPipeline

This wrapper will be removed in a future version.

Author: LegalRAG Cleanup Team
Date: 2025-10-02
"""

# Re-export from new modular location
from .multimodal import MultimodalSearchPipeline, QueryAnalyzer

# Legacy compatibility function
def create_multimodal_search_pipeline(*args, **kwargs):
    """
    DEPRECATED: Legacy factory function.
    Use MultimodalSearchPipeline() directly instead.
    """
    return MultimodalSearchPipeline(*args, **kwargs)

__all__ = ["MultimodalSearchPipeline", "QueryAnalyzer", "create_multimodal_search_pipeline"]
