#!/usr/bin/env python3
"""
Smart Search - Backward Compatibility Module.

Re-exports all smart search components for seamless migration from
core.universal_smart_search to core.smart_search.

Usage:
    # Old import (still works):
    from core.universal_smart_search import UniversalSmartSearch

    # New import (recommended):
    from core.smart_search import UniversalSmartSearch

Author: LegalRAG Development Team
License: MIT
"""

from .search_engine import UniversalSmartSearch, get_universal_smart_search
from .types import (
    QueryAnalysis,
    QueryType,
    SearchMode,
    SearchResult,
    SmartSearchResults,
)

__all__ = [
    "UniversalSmartSearch",
    "get_universal_smart_search",
    "QueryType",
    "SearchMode",
    "QueryAnalysis",
    "SearchResult",
    "SmartSearchResults",
]

__version__ = "2.0.0"
__author__ = "LegalRAG Development Team"
__license__ = "MIT"
