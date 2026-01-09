#!/usr/bin/env python3
"""
Smart Search - Type Definitions (Context7 validated).

This module contains enums and dataclasses for the universal smart search system
with proper type hints as per Context7 best practices.

Author: LegalRAG Development Team
License: MIT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..universal_legal_ner import UniversalLegalEntities


class QueryType(Enum):
    """Legal query types."""

    NUMERICAL_QUERY = "numerical_query"
    DEFINITION_QUERY = "definition_query"
    PROCEDURE_QUERY = "procedure_query"
    AUTHORITY_QUERY = "authority_query"
    REFERENCE_QUERY = "reference_query"
    CONDITION_QUERY = "condition_query"
    COMPARISON_QUERY = "comparison_query"
    GENERAL_QUERY = "general_query"


class SearchMode(Enum):
    """Search modes."""

    PRECISION = "precision"
    RECALL = "recall"
    BALANCED = "balanced"
    NUMERICAL_FOCUS = "numerical_focus"


@dataclass
class QueryAnalysis:
    """User query analysis result."""

    original_query: str
    query_type: QueryType
    search_mode: SearchMode

    entities: Any  # UniversalLegalEntities
    keywords: List[str]
    numerical_values: List[str]
    document_references: List[str]

    intent_confidence: float
    complexity_score: float
    ambiguity_score: float

    suggested_filters: Dict[str, Any] = field(default_factory=dict)
    boost_factors: Dict[str, float] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Search result with extended metadata."""

    content: str
    metadata: Dict[str, Any]

    semantic_score: float
    entity_match_score: float
    context_relevance_score: float
    authority_score: float
    recency_score: float
    final_score: float

    relevance_explanation: List[str]
    matched_entities: List[str]
    matched_keywords: List[str]

    chunk_priority: str
    search_criticality: float
    source_document: Optional[str] = None


@dataclass
class SmartSearchResults:
    """Collection of smart search results."""

    query_analysis: QueryAnalysis
    results: List[SearchResult]
    total_found: int

    search_stats: Dict[str, Any]
    performance_metrics: Dict[str, float]

    search_suggestions: List[str] = field(default_factory=list)
    alternative_queries: List[str] = field(default_factory=list)


__all__ = [
    "QueryType",
    "SearchMode",
    "QueryAnalysis",
    "SearchResult",
    "SmartSearchResults",
]
