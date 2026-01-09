"""Key term extraction helpers for legal chunking."""

import re
from typing import Iterable, List, Set


def extract_key_terms(text: str, ontology, numerical_patterns: Iterable[str]) -> List[str]:
    """Return unique legal key terms detected in the provided text."""

    text_lower = text.lower()
    key_terms: Set[str] = set()

    synonyms = getattr(ontology, "LEGAL_SYNONYMS", {})
    for term in synonyms.keys():
        if term in text_lower:
            key_terms.add(term)

    abbreviations = getattr(ontology, "ABBREVIATIONS", {})
    for abbr in abbreviations.keys():
        if abbr in text_lower:
            key_terms.add(abbr)

    for pattern in numerical_patterns:
        for match in re.findall(pattern, text_lower, re.IGNORECASE):
            cleaned = match.strip()
            if cleaned:
                key_terms.add(cleaned)

    return list(key_terms)
