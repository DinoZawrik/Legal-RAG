#!/usr/bin/env python3
"""
Prompt Sanitizer for Legal-RAG

Sanitizes user input before interpolation into LLM prompts to mitigate
prompt injection attacks.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum allowed input length for prompts
MAX_QUERY_LENGTH = 5000
MAX_CONTEXT_LENGTH = 50000

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?previous\s+(instructions?|context)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(system|hidden|secret)", re.IGNORECASE),
    re.compile(r"override\s+(system|instructions?|safety)", re.IGNORECASE),
    re.compile(r"disregard\s+(all|any|the)\s+(above|previous|prior)", re.IGNORECASE),
    re.compile(r"new\s+instructions?:\s*", re.IGNORECASE),
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
    re.compile(r"\[\s*SYSTEM\s*\]", re.IGNORECASE),
]


def sanitize_prompt_input(
    text: str,
    max_length: int = MAX_QUERY_LENGTH,
    field_name: str = "input",
) -> str:
    """
    Sanitize user-provided text before inserting into a prompt template.

    - Truncates to *max_length* characters.
    - Strips control characters.
    - Detects and neutralises known injection patterns.
    """
    if not text:
        return ""

    # Truncate
    if len(text) > max_length:
        logger.warning(
            "Prompt %s truncated from %d to %d chars",
            field_name, len(text), max_length,
        )
        text = text[:max_length]

    # Strip ASCII control characters (keep newlines and tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Detect injection patterns — log and neutralise
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning(
                "Potential prompt injection detected in %s: matched %s",
                field_name, pattern.pattern,
            )
            text = pattern.sub("[FILTERED]", text)

    return text


def sanitize_query(query: str) -> str:
    """Convenience wrapper for user queries."""
    return sanitize_prompt_input(query, max_length=MAX_QUERY_LENGTH, field_name="query")


def sanitize_context(context: str) -> str:
    """Convenience wrapper for context blocks."""
    return sanitize_prompt_input(context, max_length=MAX_CONTEXT_LENGTH, field_name="context")
