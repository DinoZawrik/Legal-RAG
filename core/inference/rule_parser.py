#!/usr/bin/env python3
"""
Legal Inference - Rule Parser
==============================

Parses legal rules from text content.

Author: LegalRAG Development Team
License: MIT
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .types import LegalRule, LogicalOperator

logger = logging.getLogger(__name__)


class RuleParser:
    """Parses legal rules from document content."""

    def __init__(self, legal_ontology: Any) -> None:
        """
        Initialize rule parser.

        Args:
            legal_ontology: LegalOntology instance
        """
        self.legal_ontology = legal_ontology
        self.rules_database: Dict[str, LegalRule] = {}

    def parse_legal_rule(self, content: str, metadata: Dict[str, Any]) -> Optional[LegalRule]:
        """
        Extract legal rule from document text.

        Args:
            content: Document text content
            metadata: Document metadata

        Returns:
            Parsed LegalRule or None if parsing fails
        """
        try:
            from ..legal_ontology import DocumentType

            rule_id = f"{metadata.get('document_type', 'unknown')}_{metadata.get('article_number', 'na')}_{hash(content) % 10000}"

            doc_type_str = metadata.get('document_type', '')
            document_type = None
            for dt in DocumentType:
                if dt.value.lower() in doc_type_str.lower():
                    document_type = dt
                    break

            if not document_type:
                document_type = DocumentType.OTHER

            conditions = self._extract_conditions(content)
            consequences = self._extract_consequences(content)
            exceptions = self._extract_exceptions(content)
            legal_concepts = self._extract_legal_concepts(content)
            keywords = self._extract_keywords(content)

            hierarchy_level = self.legal_ontology.DOCUMENT_HIERARCHY.get(document_type, 999)

            rule = LegalRule(
                rule_id=rule_id,
                document_type=document_type,
                document_title=metadata.get('document_title', 'Unknown document'),
                article_number=metadata.get('article_number'),
                part_number=metadata.get('part_number'),
                conditions=conditions,
                consequences=consequences,
                exceptions=exceptions,
                hierarchy_level=hierarchy_level,
                legal_concepts=legal_concepts,
                keywords=keywords,
                confidence=0.8
            )

            self.rules_database[rule_id] = rule
            return rule

        except Exception as e:
            logger.warning(f"Error extracting legal rule: {e}")
            return None

    def _extract_conditions(self, text: str) -> List[str]:
        """Extract rule application conditions from text."""
        conditions = []
        condition_patterns = [
            r'если\s+([^,\.]+)',
            r'при\s+условии\s+([^,\.]+)',
            r'в\s+случае\s+([^,\.]+)',
            r'при\s+наличии\s+([^,\.]+)',
            r'когда\s+([^,\.]+)',
            r'в\s+случаях?\s+([^,\.]+)'
        ]

        for pattern in condition_patterns:
            matches = re.finditer(pattern, text.lower(), re.IGNORECASE)
            for match in matches:
                condition = match.group(1).strip()
                if len(condition) > 5:
                    conditions.append(condition)

        return list(set(conditions))

    def _extract_consequences(self, text: str) -> List[str]:
        """Extract legal consequences from text."""
        consequences = []
        consequence_patterns = [
            r'влечет\s+([^,\.]+)',
            r'наказывается\s+([^,\.]+)',
            r'карается\s+([^,\.]+)',
            r'подлежит\s+([^,\.]+)',
            r'обязан\s+([^,\.]+)',
            r'имеет\s+право\s+([^,\.]+)',
            r'вправе\s+([^,\.]+)'
        ]

        for pattern in consequence_patterns:
            matches = re.finditer(pattern, text.lower(), re.IGNORECASE)
            for match in matches:
                consequence = match.group(1).strip()
                if len(consequence) > 5:
                    consequences.append(consequence)

        return list(set(consequences))

    def _extract_exceptions(self, text: str) -> List[str]:
        """Extract exceptions from text."""
        exceptions = []
        exception_patterns = [
            r'за\s+исключением\s+([^,\.]+)',
            r'кроме\s+случаев\s+([^,\.]+)',
            r'не\s+распространяется\s+на\s+([^,\.]+)',
            r'исключение\s+составляют\s+([^,\.]+)',
            r'не\s+применяется\s+к\s+([^,\.]+)'
        ]

        for pattern in exception_patterns:
            matches = re.finditer(pattern, text.lower(), re.IGNORECASE)
            for match in matches:
                exception = match.group(1).strip()
                if len(exception) > 5:
                    exceptions.append(exception)

        return list(set(exceptions))

    def _extract_legal_concepts(self, text: str) -> List[str]:
        """Extract legal concepts from text."""
        concepts = []
        text_lower = text.lower()

        if hasattr(self.legal_ontology, 'legal_synonyms'):
            for category, terms in self.legal_ontology.legal_synonyms.items():
                for term in terms:
                    if term.lower() in text_lower:
                        concepts.append(term)

        return list(set(concepts))

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords for indexing."""
        keywords = []
        legal_keywords = [
            'право', 'обязанность', 'ответственность', 'наказание',
            'процедура', 'требование', 'условие', 'срок',
            'документ', 'заявление', 'решение', 'определение'
        ]

        text_lower = text.lower()
        for keyword in legal_keywords:
            if keyword in text_lower:
                keywords.append(keyword)

        return keywords


__all__ = ["RuleParser"]
