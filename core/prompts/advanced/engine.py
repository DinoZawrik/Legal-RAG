"""Основной класс AdvancedPromptEngine с делегированием помощникам."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .adaptation import adapt_system_prompt, adapt_user_prompt
from .detection import detect_query_type
from .metrics import collect_stats, optimize_prompts, record_performance
from .templates import initialize_templates
from .types import ModelType, PromptContext, PromptTemplate, QueryType

logger = logging.getLogger(__name__)


class AdvancedPromptEngine:
    """Продвинутая система управления промптами."""

    def __init__(self, model_type: ModelType = ModelType.GEMINI):
        self.model_type = model_type
        self.prompt_templates: Dict[str, PromptTemplate] = initialize_templates(model_type)
        self.performance_history: List[Dict[str, Any]] = []
        self.adaptation_config = {
            "enable_context_adaptation": True,
            "enable_performance_learning": True,
            "min_chunks_for_detailed": 3,
            "max_chunks_for_summary": 10,
        }

    def detect_query_type(self, query: str) -> QueryType:
        return detect_query_type(query)

    def generate_adaptive_prompt(
        self, query: str, chunks: List[str], context: Optional[PromptContext] = None
    ) -> Tuple[str, str]:
        query_type = context.query_type if context and context.query_type else self.detect_query_type(query)
        logger.info("🎯 Определен тип запроса: %s", query_type.value)

        template = self.prompt_templates.get(query_type.value) or self.prompt_templates["casual_chat"]
        system_prompt = adapt_system_prompt(template.system_prompt, chunks, context, self.adaptation_config)
        user_prompt = adapt_user_prompt(template.user_prompt_template, query, chunks, context)
        template.usage_count += 1
        return system_prompt, user_prompt

    def record_performance(
        self, query_type: QueryType, prompt_name: str, success: bool, response_quality: float = 0.0
    ) -> None:
        if not self.adaptation_config.get("enable_performance_learning", True):
            return
        record_performance(
            self.performance_history,
            self.prompt_templates,
            query_type,
            prompt_name,
            success,
            response_quality,
        )

    def get_best_prompt_for_query_type(self, query_type: QueryType) -> Optional[PromptTemplate]:
        matching = [template for template in self.prompt_templates.values() if template.query_type == query_type]
        if not matching:
            return None
        return max(matching, key=lambda t: t.performance_score)

    def optimize_prompts(self) -> Dict[str, Any]:
        report = optimize_prompts(self.performance_history, self.prompt_templates)
        logger.info("📊 Анализ промптов завершен: %d рекомендаций", len(report["optimizations"]))
        return report

    def get_prompt_stats(self) -> Dict[str, Any]:
        return collect_stats(self.prompt_templates)


_prompt_engine: Optional[AdvancedPromptEngine] = None


def get_prompt_engine(model_type: ModelType = ModelType.GEMINI) -> AdvancedPromptEngine:
    global _prompt_engine
    if _prompt_engine is None:
        _prompt_engine = AdvancedPromptEngine(model_type)
    return _prompt_engine


__all__ = ["AdvancedPromptEngine", "get_prompt_engine"]
