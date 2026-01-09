#!/usr/bin/env python3
"""
Legal Inference - Type Definitions
===================================

Enums and data models for legal inference system.

Author: LegalRAG Development Team
License: MIT
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional


class LogicalOperator(Enum):
    """Logical operators for legal rules."""

    AND = "and"
    OR = "or"
    NOT = "not"
    IF_THEN = "if_then"
    IFF = "iff"
    XOR = "xor"


class ConflictType(Enum):
    """Types of legal conflicts."""

    TEMPORAL = "temporal"
    HIERARCHICAL = "hierarchical"
    TERRITORIAL = "territorial"
    SUBSTANTIVE = "substantive"
    PROCEDURAL = "procedural"


class InferenceType(Enum):
    """Types of legal inferences."""

    DEDUCTIVE = "deductive"
    INDUCTIVE = "inductive"
    ANALOGICAL = "analogical"
    A_FORTIORI = "a_fortiori"
    A_CONTRARIO = "a_contrario"


@dataclass
class LegalRule:
    """Legal norm as logical rule."""

    rule_id: str
    document_type: any  # DocumentType
    document_title: str
    article_number: Optional[str]
    part_number: Optional[str]

    conditions: List[str]
    consequences: List[str]
    exceptions: List[str] = field(default_factory=list)
    operator: LogicalOperator = LogicalOperator.IF_THEN

    validity_start: Optional[date] = None
    validity_end: Optional[date] = None
    territorial_scope: str = "РФ"
    hierarchy_level: int = 0

    overrides: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    implements: List[str] = field(default_factory=list)

    legal_concepts: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class LegalConflict:
    """Legal conflict between norms."""

    conflict_id: str
    conflict_type: ConflictType
    conflicting_rules: List[LegalRule]
    description: str
    severity: float

    suggested_resolution: Optional[str] = None
    resolution_principle: Optional[str] = None

    factual_circumstances: List[str] = field(default_factory=list)
    affected_rights: List[str] = field(default_factory=list)


@dataclass
class InferenceResult:
    """Result of legal inference."""

    conclusion: str
    inference_type: InferenceType
    confidence: float

    premises: List[LegalRule]
    logical_chain: List[str]

    supporting_evidence: List[str] = field(default_factory=list)
    counterarguments: List[str] = field(default_factory=list)

    applicable_exceptions: List[str] = field(default_factory=list)
    legal_uncertainties: List[str] = field(default_factory=list)


@dataclass
class LegalGap:
    """Legal gap (lacuna) in legislation."""

    gap_id: str
    description: str
    affected_area: str
    gap_type: str

    relevant_rules: List[LegalRule] = field(default_factory=list)
    suggested_analogies: List[str] = field(default_factory=list)
    filling_strategies: List[str] = field(default_factory=list)

    severity: float = 0.5
    identified_by: str = "system"


__all__ = [
    "LogicalOperator",
    "ConflictType",
    "InferenceType",
    "LegalRule",
    "LegalConflict",
    "InferenceResult",
    "LegalGap",
]
