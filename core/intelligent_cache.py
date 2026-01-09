#!/usr/bin/env python3
"""
DEPRECATED: Backward Compatibility Wrapper
==========================================

This file provides backward compatibility for code that imports from:
    from core.intelligent_cache import IntelligentCache, get_intelligent_cache, CacheStrategy

NEW LOCATION: Please update your imports to:
    from core.cache import IntelligentCache

This wrapper will be removed in a future version.

Author: LegalRAG Cleanup Team
Date: 2025-10-02
"""

# Re-export from new modular location
from .cache import IntelligentCache

# Also export enums and helper functions if they exist in old file
try:
    from .cache.cache import CacheStrategy, CacheLevel, CacheEntry, CacheStats
except ImportError:
    # Fallback: define basic enums if not available in new module
    from enum import Enum
    
    class CacheStrategy(Enum):
        """Стратегии управления кэшем."""
        LRU = "lru"
        LFU = "lfu"
        TTL = "ttl"
        ADAPTIVE = "adaptive"

# Legacy compatibility function
async def get_intelligent_cache() -> IntelligentCache:
    """
    DEPRECATED: Legacy function for backward compatibility.
    
    Returns global IntelligentCache instance.
    Prefer creating instances directly: IntelligentCache()
    """
    return IntelligentCache()

__all__ = [
    "IntelligentCache",
    "get_intelligent_cache", 
    "CacheStrategy",
]
