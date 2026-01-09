#!/usr/bin/env python3
"""
Answer Verification Layer для проверки корректности ответов AI

ПРОБЛЕМА: Система генерирует "галлюцинации" - несуществующие статьи
- Вопрос 6-7: Цитирует "Статью 6" (не существует в 115-ФЗ)
- Вопрос 19-20: Цитирует "Статья 13, Часть 2" (не существует)
- 20% ошибок - это wrong article citations

РЕШЕНИЕ: Post-generation verification
1. Извлечение всех цитат статей из ответа
2. Проверка существования цитируемых статей в исходных чанках
3. Проверка соответствия контента ответа исходным текстам
4. Флаг "⚠️ Low Confidence" если проверка не прошла

ОЖИДАЕМЫЙ ЭФФЕКТ:
- Wrong article citations: 3 → 0 ошибок (-100%)
- False negatives: снижение за счет обнаружения несоответствий
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CitationMatch:
    """Результат проверки цитирования"""
    article_number: str
    exists_in_source: bool
    source_chunks: List[str]  # Чанки, содержащие эту статью
    confidence: float


@dataclass
class VerificationResult:
    """Результат верификации ответа"""
    is_valid: bool
    confidence: float
    citations_valid: bool
    content_match_score: float
    warnings: List[str]
    verified_citations: List[CitationMatch]


class AnswerVerifier:
    """
    Верификатор ответов для предотвращения галлюцинаций

    Usage:
    ```python
    verifier = AnswerVerifier()
    result = verifier.verify_answer(
        answer="Статья 10.1 определяет плату концедента...",
        source_chunks=[chunk1, chunk2, chunk3]
    )
    if not result.is_valid:
        print(f"⚠️ Низкая уверенность: {result.warnings}")
    ```
    """

    def __init__(self, min_confidence: float = 0.6):
        """
        Args:
            min_confidence: Минимальная уверенность для валидного ответа (0.0-1.0)
        """
        self.min_confidence = min_confidence
        self.logger = logging.getLogger(self.__class__.__name__)

        # Regex для извлечения статей из текста
        self.article_patterns = [
            r'Статья\s+(\d+(?:\.\d+)?)',  # Статья 10.1
            r'статья\s+(\d+(?:\.\d+)?)',  # статья 10.1 (lowercase)
            r'Статье\s+(\d+(?:\.\d+)?)',  # Статье 10.1 (дательный падеж)
            r'статье\s+(\d+(?:\.\d+)?)',  # статье 10.1
            r'Статьи\s+(\d+(?:\.\d+)?)',  # Статьи 10.1 (родительный)
            r'статьи\s+(\d+(?:\.\d+)?)',  # статьи 10.1
        ]

    def verify_answer(
        self,
        answer: str,
        source_chunks: List[Dict],
        query: Optional[str] = None
    ) -> VerificationResult:
        """
        Основной метод верификации ответа

        Args:
            answer: Сгенерированный AI ответ
            source_chunks: Чанки, использованные для генерации
            query: Исходный запрос (опционально, для контекстной проверки)

        Returns:
            VerificationResult с детальной информацией о проверке
        """
        warnings = []
        verified_citations = []

        # Шаг 1: Проверка цитирований статей
        citations_valid, citation_matches = self._verify_citations(answer, source_chunks)

        verified_citations.extend(citation_matches)

        if not citations_valid:
            warnings.append(
                f"Обнаружены цитирования несуществующих статей: "
                f"{[c.article_number for c in citation_matches if not c.exists_in_source]}"
            )

        # Шаг 2: Проверка соответствия контента
        content_match_score = self._verify_content_match(answer, source_chunks)

        if content_match_score < 0.5:
            warnings.append(
                f"Низкое соответствие ответа исходным текстам ({content_match_score:.2f})"
            )

        # Шаг 3: Проверка на "недостаточно информации"
        if self._is_insufficient_info_response(answer):
            # Проверяем, действительно ли нет информации
            if content_match_score > 0.3:
                warnings.append(
                    "Ответ 'недостаточно информации', но релевантные чанки найдены"
                )

        # Шаг 4: Вычисление итоговой уверенности
        confidence = self._calculate_confidence(
            citations_valid=citations_valid,
            content_match_score=content_match_score,
            has_citations=len(citation_matches) > 0
        )

        # Шаг 5: Итоговый вердикт
        is_valid = (confidence >= self.min_confidence) and citations_valid

        result = VerificationResult(
            is_valid=is_valid,
            confidence=confidence,
            citations_valid=citations_valid,
            content_match_score=content_match_score,
            warnings=warnings,
            verified_citations=verified_citations
        )

        # Логирование
        if not is_valid:
            self.logger.warning(
                f"[VERIFICATION FAILED] Confidence: {confidence:.2f}, "
                f"Warnings: {len(warnings)}, Answer preview: {answer[:100]}..."
            )
        else:
            self.logger.info(
                f"[VERIFICATION PASSED] Confidence: {confidence:.2f}"
            )

        return result

    def _verify_citations(
        self,
        answer: str,
        source_chunks: List[Dict]
    ) -> Tuple[bool, List[CitationMatch]]:
        """
        Проверка всех цитирований статей в ответе

        Returns:
            (citations_valid: bool, matches: List[CitationMatch])
        """
        # Извлекаем все статьи из ответа
        cited_articles = self._extract_articles(answer)

        if not cited_articles:
            # Нет цитирований - не можем проверить
            return True, []

        # Извлекаем все статьи из исходных чанков
        source_articles = set()
        article_to_chunks = {}

        for chunk in source_chunks:
            chunk_text = chunk.get('text', '') if isinstance(chunk, dict) else str(chunk)
            chunk_articles = self._extract_articles(chunk_text)

            for article in chunk_articles:
                source_articles.add(article)
                if article not in article_to_chunks:
                    article_to_chunks[article] = []
                article_to_chunks[article].append(chunk_text[:200])  # Первые 200 символов

        # Проверяем каждое цитирование
        matches = []
        all_valid = True

        for cited_article in cited_articles:
            exists = cited_article in source_articles

            match = CitationMatch(
                article_number=cited_article,
                exists_in_source=exists,
                source_chunks=article_to_chunks.get(cited_article, []),
                confidence=1.0 if exists else 0.0
            )
            matches.append(match)

            if not exists:
                all_valid = False
                self.logger.warning(
                    f"[CITATION ERROR] Answer cites Article {cited_article}, "
                    f"but it's not in source chunks!"
                )

        return all_valid, matches

    def _extract_articles(self, text: str) -> List[str]:
        """
        Извлечение всех упоминаний статей из текста

        Returns:
            List of article numbers (e.g., ['10.1', '5', '22'])
        """
        articles = set()

        for pattern in self.article_patterns:
            matches = re.findall(pattern, text)
            articles.update(matches)

        return sorted(list(articles), key=lambda x: float(x) if '.' not in x else float(x))

    def _verify_content_match(
        self,
        answer: str,
        source_chunks: List[Dict]
    ) -> float:
        """
        Проверка соответствия контента ответа исходным чанкам

        Returns:
            Score от 0.0 до 1.0 (1.0 = полное соответствие)
        """
        # Простая проверка: какой процент ключевых слов ответа есть в чанках
        answer_keywords = self._extract_keywords(answer)

        if not answer_keywords:
            return 0.5  # Нейтральный score если не можем извлечь keywords

        # Объединяем все чанки в один текст
        source_text = ' '.join([
            chunk.get('text', '') if isinstance(chunk, dict) else str(chunk)
            for chunk in source_chunks
        ]).lower()

        # Считаем сколько keywords из ответа есть в исходном тексте
        matched_keywords = 0
        for keyword in answer_keywords:
            if keyword.lower() in source_text:
                matched_keywords += 1

        match_ratio = matched_keywords / len(answer_keywords) if answer_keywords else 0

        return match_ratio

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Извлечение ключевых слов из текста (существительные и важные термины)
        """
        # Простая версия: слова длиной >4 символов, исключая стоп-слова
        stop_words = {
            'это', 'который', 'какой', 'может', 'быть', 'если', 'того',
            'этого', 'данный', 'также', 'должен', 'таким', 'образом',
            'согласно', 'соответствии', 'основании', 'случае'
        }

        # Токенизация
        words = re.findall(r'\b[а-яА-ЯёЁ]{4,}\b', text.lower())

        # Фильтрация
        keywords = [
            word for word in words
            if word not in stop_words
        ]

        return keywords[:50]  # Берем первые 50 keywords

    def _is_insufficient_info_response(self, answer: str) -> bool:
        """
        Проверка, является ли ответ "недостаточно информации"
        """
        insufficient_phrases = [
            'недостаточно информации',
            'нет информации',
            'информация отсутствует',
            'не содержит',
            'не содержится',
            'не предусмотрено',
            'не определено',
            'не указано',
        ]

        answer_lower = answer.lower()

        for phrase in insufficient_phrases:
            if phrase in answer_lower:
                return True

        return False

    def _calculate_confidence(
        self,
        citations_valid: bool,
        content_match_score: float,
        has_citations: bool
    ) -> float:
        """
        Расчет итоговой уверенности в ответе

        Формула:
        - citations_valid: 0.4 веса (критично!)
        - content_match_score: 0.5 веса
        - has_citations: 0.1 веса (бонус если есть цитаты)
        """
        citation_score = 1.0 if citations_valid else 0.0
        citation_bonus = 0.1 if has_citations else 0.0

        confidence = (
            (citation_score * 0.4) +
            (content_match_score * 0.5) +
            citation_bonus
        )

        return min(confidence, 1.0)  # Cap at 1.0

    def format_warning_message(self, result: VerificationResult) -> str:
        """
        Форматирование предупреждающего сообщения для низкой уверенности

        Returns:
            Строка с предупреждением для добавления к ответу
        """
        if result.is_valid:
            return ""

        warning_parts = [
            f"\n\n⚠️ ПРЕДУПРЕЖДЕНИЕ: Низкая уверенность в ответе ({result.confidence:.1%})"
        ]

        if result.warnings:
            warning_parts.append("\nПроблемы:")
            for i, warning in enumerate(result.warnings, 1):
                warning_parts.append(f"  {i}. {warning}")

        if not result.citations_valid:
            invalid_citations = [
                c.article_number for c in result.verified_citations
                if not c.exists_in_source
            ]
            warning_parts.append(
                f"\n⚠️ Ответ ссылается на статьи, которые отсутствуют в исходных документах: "
                f"{', '.join(invalid_citations)}"
            )

        warning_parts.append("\n🔍 Рекомендуется проверить ответ вручную.")

        return '\n'.join(warning_parts)


# Singleton instance
_answer_verifier: Optional[AnswerVerifier] = None


def get_answer_verifier(min_confidence: float = 0.6) -> AnswerVerifier:
    """
    Получить singleton instance AnswerVerifier
    """
    global _answer_verifier

    if _answer_verifier is None:
        _answer_verifier = AnswerVerifier(min_confidence=min_confidence)

    return _answer_verifier


def verify_answer(
    answer: str,
    source_chunks: List[Dict],
    min_confidence: float = 0.6
) -> VerificationResult:
    """
    Convenience function для верификации ответа

    Usage:
    ```python
    result = verify_answer(
        answer=ai_generated_answer,
        source_chunks=retrieved_chunks,
        min_confidence=0.6
    )

    if not result.is_valid:
        answer += result.format_warning_message()
    ```
    """
    verifier = get_answer_verifier(min_confidence=min_confidence)
    return verifier.verify_answer(answer, source_chunks)
