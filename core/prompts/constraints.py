#!/usr/bin/env python3
"""
Universal Prompt Framework - Constraints and Configuration (Context7 validated).
=================================================================================

Data models for prompt constraints and adaptive configuration with proper
type hints as per Context7 best practices.

This module contains dataclasses that define:
- PromptConstraints: Constraints for prompt generation to prevent hallucinations
- AdaptivePromptConfig: Configuration for adaptive prompt generation

Author: LegalRAG Development Team
License: MIT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..universal_smart_search import QueryAnalysis, SmartSearchResults

from .types import ConstraintLevel, PromptTemplate, ResponseFormat


@dataclass
class PromptConstraints:
    """
    Constraints for prompt generation to prevent hallucinations.

    Attributes:
        require_source_attribution: Require source citations
        require_exact_quotes: Require exact quotes from sources
        forbid_extrapolation: Forbid extrapolating beyond sources
        forbid_speculation: Forbid speculative statements
        numerical_precision_required: Require precise numerical data
        verify_numerical_context: Verify context of numerical values
        forbid_numerical_approximation: Forbid approximating numbers
        required_sections: Required response sections
        forbidden_phrases: Phrases forbidden in response
        mandatory_disclaimers: Disclaimers that must be included
        context_preservation_level: Level of context preservation
        citation_format: Citation format style
        uncertainty_handling: How to handle uncertainty
    """

    require_source_attribution: bool = True
    require_exact_quotes: bool = False
    forbid_extrapolation: bool = True
    forbid_speculation: bool = True

    numerical_precision_required: bool = True
    verify_numerical_context: bool = True
    forbid_numerical_approximation: bool = True

    required_sections: List[str] = field(default_factory=list)
    forbidden_phrases: List[str] = field(default_factory=list)
    mandatory_disclaimers: List[str] = field(default_factory=list)

    context_preservation_level: ConstraintLevel = ConstraintLevel.HIGH
    citation_format: str = "strict"
    uncertainty_handling: str = "explicit"


@dataclass
class AdaptivePromptConfig:
    """
    Configuration for adaptive prompt generation.

    Attributes:
        query_analysis: Analysis of user query
        search_results: Search results
        template_type: Prompt template to use
        response_format: Response format style
        constraints: Constraints to apply
        complexity_level: Query complexity level
        technical_depth: Technical depth level
        user_expertise_assumed: Assumed user expertise
        source_count: Number of sources available
        entity_types_present: Types of entities in results
        has_numerical_data: Whether results contain numerical data
        has_procedural_content: Whether results contain procedures
    """

    query_analysis: Any  # QueryAnalysis
    search_results: Any  # SmartSearchResults
    template_type: PromptTemplate
    response_format: ResponseFormat
    constraints: PromptConstraints

    complexity_level: str
    technical_depth: str
    user_expertise_assumed: str

    source_count: int
    entity_types_present: List[str]
    has_numerical_data: bool
    has_procedural_content: bool


__all__ = [
    "PromptConstraints",
    "AdaptivePromptConfig",
]
