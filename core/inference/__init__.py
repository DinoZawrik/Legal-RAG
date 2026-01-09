#!/usr/bin/env python3
"""
Legal Inference - Backward Compatibility Module
================================================

Re-exports LegalInferenceEngine for seamless migration.

Usage:
    # Old import (still works):
    from core.legal_inference import LegalInferenceEngine
    
    # New import (recommended):
    from core.inference import LegalInferenceEngine

Author: LegalRAG Development Team
License: MIT
"""

# Core types
from .types import (
    ConflictType,
    InferenceResult,
    InferenceType,
    LegalConflict,
    LegalGap,
    LegalRule,
    LogicalOperator,
)

# Main engine
from .engine import (
    LegalInferenceEngine,
    get_legal_inference_engine,
)

# Rule parser
from .rule_parser import RuleParser

__all__ = [
    # Main class
    "LegalInferenceEngine",
    "get_legal_inference_engine",
    
    # Types
    "LogicalOperator",
    "ConflictType",
    "InferenceType",
    "LegalRule",
    "LegalConflict",
    "InferenceResult",
    "LegalGap",
    
    # Components
    "RuleParser",
]

__version__ = "2.0.0"
__author__ = "LegalRAG Development Team"
__license__ = "MIT"
