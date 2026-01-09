#!/usr/bin/env python3
"""Universal Fact Verifier - Exports"""

from .types import FactStatement, FactType, VerificationResult, VerificationStatus
from .verifier import UniversalFactVerifier

__all__ = [
    "UniversalFactVerifier",
    "FactType",
    "VerificationStatus",
    "FactStatement",
    "VerificationResult",
]
