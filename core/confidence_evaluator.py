#!/usr/bin/env python3
"""
Confidence Evaluator для RAG системы
Оценивает качество найденных результатов перед генерацией ответа

Ключевая идея:
- Не просто проверяем НАЛИЧИЕ результатов
- Проверяем КАЧЕСТВО - содержат ли они ответ на вопрос
- Если качество низкое агент ищет в других источниках
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os

from langchain_google_genai import ChatGoogleGenerativeAI

from core.api_key_manager import get_key_manager
from core.gemini_rate_limiter import GeminiRateLimiter

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceResult:
    """Результат оценки уверенности"""
    confidence: float # 0.0 - 1.0
    reasoning: str # Объяснение оценки
    missing_info: Optional[str] = None # Что не хватает для полного ответа
    answer_found: bool = False # Найден ли прямой ответ


class ConfidenceEvaluator:
    """
    Оценщик качества результатов поиска

    Использует LLM (Gemini 2.5 Flash) для критической оценки:
    - Содержат ли результаты прямой ответ на вопрос?
    - Есть ли определение термина (для definition queries)?
    - Достаточно ли информации для полного ответа?
    """

    def __init__(self, api_key: Optional[str] = None):
        from core.api_key_manager import get_key_manager
        key_manager = get_key_manager()
        self.api_key = api_key or key_manager.get_next_key()

        # LLM для оценки (Gemini 3.1 Flash Lite — быстрая лёгкая модель)
        # Для критической оценки не нужна сложная модель
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite-preview",
            google_api_key=self.api_key,
            temperature=0.1 # Низкая температура для консистентности
        )

        logger.info(" Confidence Evaluator initialized (using Gemini 3.1 Flash Lite)")

    async def evaluate_definition_quality(
        self,
        term: str,
        results: List[Dict],
        max_results: int = 10
    ) -> ConfidenceResult:
        """
        Оценка качества для вопросов на определение

        Args:
            term: Термин, определение которого ищем
            results: Список найденных результатов
            max_results: Сколько результатов анализировать

        Returns:
            ConfidenceResult с оценкой
        """
        if not results:
            return ConfidenceResult(
                confidence=0.0,
                reasoning="Результаты поиска пусты",
                missing_info=f"Определение термина '{term}'",
                answer_found=False
            )

        # Берем топ-N результатов
        top_results = results[:max_results]

        # Формируем текст для анализа
        results_text = []
        for i, r in enumerate(top_results, 1):
            law = r.get('metadata', {}).get('law_number', r.get('law', 'N/A'))
            article = r.get('metadata', {}).get('article_number', r.get('article', 'N/A'))
            text = r.get('text', r.get('definition', ''))[:500] # Первые 500 символов

            results_text.append(f"[{i}] Закон: {law}, Статья: {article}")
            results_text.append(f"Текст: {text}\n")

        prompt = f"""Ты - критический эксперт по российскому законодательству.

Задача: СТРОГО оценить, содержат ли эти фрагменты ТОЧНОЕ ОПРЕДЕЛЕНИЕ термина "{term}".

Найденные фрагменты:
{chr(10).join(results_text)}

Критерии оценки:
1.0 (ОТЛИЧНО) - Есть прямое определение:
   - "под {term} понимается..."
   - "{term} является..."
   - "...{term} (далее - ...)..."
   - Четкое объяснение что такое {term}

0.7 (ХОРОШО) - Есть косвенное объяснение:
   - Описание использования термина
   - Контекст, из которого понятно значение

0.3 (ПЛОХО) - Только упоминания термина:
   - Термин встречается, но без объяснения
   - Описание связанных процедур, но не самого термина

0.0 (НЕТ ОТВЕТА) - Определения нет вообще

Ответ в формате JSON:
{{
  "confidence": 0.0-1.0,
  "answer_found": true/false,
  "reasoning": "краткое объяснение оценки",
  "missing_info": "что не хватает (если confidence < 0.7)"
}}

Только JSON, без дополнительного текста:"""

        try:
            # Ротация ключа перед вызовом (пер-запрос)
            key_manager = get_key_manager()
            rotated_key = key_manager.get_next_key()
            self.llm = ChatGoogleGenerativeAI(
                model=self.llm.model,
                google_api_key=rotated_key,
                temperature=self.llm.temperature
            )

            await GeminiRateLimiter.wait("flash-lite")
            response = await self.llm.ainvoke(prompt)
            result_text = response.content.strip()

            # Извлекаем JSON
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            elif "```" in result_text:
                json_start = result_text.find("```") + 3
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()

            import json
            result = json.loads(result_text)

            confidence_result = ConfidenceResult(
                confidence=float(result.get('confidence', 0.0)),
                reasoning=result.get('reasoning', ''),
                missing_info=result.get('missing_info'),
                answer_found=result.get('answer_found', False)
            )

            logger.info(f" Definition quality: confidence={confidence_result.confidence:.2f}, found={confidence_result.answer_found}")

            return confidence_result

        except Exception as e:
            logger.error(f" Error evaluating definition quality: {e}")
            # Fallback: простая эвристика
            return self._fallback_definition_check(term, results)

    async def evaluate_answer_completeness(
        self,
        query: str,
        results: List[Dict],
        max_results: int = 10
    ) -> ConfidenceResult:
        """
        Оценка полноты ответа для общих вопросов

        Args:
            query: Вопрос пользователя
            results: Найденные результаты
            max_results: Сколько результатов анализировать

        Returns:
            ConfidenceResult
        """
        if not results:
            return ConfidenceResult(
                confidence=0.0,
                reasoning="Результаты поиска пусты",
                missing_info="Релевантная информация для ответа",
                answer_found=False
            )

        top_results = results[:max_results]

        results_text = []
        for i, r in enumerate(top_results, 1):
            law = r.get('metadata', {}).get('law_number', r.get('law', 'N/A'))
            article = r.get('metadata', {}).get('article_number', r.get('article', 'N/A'))
            text = r.get('text', r.get('definition', ''))[:400]

            results_text.append(f"[{i}] {law} ст.{article}: {text}")

        prompt = f"""Ты - критический эксперт по российскому законодательству.

Вопрос пользователя: "{query}"

Найденные фрагменты:
{chr(10).join(results_text)}

Задача: СТРОГО оценить, достаточно ли этих фрагментов для ПОЛНОГО ответа на вопрос.

Критерии:
1.0 - Полный прямой ответ найден
0.7 - Частичный ответ, но не хватает деталей
0.3 - Только косвенная информация
0.0 - Нет релевантной информации

JSON ответ:
{{
  "confidence": 0.0-1.0,
  "answer_found": true/false,
  "reasoning": "объяснение",
  "missing_info": "что не хватает (если < 0.7)"
}}"""

        try:
            # Ротация ключа перед вызовом (пер-запрос)
            try:
                key_manager = get_key_manager()
                rotated_key = key_manager.get_next_key()
                self.llm = ChatGoogleGenerativeAI(
                    model=self.llm.model,
                    google_api_key=rotated_key,
                    temperature=self.llm.temperature
                )
            except Exception:
                pass

            await GeminiRateLimiter.wait("flash-lite")
            response = await self.llm.ainvoke(prompt)
            result_text = response.content.strip()

            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()

            import json
            result = json.loads(result_text)

            return ConfidenceResult(
                confidence=float(result.get('confidence', 0.0)),
                reasoning=result.get('reasoning', ''),
                missing_info=result.get('missing_info'),
                answer_found=result.get('answer_found', False)
            )

        except Exception as e:
            logger.error(f" Error evaluating answer completeness: {e}")
            return ConfidenceResult(
                confidence=0.5, # Средняя уверенность при ошибке
                reasoning="Ошибка оценки, используем найденные результаты",
                answer_found=len(results) >= 3
            )

    def _fallback_definition_check(self, term: str, results: List[Dict]) -> ConfidenceResult:
        """
        Простая эвристическая проверка (fallback при ошибке LLM)
        """
        term_lower = term.lower()

        # Проверяем наличие паттернов определений
        definition_patterns = [
            "понимается",
            "является",
            "далее -",
            "далее —",
            "определение",
            "означает"
        ]

        has_definition = False
        for result in results[:5]:
            text = result.get('text', result.get('definition', '')).lower()
            if term_lower in text:
                if any(pattern in text for pattern in definition_patterns):
                    has_definition = True
                    break

        if has_definition:
            return ConfidenceResult(
                confidence=0.7,
                reasoning="Найден паттерн определения (эвристическая проверка)",
                answer_found=True
            )
        else:
            return ConfidenceResult(
                confidence=0.2,
                reasoning="Термин упоминается, но паттерны определения не найдены",
                missing_info=f"Точное определение '{term}'",
                answer_found=False
            )
