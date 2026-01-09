#!/usr/bin/env python3
"""
Universal Prompt Framework - Backward Compatibility Module
===========================================================

Re-exports UniversalPromptFramework for seamless migration.

Usage:
    # Old import (still works):
    from core.universal_prompt_framework import UniversalPromptFramework
    
    # New import (recommended):
    from core.prompts import UniversalPromptFramework

Author: LegalRAG Development Team
License: MIT
"""

# Core types
from .types import (
    ConstraintLevel,
    PromptTemplate,
    ResponseFormat,
)

# Constraints and configuration
from .constraints import (
    AdaptivePromptConfig,
    PromptConstraints,
)

# Main framework
from .framework import (
    UniversalPromptFramework,
    get_universal_prompt_framework,
)

# Templates (utility functions)
from .templates import (
    get_anti_hallucination_rules,
    get_prompt_templates,
    get_response_formats,
)

__all__ = [
    # Main class
    "UniversalPromptFramework",
    "get_universal_prompt_framework",
    
    # Types
    "PromptTemplate",
    "ResponseFormat",
    "ConstraintLevel",
    
    # Configuration
    "PromptConstraints",
    "AdaptivePromptConfig",
    
    # Templates
    "get_prompt_templates",
    "get_response_formats",
    "get_anti_hallucination_rules",
]

__version__ = "2.0.0"
__author__ = "LegalRAG Development Team"
__license__ = "MIT"
