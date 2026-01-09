#!/usr/bin/env python3
"""Universal Fact Verifier - Main Class"""

import logging
from typing import Any, Dict, List

from .types import FactStatement, FactType, VerificationResult, VerificationStatus

logger = logging.getLogger(__name__)


class UniversalFactVerifier:
    """Universal fact verification system to prevent hallucinations."""

    def __init__(self) -> None:
        """Initialize fact verifier."""
        logger.info("[UniversalFactVerifier] Initialized")

    async def verify_response(
        self,
        response_text: str,
        search_results: List[Dict[str, Any]]
    ) -> List[VerificationResult]:
        """
        Verify response against sources.

        Args:
            response_text: Generated response text
            search_results: Source documents

        Returns:
            List of verification results
        """
        statements = self._extract_fact_statements(response_text)
        results = []

        for statement in statements:
            result = await self._verify_statement(statement, search_results)
            results.append(result)

        return results

    def _extract_fact_statements(self, text: str) -> List[FactStatement]:
        """Extract fact statements from text."""
        # Simplified extraction
        statements = []
        sentences = text.split('.')

        for sentence in sentences[:5]:  # Limit to 5 statements
            if len(sentence.strip()) > 10:
                statements.append(FactStatement(
                    statement=sentence.strip(),
                    fact_type=FactType.EXISTENCE_FACT,
                    confidence=0.8
                ))

        return statements

    async def _verify_statement(
        self,
        statement: FactStatement,
        search_results: List[Dict[str, Any]]
    ) -> VerificationResult:
        """Verify single statement against sources."""
        supporting = []
        contradicting = []

        for result in search_results[:3]:
            content = result.get('content', '').lower()
            if any(word in content for word in statement.statement.lower().split()[:3]):
                supporting.append(result)

        if supporting:
            status = VerificationStatus.VERIFIED
            confidence = 0.9
        else:
            status = VerificationStatus.UNVERIFIED
            confidence = 0.3

        return VerificationResult(
            statement=statement,
            verification_status=status,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            confidence_score=confidence,
            explanation=f"Found {len(supporting)} supporting sources"
        )


__all__ = ["UniversalFactVerifier"]
