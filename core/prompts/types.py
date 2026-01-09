#!/usr/bin/env python3
"""
Universal Prompt Framework - Type Definitions (Context7 validated).
====================================================================

Enums and type definitions for the prompt framework with proper
type hints as per Context7 best practices.

This module defines the core types used throughout the prompt framework:
- PromptTemplate: Types of prompt templates for different query types
- ResponseFormat: Response formatting styles
- ConstraintLevel: Constraint strictness levels for anti-hallucination

Author: LegalRAG Development Team
License: MIT
"""

from __future__ import annotations

from enum import Enum


class PromptTemplate(Enum):
    """Types of prompt templates for different query types."""

    STRICT_FACTUAL = "strict_factual"
    NUMERICAL_VERIFICATION = "numerical_verification"
    DEFINITION_PRECISE = "definition_precise"
    PROCEDURE_STEP_BY_STEP = "procedure_step_by_step"
    AUTHORITY_CLEAR = "authority_clear"
    REFERENCE_BASED = "reference_based"
    COMPARATIVE_ANALYSIS = "comparative_analysis"
    GENERAL_CONSTRAINED = "general_constrained"


class ResponseFormat(Enum):
    """Response formatting styles."""

    STRUCTURED_SECTIONS = "structured_sections"
    BULLET_POINTS = "bullet_points"
    NUMBERED_STEPS = "numbered_steps"
    DEFINITION_FORMAT = "definition_format"
    QUESTION_ANSWER = "question_answer"
    COMPARISON_TABLE = "comparison_table"


class ConstraintLevel(Enum):
    """Constraint strictness levels for anti-hallucination."""

    MAXIMUM = "maximum"
    HIGH = "high"
    MEDIUM = "medium"
    MINIMAL = "minimal"


__all__ = [
    "PromptTemplate",
    "ResponseFormat",
    "ConstraintLevel",
]
