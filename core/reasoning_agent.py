#!/usr/bin/env python3
"""
Reasoning Agent для юридических запросов
Использует Gemini 2.5 Flash с thinking mode для анализа запросов

Функциональность:
- Анализ типа вопроса (определение/процедура/условие/последствия)
- Извлечение ключевых терминов
- Определение стратегии поиска
- Приоритизация источников (локальная база / граф / веб)
"""

import logging
import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.api_key_manager import get_key_manager
from core.gemini_rate_limiter import GeminiRateLimiter

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Типы юридических запросов"""
    DEFINITION = "definition" # "Что такое X?"
    PROCEDURE = "procedure" # "Как происходит X?"
    CONDITION = "condition" # "При каких условиях X?"
    CONSEQUENCE = "consequence" # "Какие последствия X?"
    REQUIREMENT = "requirement" # "Какие требования к X?"
    RIGHT = "right" # "Кто имеет право на X?"
    OBLIGATION = "obligation" # "Какие обязанности X?"
    COMPARISON = "comparison" # "В чем разница между X и Y?"
    GENERAL = "general" # Общий вопрос


class SearchStrategy(Enum):
    """Стратегии поиска"""
    DEFINITION_FIRST = "definition_first" # Сначала ищем в узлах Definition
    ARTICLE_RANGE = "article_range" # Поиск в диапазоне статей
    GRAPH_TRAVERSAL = "graph_traversal" # Обход графа связей
    FULL_TEXT = "full_text" # Полнотекстовый поиск
    WEB_FALLBACK = "web_fallback" # Поиск в интернете


@dataclass
class QueryAnalysis:
    """Результат анализа запроса"""
    query_type: QueryType
    key_terms: List[str]
    search_strategy: SearchStrategy
    article_range: Optional[tuple] = None # (min, max) номера статей
    laws: List[str] = None # Упоминаемые законы (формат "XXX-ФЗ" и т.п.)
    need_graph: bool = False # Нужен ли графовый поиск
    need_web: bool = False # Нужен ли веб-поиск
    confidence: float = 0.0 # Уверенность в анализе
    reasoning: str = "" # Объяснение от модели


class ReasoningAgent:
    """
    Агент с reasoning mode для анализа юридических запросов
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash-preview-09-2025",
        temperature: float = 0.1
    ):
        from core.api_key_manager import get_key_manager
        key_manager = get_key_manager()
        self.api_key = api_key or key_manager.get_next_key()
        if not self.api_key:
            raise ValueError("No Gemini API key available")

        # Инициализация LLM с thinking mode
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=self.api_key,
            temperature=temperature,
            # CRITICAL: Включаем thinking mode для reasoning
            model_kwargs={
                "thinking": True # Gemini 2.5 Flash поддерживает thinking
            }
        )

        logger.info(f" Reasoning Agent initialized with {model_name} (thinking mode: ON)")

    async def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Анализирует запрос и определяет стратегию поиска

        Args:
            query: Пользовательский запрос

        Returns:
            QueryAnalysis с типом запроса и стратегией поиска
        """
        system_prompt = """
Ты - эксперт по российскому законодательству и информационному поиску.

Твоя задача: проанализировать юридический запрос и определить оптимальную стратегию поиска.

## Типы запросов:
1. **definition** - "Что такое X?", "Определение X", "Понятие X"
2. **procedure** - "Как происходит X?", "Порядок X", "Процедура X"
3. **condition** - "При каких условиях X?", "Когда X?", "Если X, то Y?"
4. **consequence** - "Какие последствия X?", "Что будет если X?"
5. **requirement** - "Какие требования к X?", "Что нужно для X?"
6. **right** - "Кто имеет право на X?", "Может ли X?"
7. **obligation** - "Кто обязан X?", "Должен ли X?"
8. **comparison** - "В чем разница X и Y?", "Чем отличается X от Y?"
9. **general** - Общий вопрос, не подходящий под категории выше

## Стратегии поиска:
1. **definition_first** - Для вопросов на определение. Сначала искать в узлах Definition (Neo4j), потом в статьях 1-20.
2. **article_range** - Для вопросов, где известен примерный диапазон статей.
3. **graph_traversal** - Для сложных вопросов, требующих контекста из нескольких связанных статей.
4. **full_text** - Для общих вопросов, полнотекстовый поиск.
5. **web_fallback** - Если вопрос специфичный и может отсутствовать в локальной базе.

## Важные паттерны:
- Определения обычно находятся в статьях 1-20
- Процедуры и условия - в средних статьях (20-60)
- Последствия и санкции - в конечных статьях (60+)

Верни результат в JSON формате:
{
  "query_type": "definition",
  "key_terms": ["плата концедента"],
  "search_strategy": "definition_first",
  "article_range": [1, 20],
  "laws": ["115-ФЗ"],
  "need_graph": false,
  "need_web": false,
  "confidence": 0.95,
  "reasoning": "Вопрос на определение термина. Термин 'плата концедента' относится к концессионным соглашениям (115-ФЗ). Определения обычно в начале закона."
}
"""

        user_prompt = f"""
Проанализируй следующий юридический запрос:

"{query}"

Определи:
1. Тип запроса (definition/procedure/condition/etc)
2. Ключевые термины для поиска
3. Оптимальную стратегию поиска
4. Диапазон статей (если применимо)
5. Упоминаемые законы (например: "123-ФЗ", "ГК РФ")
6. Нужен ли графовый поиск связанных статей?
7. Нужен ли веб-поиск как fallback?
8. Уверенность в анализе (0.0 - 1.0)
9. Объяснение твоего рассуждения

Верни только JSON, без дополнительного текста.
"""

        try:
            # Ротация ключа перед каждым запросом (пер-ревест)
            key_manager = get_key_manager()
            rotated_key = key_manager.get_next_key()
            self.llm = ChatGoogleGenerativeAI(
                model=self.llm.model,
                google_api_key=rotated_key,
                temperature=self.llm.temperature,
                model_kwargs={"thinking": True}
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            # Rate limiting для flash модели
            await GeminiRateLimiter.wait("flash")

            # Вызов с thinking mode - модель сначала думает, потом отвечает
            response = await self.llm.ainvoke(messages)
            response_text = response.content

            # Парсинг JSON из ответа
            # Модель может вернуть ```json ... ``` - нужно извлечь
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()

            result = json.loads(json_text)

            # Преобразование в QueryAnalysis
            analysis = QueryAnalysis(
                query_type=QueryType(result.get("query_type", "general")),
                key_terms=result.get("key_terms", []),
                search_strategy=SearchStrategy(result.get("search_strategy", "full_text")),
                article_range=tuple(result["article_range"]) if result.get("article_range") else None,
                laws=result.get("laws", []),
                need_graph=result.get("need_graph", False),
                need_web=result.get("need_web", False),
                confidence=result.get("confidence", 0.0),
                reasoning=result.get("reasoning", "")
            )

            logger.info(f" Query analyzed: type={analysis.query_type.value}, strategy={analysis.search_strategy.value}")
            logger.debug(f"Reasoning: {analysis.reasoning}")

            return analysis

        except Exception as e:
            logger.error(f" Error analyzing query: {e}")
            # Fallback: простой анализ без LLM
            return self._fallback_analysis(query)

    def _fallback_analysis(self, query: str) -> QueryAnalysis:
        """Простой анализ без LLM (fallback)"""
        query_lower = query.lower()

        # Определение типа по ключевым словам
        if any(word in query_lower for word in ["что такое", "определение", "понятие", "является ли"]):
            query_type = QueryType.DEFINITION
            strategy = SearchStrategy.DEFINITION_FIRST
            article_range = (1, 20)
        elif any(word in query_lower for word in ["как происходит", "порядок", "процедура"]):
            query_type = QueryType.PROCEDURE
            strategy = SearchStrategy.ARTICLE_RANGE
            article_range = (20, 60)
        elif any(word in query_lower for word in ["условия", "при каких", "когда"]):
            query_type = QueryType.CONDITION
            strategy = SearchStrategy.FULL_TEXT
            article_range = None
        else:
            query_type = QueryType.GENERAL
            strategy = SearchStrategy.FULL_TEXT
            article_range = None

        # Извлечение законов (формат "123-ФЗ", "ГК РФ" и т.п.)
        laws = []
        import re
        for match in re.findall(r"\d{1,3}\s*-\s*фз", query_lower):
            laws.append(match.replace(" ", "").upper())
        code_match = re.findall(r"\b([а-яё]+\s+кодекс\s+российской\s+федерации)\b", query_lower)
        laws.extend([m.strip().title() for m in code_match])

        return QueryAnalysis(
            query_type=query_type,
            key_terms=[], # Не извлекаем без LLM
            search_strategy=strategy,
            article_range=article_range,
            laws=laws,
            need_graph=False,
            need_web=False,
            confidence=0.5, # Низкая уверенность для fallback
            reasoning="Fallback analysis without LLM"
        )
