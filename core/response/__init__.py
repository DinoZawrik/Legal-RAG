#!/usr/bin/env python3
"""
Enhanced Response Generator - Backward Compatibility Module
============================================================

Re-exports EnhancedResponseGenerator for seamless migration.

Author: LegalRAG Development Team
License: MIT
"""

from .types import (
    ResponseMetrics,
    ResponseQuality,
    ResponseSection,
    StructuredResponse,
)

from .generator import EnhancedResponseGenerator

__all__ = [
    # Main class
    "EnhancedResponseGenerator",
    
    # Types
    "ResponseQuality",
    "ResponseSection",
    "ResponseMetrics",
    "StructuredResponse",
]

__version__ = "2.0.0"
__author__ = "LegalRAG Development Team"
__license__ = "MIT"
