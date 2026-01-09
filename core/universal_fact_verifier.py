#!/usr/bin/env python3
"""
DEPRECATED: Backward Compatibility Wrapper
==========================================

This file provides backward compatibility for code that imports from:
    from core.universal_fact_verifier import UniversalFactVerifier

NEW LOCATION: Please update your imports to:
    from core.verifier import UniversalFactVerifier

This wrapper will be removed in a future version.

Author: LegalRAG Cleanup Team
Date: 2025-10-02
"""

# Re-export from new modular location
from .verifier import UniversalFactVerifier

__all__ = ["UniversalFactVerifier"]
