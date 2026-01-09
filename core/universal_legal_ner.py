#!/usr/bin/env python3
"""
DEPRECATED: Backward Compatibility Wrapper
==========================================

This file provides backward compatibility for code that imports from:
    from core.universal_legal_ner import UniversalLegalNER

NEW LOCATION: Please update your imports to:
    from core.ner import UniversalLegalNER

This wrapper will be removed in a future version.

Author: LegalRAG Cleanup Team
Date: 2025-10-02
"""

# Re-export from new modular location
from .ner import UniversalLegalNER
from enum import Enum

# Backward compatibility: EntityType stub
class EntityType(Enum):
    """Stub class for backward compatibility."""
    LAW = "law"
    ARTICLE = "article"
    PART = "part"
    CLAUSE = "clause"
    NUMERICAL_CONSTRAINT = "numerical_constraint"

# Backward compatibility alias
UniversalLegalEntities = UniversalLegalNER

# Legacy compatibility function
def get_universal_legal_ner():
    """
    DEPRECATED: Legacy function for backward compatibility.
    Returns UniversalLegalNER instance.
    """
    return UniversalLegalNER()

__all__ = ["UniversalLegalNER", "UniversalLegalEntities", "EntityType", "get_universal_legal_ner"]
