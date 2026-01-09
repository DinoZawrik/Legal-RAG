#!/usr/bin/env python3
"""
DEPRECATED: Backward Compatibility Wrapper
==========================================

This file provides backward compatibility for code that imports from:
    from core.universal_prompt_framework import <classes>

NEW LOCATION: Please update your imports to:
    from core.prompts import <classes>

This wrapper will be removed in a future version.

Author: LegalRAG Cleanup Team
Date: 2025-10-02
"""

# Re-export everything from new modular location
from .prompts import *

__all__ = [
    "UniversalPromptFramework",
    "get_universal_prompt_framework",
    "PromptTemplate",
    "ResponseFormat",
    "ConstraintLevel",
    "PromptConstraints",
    "AdaptivePromptConfig",
    "get_prompt_templates",
    "get_response_formats",
    "get_anti_hallucination_rules",
]
