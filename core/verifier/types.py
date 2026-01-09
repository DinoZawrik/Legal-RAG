#!/usr/bin/env python3
"""Universal Fact Verifier - Types"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FactType(Enum):
    NUMERICAL_FACT = "numerical_fact"
    DEFINITIONAL_FACT = "definitional_fact"
    PROCEDURAL_FACT = "procedural_fact"
    AUTHORITY_FACT = "authority_fact"
    REFERENCE_FACT = "reference_fact"
    CONDITIONAL_FACT = "conditional_fact"
    EXISTENCE_FACT = "existence_fact"


class VerificationStatus(Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"


@dataclass
class FactStatement:
    statement: str
    fact_type: FactType
    confidence: float
    source_references: List[str] = field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED


@dataclass
class VerificationResult:
    statement: FactStatement
    verification_status: VerificationStatus
    supporting_evidence: List[Dict[str, Any]] = field(default_factory=list)
    contradicting_evidence: List[Dict[str, Any]] = field(default_factory=list)
    confidence_score: float = 0.0
    explanation: str = ""


__all__ = ["FactType", "VerificationStatus", "FactStatement", "VerificationResult"]
