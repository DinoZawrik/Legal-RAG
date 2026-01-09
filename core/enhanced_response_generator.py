#!/usr/bin/env python3
"""
DEPRECATED: Backward Compatibility Wrapper
==========================================

This file provides backward compatibility for code that imports from:
    from core.enhanced_response_generator import <classes>

NEW LOCATION: Please update your imports to:
    from core.response import <classes>

This wrapper will be removed in a future version.

Author: LegalRAG Cleanup Team
Date: 2025-10-02
"""

# Re-export everything from new modular location
from .response import *

__all__ = ["ResponseGenerator", "ResponseType"]
