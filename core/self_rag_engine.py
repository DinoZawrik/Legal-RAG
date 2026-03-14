#!/usr/bin/env python3
"""
Self-RAG Engine для юридических систем
КРИТИЧЕСКОЕ УЛУЧШЕНИЕ: Автоматическая верификация и улучшение качества ответов
"""

import asyncio
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import re

from core.russian_legal_prompts import RussianLegalPrompts


class CritiqueDecision(Enum):
    """Решения критики Self-RAG"""
    RETRIEVE_MORE = "RETRIEVE_MORE" # Нужны дополнительные документы
    SUFFICIENT = "SUFFICIENT" # Достаточно документов
    RELEVANT = "RELEVANT" # Документ релевантен
    IRRELEVANT = "IRRELEVANT" # Документ не релевантен
    SUPPORTED = "SUPPORTED" # Утверждение поддержано
    NOT_SUPPORTED = "NOT_SUPPORTED" # Утверждение не поддержано
    USEFUL = "USEFUL" # Ответ полезен
    NOT_USEFUL = "NOT_USEFUL" # Ответ не полезен


@dataclass
class CritiqueResult:
    """Результат критики"""
    decision: CritiqueDecision
    confidence: float
    reasoning: str
    evidence: Optional[str] = None


@dataclass
class SelfRAGResult:
    """Результат Self-RAG генерации"""
    answer: str
    confidence_score: float
    critique_results: Dict[str, CritiqueResult]
    used_documents: List[str]
    verification_details: Dict[str, any]


class SelfRAGInferenceEngine:
    """
    Self-RAG движок для юридических систем
    Реализует автоматическую критику и верификацию ответов
    """

    def __init__(self, inference_service, storage_manager):
        self.inference_service = inference_service
        self.storage_manager = storage_manager
        self.legal_prompts = RussianLegalPrompts()

        # Пороги для принятия решений
        self.thresholds = {
            'retrieve_more': 0.6, # Порог для дополнительного поиска
            'relevance': 0.7, # Порог релевантности документа
            'support': 0.75, # Порог поддержки утверждения
            'usefulness': 0.8 # Порог полезности ответа
        }

    async def generate_with_self_critique(self, query: str, initial_docs: List[str]) -> SelfRAGResult:
        """
        Основной метод Self-RAG генерации с критикой
        """
        critique_results = {}

        # 1. Критика необходимости дополнительного поиска
        retrieve_critique = await self._critique_retrieve(query, initial_docs)
        critique_results['retrieve'] = retrieve_critique

        # 2. Расширение поиска если необходимо
        working_docs = initial_docs.copy()
        if retrieve_critique.decision == CritiqueDecision.RETRIEVE_MORE:
            additional_docs = await self._expand_search(query, retrieve_critique.reasoning)
            working_docs.extend(additional_docs)

        # 3. Критика релевантности каждого документа
        relevant_docs = []
        for i, doc in enumerate(working_docs):
            relevance_critique = await self._critique_relevance(query, doc)
            critique_results[f'relevance_{i}'] = relevance_critique

            if relevance_critique.decision == CritiqueDecision.RELEVANT:
                relevant_docs.append(doc)

        # 4. Генерация ответа на основе релевантных документов
        if not relevant_docs:
            return SelfRAGResult(
                answer="КРИТИЧЕСКАЯ ОШИБКА: Не найдено релевантных документов для ответа на запрос.",
                confidence_score=0.0,
                critique_results=critique_results,
                used_documents=[],
                verification_details={'error': 'no_relevant_documents'}
            )

        answer = await self._generate_legal_answer(query, relevant_docs)

        # 5. Критика поддержки ответа документами
        support_critique = await self._critique_support(answer, relevant_docs)
        critique_results['support'] = support_critique

        # 6. Если поддержка недостаточная - генерация осторожного ответа
        if support_critique.decision == CritiqueDecision.NOT_SUPPORTED:
            answer = await self._generate_cautious_answer(query, relevant_docs, support_critique.reasoning)

        # 7. Финальная критика полезности ответа
        usefulness_critique = await self._critique_usefulness(query, answer)
        critique_results['usefulness'] = usefulness_critique

        # 8. Расчет общего confidence score
        confidence_score = self._calculate_overall_confidence(critique_results)

        # 9. Детальная верификация
        verification_details = await self._detailed_verification(answer, relevant_docs)

        return SelfRAGResult(
            answer=answer,
            confidence_score=confidence_score,
            critique_results=critique_results,
            used_documents=relevant_docs,
            verification_details=verification_details
        )

    async def _critique_retrieve(self, query: str, current_docs: List[str]) -> CritiqueResult:
        """Критика: нужны ли дополнительные документы?"""

        # Анализ покрытия запроса текущими документами
        coverage_prompt = f"""
Проанализируй, достаточно ли предоставленных документов для полного ответа на правовой запрос.

ЗАПРОС: {query}

КОЛИЧЕСТВО ДОКУМЕНТОВ: {len(current_docs)}
СОДЕРЖАНИЕ ДОКУМЕНТОВ: {' '.join([doc[:200] + '...' for doc in current_docs[:3]])}

КРИТЕРИИ ДОСТАТОЧНОСТИ:
1. Есть ли прямые ссылки на применимые законы?
2. Покрывают ли документы все аспекты запроса?
3. Достаточно ли контекста для правового анализа?

ОТВЕТ должен быть ТОЛЬКО одним из: ДОСТАТОЧНО / НУЖНО_БОЛЬШЕ
Если НУЖНО_БОЛЬШЕ - укажи, какие именно аспекты не покрыты.
"""

        # ИСПРАВЛЕНИЕ: Правильный вызов через inference_system
        response_data = await self.inference_service.inference_system.generate_response(
            prompt=coverage_prompt,
            temperature=0.1,
            max_tokens=500
        )
        response = response_data.get('response', str(response_data)) if isinstance(response_data, dict) else str(response_data)

        if "НУЖНО_БОЛЬШЕ" in response:
            decision = CritiqueDecision.RETRIEVE_MORE
            reasoning = self._extract_reasoning(response)
            confidence = 0.8
        else:
            decision = CritiqueDecision.SUFFICIENT
            reasoning = "Текущие документы покрывают запрос"
            confidence = 0.9

        return CritiqueResult(decision, confidence, reasoning)

    async def _critique_relevance(self, query: str, document: str) -> CritiqueResult:
        """Критика: релевантен ли документ запросу?"""

        relevance_prompt = f"""
Оцени релевантность документа для правового запроса по шкале 0-10.

ЗАПРОС: {query}
ДОКУМЕНТ: {document[:1000]}...

КРИТЕРИИ РЕЛЕВАНТНОСТИ:
1. Содержит ли документ применимые правовые нормы?
2. Относится ли к той же области права?
3. Помогает ли ответить на конкретный вопрос?

ОТВЕТ: РЕЛЕВАНТНОСТЬ: [0-10] - [обоснование]
Если оценка 7 - документ РЕЛЕВАНТЕН, иначе НЕ_РЕЛЕВАНТЕН.
"""

        # ИСПРАВЛЕНИЕ: Правильный вызов через inference_system
        response_data = await self.inference_service.inference_system.generate_response(
            prompt=relevance_prompt,
            temperature=0.1,
            max_tokens=500
        )
        response = response_data.get('response', str(response_data)) if isinstance(response_data, dict) else str(response_data)

        # Извлечение оценки
        score_match = re.search(r'(\d+)', response)
        score = int(score_match.group(1)) if score_match else 0

        if score >= 7:
            decision = CritiqueDecision.RELEVANT
            confidence = min(score / 10, 1.0)
        else:
            decision = CritiqueDecision.IRRELEVANT
            confidence = (10 - score) / 10

        reasoning = self._extract_reasoning(response)
        return CritiqueResult(decision, confidence, reasoning, evidence=f"Оценка: {score}/10")

    async def _critique_support(self, answer: str, documents: List[str]) -> CritiqueResult:
        """Критика: поддерживают ли документы ответ?"""

        docs_context = "\n\n".join([f"ДОК {i+1}: {doc[:500]}" for i, doc in enumerate(documents)])

        support_prompt = f"""
Проверь, поддерживают ли предоставленные документы каждое утверждение в ответе.

ОТВЕТ ДЛЯ ПРОВЕРКИ:
{answer}

ИСТОЧНИКИ:
{docs_context}

ДЛЯ КАЖДОГО ФАКТ-УТВЕРЖДЕНИЯ в ответе укажи:
1. Есть ли прямое подтверждение в документах?
2. Правильно ли указаны ссылки на законы/статьи?
3. Нет ли противоречий с источниками?

ИТОГОВАЯ ОЦЕНКА: ПОДДЕРЖАНО / НЕ_ПОДДЕРЖАНО / ЧАСТИЧНО_ПОДДЕРЖАНО
"""

        # ИСПРАВЛЕНИЕ: Правильный вызов через inference_system
        response_data = await self.inference_service.inference_system.generate_response(
            prompt=support_prompt,
            temperature=0.1,
            max_tokens=1000
        )
        response = response_data.get('response', str(response_data)) if isinstance(response_data, dict) else str(response_data)

        if "НЕ_ПОДДЕРЖАНО" in response:
            decision = CritiqueDecision.NOT_SUPPORTED
            confidence = 0.9
        elif "ЧАСТИЧНО" in response:
            decision = CritiqueDecision.NOT_SUPPORTED
            confidence = 0.6
        else:
            decision = CritiqueDecision.SUPPORTED
            confidence = 0.8

        reasoning = self._extract_reasoning(response)
        return CritiqueResult(decision, confidence, reasoning)

    async def _critique_usefulness(self, query: str, answer: str) -> CritiqueResult:
        """Критика: полезен ли ответ для пользователя?"""

        usefulness_prompt = f"""
Оцени полезность ответа для пользователя по следующим критериям:

ЗАПРОС: {query}
ОТВЕТ: {answer}

КРИТЕРИИ ПОЛЕЗНОСТИ:
1. Отвечает ли на поставленный вопрос?
2. Предоставляет ли конкретную правовую информацию?
3. Структурирован ли ответ логично?
4. Указаны ли точные ссылки на источники?
5. Можно ли использовать ответ на практике?

ОЦЕНКА: [0-10] - ПОЛЕЗЕН / НЕ_ПОЛЕЗЕН
"""

        # ИСПРАВЛЕНИЕ: Правильный вызов через inference_system
        response_data = await self.inference_service.inference_system.generate_response(
            prompt=usefulness_prompt,
            temperature=0.1,
            max_tokens=500
        )
        response = response_data.get('response', str(response_data)) if isinstance(response_data, dict) else str(response_data)

        score_match = re.search(r'(\d+)', response)
        score = int(score_match.group(1)) if score_match else 0

        if score >= 8:
            decision = CritiqueDecision.USEFUL
            confidence = score / 10
        else:
            decision = CritiqueDecision.NOT_USEFUL
            confidence = (10 - score) / 10

        reasoning = self._extract_reasoning(response)
        return CritiqueResult(decision, confidence, reasoning, evidence=f"Оценка: {score}/10")

    async def _generate_legal_answer(self, query: str, documents: List[str]) -> str:
        """Генерация правового ответа с IRAC структурой"""

        irac_prompt = self.legal_prompts.format_legal_query(query, documents)
        system_prompt = self.legal_prompts.get_irac_system_prompt()

        # Используем систему промптов для структурированного ответа
        full_prompt = f"{system_prompt}\n\n{irac_prompt}"

        # ИСПРАВЛЕНИЕ: Правильный вызов через inference_system
        response_data = await self.inference_service.inference_system.generate_response(
            prompt=full_prompt,
            temperature=0.05,
            max_tokens=2048
        )
        return response_data.get('response', str(response_data)) if isinstance(response_data, dict) else str(response_data)

    async def _generate_cautious_answer(self, query: str, documents: List[str], support_issues: str) -> str:
        """Генерация осторожного ответа при недостаточной поддержке"""

        cautious_prompt = f"""
ВНИМАНИЕ: Обнаружены проблемы с поддержкой ответа источниками.
ПРОБЛЕМЫ: {support_issues}

Дай осторожный ответ на запрос: {query}

ТРЕБОВАНИЯ:
1. Укажи только то, что ПРЯМО подтверждено источниками
2. Четко обозначь ограничения анализа
3. Укажи, какая дополнительная информация нужна
4. Избегай предположений и интерпретаций

ИСТОЧНИКИ: {' '.join([doc[:300] for doc in documents])}

ОТВЕТ должен начинаться с: "ОГРАНИЧЕННЫЙ АНАЛИЗ (недостаточно данных):"
"""

        # ИСПРАВЛЕНИЕ: Правильный вызов через inference_system
        response_data = await self.inference_service.inference_system.generate_response(
            prompt=cautious_prompt,
            temperature=0.1,
            max_tokens=1500
        )
        return response_data.get('response', str(response_data)) if isinstance(response_data, dict) else str(response_data)

    async def _expand_search(self, query: str, search_reasoning: str) -> List[str]:
        """Расширение поиска на основе критики"""

        # Извлекаем ключевые термины из обоснования для дополнительного поиска
        expanded_query = f"{query} {search_reasoning}"

        # Используем семантический поиск с расширенным запросом
        additional_results = await self.storage_manager.search_documents(
            expanded_query,
            k=5,
            similarity_threshold=0.5 # Более низкий порог для расширения
        )

        # FIX: storage_manager returns 'text' key, not 'content'
        return [result.get('text', result.get('content', '')) for result in additional_results]

    async def _detailed_verification(self, answer: str, documents: List[str]) -> Dict:
        """Детальная верификация ответа"""

        verification_prompt = self.legal_prompts.get_verification_prompt(answer, documents)

        # ИСПРАВЛЕНИЕ: Правильный вызов через inference_system
        response_data = await self.inference_service.inference_system.generate_response(
            prompt=verification_prompt,
            temperature=0.1,
            max_tokens=1000
        )
        verification_result = response_data.get('response', str(response_data)) if isinstance(response_data, dict) else str(response_data)

        # Парсинг результатов верификации
        verification_details = {
            'verification_text': verification_result,
            'citation_accuracy': self._extract_verification_score(verification_result, 'ТОЧНОСТЬ ЦИТИРОВАНИЙ'),
            'source_support': self._extract_verification_score(verification_result, 'ПОДДЕРЖКА ИСТОЧНИКАМИ'),
            'legal_logic': self._extract_verification_score(verification_result, 'ПРАВОВАЯ ЛОГИКА'),
            'overall_assessment': self._extract_overall_assessment(verification_result)
        }

        return verification_details

    def _calculate_overall_confidence(self, critique_results: Dict[str, CritiqueResult]) -> float:
        """Расчет общего confidence score"""

        weights = {
            'retrieve': 0.1, # Меньший вес для решения о поиске
            'relevance': 0.3, # Высокий вес для релевантности
            'support': 0.4, # Максимальный вес для поддержки
            'usefulness': 0.2 # Средний вес для полезности
        }

        total_confidence = 0.0
        total_weight = 0.0

        for key, result in critique_results.items():
            if any(weight_key in key for weight_key in weights.keys()):
                weight_key = next(wk for wk in weights.keys() if wk in key)
                weight = weights[weight_key]

                # Штраф за негативные решения
                confidence_multiplier = 1.0 if result.decision.value not in ['NOT_SUPPORTED', 'NOT_USEFUL', 'IRRELEVANT'] else 0.3

                total_confidence += result.confidence * weight * confidence_multiplier
                total_weight += weight

        return min(total_confidence / total_weight if total_weight > 0 else 0.0, 1.0)

    def _extract_reasoning(self, response: str) -> str:
        """Извлечение обоснования из ответа"""
        lines = response.strip().split('\n')
        return ' '.join(lines[1:]) if len(lines) > 1 else response

    def _extract_verification_score(self, text: str, category: str) -> str:
        """Извлечение оценки верификации"""
        pattern = f"{category}:\\s*\\[([^\\]]+)\\]"
        match = re.search(pattern, text)
        return match.group(1) if match else "НЕОПРЕДЕЛЕНО"

    def _extract_overall_assessment(self, text: str) -> str:
        """Извлечение общей оценки"""
        pattern = r"ОБЩАЯ ОЦЕНКА:\s*\[([^\]]+)\]"
        match = re.search(pattern, text)
        return match.group(1) if match else "НЕОПРЕДЕЛЕНО"