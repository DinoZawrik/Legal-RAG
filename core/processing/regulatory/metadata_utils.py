"""Metadata helpers for regulatory document detection."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


def is_legal_document(text: str, metadata: Dict[str, Any] | None = None) -> bool:
    if not text:
        return False

    if metadata:
        doc_type = metadata.get("document_type", "").lower()
        if "legal" in doc_type or "regulatory" in doc_type:
            return True

        filename = metadata.get("filename", "").lower()
        if any(keyword in filename for keyword in ["фз", "закон", "кодекс", "постановление"]):
            return True

    legal_indicators = [
        "федеральный закон",
        "статья",
        "часть",
        "пункт",
        "подпункт",
        "кодекс",
        "постановление",
        "приказ",
        "положение",
        "правительство российской федерации",
        "российская федерация",
        "-фз",
        "вступает в силу",
        "настоящий закон",
        "настоящий кодекс",
    ]

    text_lower = text.lower()
    found_indicators = sum(1 for indicator in legal_indicators if indicator in text_lower)
    return found_indicators >= 3


def extract_law_number(text: str, metadata: Dict[str, Any] | None = None) -> Optional[str]:
    if metadata:
        doc_number = metadata.get("document_number")
        if doc_number and "-фз" in doc_number.lower():
            return doc_number

        filename = metadata.get("filename", "")
        if filename:
            match = re.search(r"(\d+)-фз", filename.lower())
            if match:
                return f"{match.group(1)}-ФЗ"

    if text:
        patterns = [
            r"федеральный закон.*?№\s*(\d+)-фз",
            r"фз.*?№\s*(\d+)-фз",
            r"№\s*(\d+)-фз",
            r"(\d+)-фз",
        ]

        text_lower = text.lower()
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return f"{match.group(1)}-ФЗ"

    return None


__all__ = ["is_legal_document", "extract_law_number"]
