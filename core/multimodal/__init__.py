#!/usr/bin/env python3
"""
Multimodal Search Pipeline - Backward Compatibility Module
===========================================================

Re-exports MultimodalSearchPipeline for seamless migration.

Author: LegalRAG Development Team
License: MIT
"""

from .types import (
    QueryAnalysis,
    QueryType,
    SearchMode,
    SearchResult,
)

from .query_analyzer import QueryAnalyzer

from .pipeline import MultimodalSearchPipeline

__all__ = [
    # Main class
    "MultimodalSearchPipeline",
    
    # Types
    "SearchMode",
    "QueryType",
    "SearchResult",
    "QueryAnalysis",
    
    # Components
    "QueryAnalyzer",
]

__version__ = "2.0.0"
__author__ = "LegalRAG Development Team"
__license__ = "MIT"
