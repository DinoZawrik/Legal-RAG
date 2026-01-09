#!/usr/bin/env python3
"""
Multimodal Search Pipeline - Type Definitions
==============================================

Enums and data models for multimodal search system.

Author: LegalRAG Development Team
License: MIT
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class SearchMode(Enum):
    """Search modes for multimodal pipeline."""

    SEMANTIC_ONLY = "semantic_only"
    STRUCTURAL_ONLY = "structural_only"
    CONSTRAINT_ONLY = "constraint_only"
    HYBRID_BASIC = "hybrid_basic"
    HYBRID_ADVANCED = "hybrid_advanced"
    MULTIMODAL_FULL = "multimodal_full"


class QueryType(Enum):
    """Query types for classification."""

    FACTUAL = "factual"
    NUMERICAL = "numerical"
    PROCEDURAL = "procedural"
    COMPARATIVE = "comparative"
    CONSTRAINT = "constraint"
    PROHIBITION = "prohibition"


@dataclass
class SearchResult:
    """Search result with multimodal metrics."""

    chunk_id: str
    document_id: str
    content: str

    semantic_score: float = 0.0
    structural_score: float = 0.0
    constraint_score: float = 0.0
    prohibition_score: float = 0.0

    relevance_score: float = 0.0
    confidence_score: float = 0.0
    completeness_score: float = 0.0

    final_score: float = 0.0

    matched_entities: List[Dict[str, Any]] = field(default_factory=list)
    matched_constraints: List[Dict[str, Any]] = field(default_factory=list)
    article_references: List[str] = field(default_factory=list)
    law_references: List[str] = field(default_factory=list)

    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'content': self.content,
            'semantic_score': self.semantic_score,
            'structural_score': self.structural_score,
            'constraint_score': self.constraint_score,
            'prohibition_score': self.prohibition_score,
            'relevance_score': self.relevance_score,
            'confidence_score': self.confidence_score,
            'completeness_score': self.completeness_score,
            'final_score': self.final_score,
            'matched_entities': self.matched_entities,
            'matched_constraints': self.matched_constraints,
            'article_references': self.article_references,
            'law_references': self.law_references,
            'explanation': self.explanation
        }


@dataclass
class QueryAnalysis:
    """Query analysis result."""

    original_query: str
    query_type: QueryType
    search_mode: SearchMode

    extracted_entities: List[str] = field(default_factory=list)
    numerical_constraints: List[Dict[str, Any]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    detected_law_references: List[str] = field(default_factory=list)
    detected_article_references: List[str] = field(default_factory=list)

    confidence: float = 1.0


__all__ = [
    "SearchMode",
    "QueryType",
    "SearchResult",
    "QueryAnalysis",
]
