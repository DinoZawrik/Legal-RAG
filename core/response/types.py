#!/usr/bin/env python3
"""
Enhanced Response Generator - Type Definitions
===============================================

Enums and data models for response generation system.

Author: LegalRAG Development Team
License: MIT
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ResponseQuality(Enum):
    """Response quality levels."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


class ResponseSection(Enum):
    """Structured response sections."""

    SUMMARY = "summary"
    LEGAL_BASIS = "legal_basis"
    DETAILED_ANALYSIS = "detailed_analysis"
    PRACTICAL_STEPS = "practical_steps"
    RISKS_WARNINGS = "risks_warnings"
    ADDITIONAL_INFO = "additional_info"
    SOURCES = "sources"
    FOLLOW_UP = "follow_up"


@dataclass
class ResponseMetrics:
    """Response quality metrics."""

    completeness: float
    accuracy: float
    clarity: float
    relevance: float
    legal_depth: float
    user_adaptation: float

    overall_quality: ResponseQuality = ResponseQuality.ACCEPTABLE


@dataclass
class StructuredResponse:
    """Structured legal response."""

    query: str
    response_id: str
    timestamp: datetime
    user_expertise: any  # UserExpertiseLevel

    sections: Dict[ResponseSection, str] = field(default_factory=dict)

    legal_reasoning: Optional[Dict[str, Any]] = None
    inferences: List[Any] = field(default_factory=list)  # InferenceResult
    conflicts: List[Any] = field(default_factory=list)   # LegalConflict
    sources: List[Dict[str, Any]] = field(default_factory=list)

    metrics: Optional[ResponseMetrics] = None
    validation_status: str = "pending"
    warnings: List[str] = field(default_factory=list)

    follow_up_questions: List[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """Get summary section (compatibility with tests)."""
        return self.sections.get(ResponseSection.SUMMARY, "Answer unavailable")


__all__ = [
    "ResponseQuality",
    "ResponseSection",
    "ResponseMetrics",
    "StructuredResponse",
]
