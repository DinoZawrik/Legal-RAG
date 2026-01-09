"""Типы и структуры данных для продвинутых промптов."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class QueryType(Enum):
    """Типы запросов для адаптивных промптов."""

    CASUAL_CHAT = "casual_chat"
    SIMPLE_DEFINITION = "simple_definition"
    COMPLEX_PROCEDURE = "complex_procedure"
    COMPARISON = "comparison"
    LEGAL_ANALYSIS = "legal_analysis"
    REGULATORY_SPECIFIC = "regulatory_specific"
    CALCULATION = "calculation"
    LEGAL_CONSULTATION = "legal_consultation"
    DOCUMENT_SEARCH = "document_search"
    LEGAL_INTERPRETATION = "legal_interpretation"
    PROCEDURE_INQUIRY = "procedure_inquiry"
    DEFINITION_REQUEST = "definition_request"
    COMPLEX_ANALYSIS = "complex_analysis"


class ModelType(Enum):
    """Типы AI моделей для оптимизации промптов."""

    GEMINI = "gemini"
    GPT = "gpt"
    CLAUDE = "claude"
    LOCAL = "local"


@dataclass
class PromptTemplate:
    """Шаблон промпта с метаданными."""

    name: str
    query_type: QueryType
    model_type: ModelType
    system_prompt: str
    user_prompt_template: str
    description: str
    performance_score: float = 0.0
    usage_count: int = 0


@dataclass
class PromptContext:
    """Контекст для адаптации промпта."""

    query: str
    query_type: QueryType
    chunks_count: int
    has_exact_match: bool
    document_types: List[str]
    confidence_level: float


__all__ = [
    "ModelType",
    "PromptContext",
    "PromptTemplate",
    "QueryType",
]
