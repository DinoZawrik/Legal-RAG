"""Compatibility wrapper for advanced prompt engine."""

from core.prompts.advanced import (
    AdvancedPromptEngine,
    ModelType,
    PromptContext,
    PromptTemplate,
    QueryType,
    get_prompt_engine,
)

__all__ = [
    "AdvancedPromptEngine",
    "ModelType",
    "PromptContext",
    "PromptTemplate",
    "QueryType",
    "get_prompt_engine",
]
