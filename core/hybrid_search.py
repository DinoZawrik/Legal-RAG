#!/usr/bin/env python3
"""
Hybrid Legal Search System
Гибридная система поиска для правовых документов.

Объединяет:
- Семантический поиск
- Точное сопоставление правовых ссылок
- Контекстный поиск по истории
- Терминологический поиск по синонимам
- Переранжирование по правовой значимости
"""

import logging
import re
import asyncio
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum
import time
from datetime import datetime

from core.legal_ontology import get_legal_ontology, DocumentType, LegalDomain
from core.smart_query_classifier import get_smart_classifier, QueryAnalysis

logger = logging.getLogger(__name__)


class SearchType(Enum):
    """Типы поиска в гибридной системе."""
    SEMANTIC = "semantic"
    EXACT_REFERENCE = "exact_reference"
    CONTEXTUAL = "contextual"
    TERMINOLOGICAL = "terminological"


@dataclass
class SearchResult:
    """Результат поиска с метаданными."""
    content: str
    document_id: str
    document_type: DocumentType
    legal_domain: LegalDomain
    search_type: SearchType
    base_score: float
    boosted_score: float
    metadata: Dict[str, Any]
    matched_terms: List[str]
    context_relevance: float
    hierarchy_level: int
    recency_bonus: float


@dataclass
class HybridSearchConfig:
    """Конфигурация гибридного поиска."""
    max_results: int = 12
    semantic_weight: float = 0.4
    exact_match_weight: float = 0.3
    contextual_weight: float = 0.2
    terminological_weight: float = 0.1
    min_similarity_threshold: float = 0.55
    max_similarity_threshold: float = 0.95
    enable_query_expansion: bool = True
    enable_contextual_boost: bool = True
    enable_hierarchy_boost: bool = True
    enable_recency_boost: bool = True


class HybridLegalSearch:
    """
    Гибридная система поиска для правовых документов.

    Функции:
    - Многотипный поиск с объединением результатов
    - Интеллектуальное переранжирование
    - Контекстуальная адаптация
    - Правовая специфика
    """

    def __init__(self, config: Optional[HybridSearchConfig] = None):
        """Инициализация гибридной системы поиска."""
        self.config = config or HybridSearchConfig()
        self.legal_ontology = get_legal_ontology()
        self.query_classifier = get_smart_classifier()

        # Компоненты будут инициализированы при первом использовании
        self.vector_store = None
        self.storage_manager = None

        # Кэш для ускорения поиска
        self.search_cache = {}
        self.cache_ttl = 300 # 5 минут

        logger.info(" Hybrid Legal Search инициализирована")

    async def search_with_legal_context(self,
                                      query: str,
                                      user_history: Optional[List[Dict]] = None,
                                      query_analysis: Optional[QueryAnalysis] = None,
                                      filters: Optional[Dict[str, Any]] = None,
                                      max_results: int = 10) -> List[SearchResult]:
        """
        Поиск с учетом правового контекста.

        Args:
            query: Поисковый запрос
            user_history: История пользователя
            query_analysis: Анализ запроса
            filters: Дополнительные фильтры
            max_results: Максимальное количество результатов (по умолчанию 10)

        Returns:
            Список результатов поиска
        """
        start_time = time.time()

        # Проверка кэша
        cache_key = self._generate_cache_key(query, user_history, filters)
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.info(f" Результат из кэша для запроса: {query[:50]}...")
            return cached_result

        # Анализ запроса если не предоставлен
        if not query_analysis:
            query_analysis = self.query_classifier.analyze_query(query, user_history)

        logger.info(f" Гибридный поиск: {query} (интенция: {query_analysis.intent.value})")

        # 1. Расширение запроса синонимами
        expanded_queries = self._expand_query(query, query_analysis)

        # 2. Параллельный поиск по всем типам
        search_tasks = []

        # Семантический поиск
        search_tasks.append(self._semantic_search(expanded_queries, query_analysis))

        # Поиск точных ссылок
        search_tasks.append(self._exact_reference_search(query, expanded_queries))

        # Контекстный поиск
        if user_history:
            search_tasks.append(self._contextual_search(query, user_history, query_analysis))

        # Терминологический поиск
        search_tasks.append(self._terminological_search(query, query_analysis))

        # Выполнение всех поисков параллельно с таймаутом
        try:
            search_results = await asyncio.wait_for(
                asyncio.gather(*search_tasks, return_exceptions=True),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning(" Search tasks timed out after 30s")
            search_results = []

        # 3. Объединение результатов
        all_results = []
        for i, results in enumerate(search_results):
            if isinstance(results, Exception):
                logger.warning(f" Ошибка в поиске типа {i}: {results}")
                continue
            all_results.extend(results)

        # 4. Удаление дубликатов
        unique_results = self._deduplicate_results(all_results)

        # 5. Переранжирование по правовой значимости
        ranked_results = self._rerank_by_legal_significance(
            unique_results, query_analysis, user_history
        )

        # 6. Применение фильтров
        if filters:
            ranked_results = self._apply_filters(ranked_results, filters)

        # 7. Ограничение количества результатов
        final_results = ranked_results[:max_results]

        # Кэширование результата
        self._cache_result(cache_key, final_results)

        search_time = time.time() - start_time
        logger.info(f" Гибридный поиск завершен: {len(final_results)} результатов за {search_time:.2f}с")

        return final_results

    async def _semantic_search(self,
                             expanded_queries: List[str],
                             query_analysis: QueryAnalysis) -> List[SearchResult]:
        """Семантический поиск по векторной базе."""
        if not self.vector_store:
            await self._initialize_components()

        results = []

        try:
            for query in expanded_queries:
                # Используем существующую логику семантического поиска
                # Здесь должна быть интеграция с ChromaDB
                # Пока заглушка для демонстрации архитектуры
                vector_results = await self._query_vector_store(query, top_k=8)

                for result in vector_results:
                    search_result = SearchResult(
                        content=result.get('content', ''),
                        document_id=result.get('document_id', ''),
                        document_type=self._parse_document_type(result.get('metadata', {})),
                        legal_domain=query_analysis.legal_area,
                        search_type=SearchType.SEMANTIC,
                        base_score=result.get('similarity', 0.0),
                        boosted_score=result.get('similarity', 0.0),
                        metadata=result.get('metadata', {}),
                        matched_terms=[],
                        context_relevance=0.0,
                        hierarchy_level=0,
                        recency_bonus=0.0
                    )
                    results.append(search_result)

        except Exception as e:
            logger.error(f" Ошибка семантического поиска: {e}")

        return results

    async def _exact_reference_search(self,
                                    original_query: str,
                                    expanded_queries: List[str]) -> List[SearchResult]:
        """Поиск точных ссылок на правовые нормы."""
        results = []

        try:
            # Извлечение ссылок из запроса
            references = self.legal_ontology.extract_legal_references(original_query)

            for ref in references:
                if ref.article:
                    # Поиск по точной ссылке на статью
                    article_results = await self._search_by_article(ref.article, ref.document_type)

                    for result in article_results:
                        search_result = SearchResult(
                            content=result.get('content', ''),
                            document_id=result.get('document_id', ''),
                            document_type=ref.document_type,
                            legal_domain=self._infer_legal_domain(result),
                            search_type=SearchType.EXACT_REFERENCE,
                            base_score=0.95, # Высокий приоритет для точных ссылок
                            boosted_score=0.95,
                            metadata=result.get('metadata', {}),
                            matched_terms=[f"статья {ref.article}"],
                            context_relevance=0.0,
                            hierarchy_level=self.legal_ontology.get_document_hierarchy_level(ref.document_type),
                            recency_bonus=0.0
                        )
                        results.append(search_result)

        except Exception as e:
            logger.error(f" Ошибка поиска точных ссылок: {e}")

        return results

    async def _contextual_search(self,
                               query: str,
                               user_history: List[Dict],
                               query_analysis: QueryAnalysis) -> List[SearchResult]:
        """Контекстный поиск на основе истории пользователя."""
        results = []

        try:
            if not user_history:
                return results

            # Извлечение контекстных терминов из истории
            context_terms = self._extract_context_terms(user_history, query_analysis.legal_area)

            # Расширение запроса контекстными терминами
            for term in context_terms[:3]: # Берем топ-3 контекстных термина
                contextual_query = f"{query} {term}"
                context_results = await self._query_vector_store(contextual_query, top_k=3)

                for result in context_results:
                    # Вычисляем релевантность контекста
                    context_relevance = self._calculate_context_relevance(result, user_history)

                    search_result = SearchResult(
                        content=result.get('content', ''),
                        document_id=result.get('document_id', ''),
                        document_type=self._parse_document_type(result.get('metadata', {})),
                        legal_domain=query_analysis.legal_area,
                        search_type=SearchType.CONTEXTUAL,
                        base_score=result.get('similarity', 0.0),
                        boosted_score=result.get('similarity', 0.0),
                        metadata=result.get('metadata', {}),
                        matched_terms=[term],
                        context_relevance=context_relevance,
                        hierarchy_level=0,
                        recency_bonus=0.0
                    )
                    results.append(search_result)

        except Exception as e:
            logger.error(f" Ошибка контекстного поиска: {e}")

        return results

    async def _terminological_search(self,
                                   query: str,
                                   query_analysis: QueryAnalysis) -> List[SearchResult]:
        """Поиск по терминологическим синонимам."""
        results = []

        try:
            # Получение синонимов из правовой онтологии
            expanded_queries = self.legal_ontology.expand_synonyms(query)

            for synonym_query in expanded_queries[1:]: # Пропускаем оригинальный запрос
                if synonym_query != query.lower():
                    synonym_results = await self._query_vector_store(synonym_query, top_k=3)

                    for result in synonym_results:
                        search_result = SearchResult(
                            content=result.get('content', ''),
                            document_id=result.get('document_id', ''),
                            document_type=self._parse_document_type(result.get('metadata', {})),
                            legal_domain=query_analysis.legal_area,
                            search_type=SearchType.TERMINOLOGICAL,
                            base_score=result.get('similarity', 0.0) * 0.9, # Небольшой штраф за синонимы
                            boosted_score=result.get('similarity', 0.0) * 0.9,
                            metadata=result.get('metadata', {}),
                            matched_terms=[synonym_query],
                            context_relevance=0.0,
                            hierarchy_level=0,
                            recency_bonus=0.0
                        )
                        results.append(search_result)

        except Exception as e:
            logger.error(f" Ошибка терминологического поиска: {e}")

        return results

    def _rerank_by_legal_significance(self,
                                    results: List[SearchResult],
                                    query_analysis: QueryAnalysis,
                                    user_history: Optional[List[Dict]]) -> List[SearchResult]:
        """Переранжирование результатов по правовой значимости."""

        for result in results:
            boosted_score = result.base_score

            # 1. Бонус за иерархию документа
            if self.config.enable_hierarchy_boost:
                hierarchy_bonus = self._calculate_hierarchy_bonus(result.document_type)
                boosted_score += hierarchy_bonus

            # 2. Бонус за актуальность (новизну)
            if self.config.enable_recency_boost:
                recency_bonus = self._calculate_recency_bonus(result.metadata)
                result.recency_bonus = recency_bonus
                boosted_score += recency_bonus

            # 3. Бонус за соответствие типу запроса
            intent_bonus = self._calculate_intent_bonus(result, query_analysis)
            boosted_score += intent_bonus

            # 4. Бонус за точные совпадения
            exact_match_bonus = self._calculate_exact_match_bonus(result, query_analysis)
            boosted_score += exact_match_bonus

            # 5. Контекстуальный бонус
            if self.config.enable_contextual_boost and user_history:
                context_bonus = result.context_relevance * 0.1
                boosted_score += context_bonus

            # 6. Бонус за тип поиска
            search_type_bonus = self._get_search_type_bonus(result.search_type)
            boosted_score += search_type_bonus

            result.boosted_score = min(boosted_score, 1.0) # Ограничиваем максимальным значением

        # Сортировка по boosted_score
        return sorted(results, key=lambda x: x.boosted_score, reverse=True)

    def _calculate_hierarchy_bonus(self, document_type: DocumentType) -> float:
        """Расчет бонуса за иерархию документа."""
        hierarchy_level = self.legal_ontology.get_document_hierarchy_level(document_type)

        # Чем выше в иерархии, тем больше бонус
        if hierarchy_level <= 2: # Конституция, ФЗ, Кодексы
            return 0.15
        elif hierarchy_level <= 4: # Указы, Постановления
            return 0.10
        elif hierarchy_level <= 6: # Приказы, Стандарты
            return 0.05
        else:
            return 0.0

    def _calculate_recency_bonus(self, metadata: Dict[str, Any]) -> float:
        """Расчет бонуса за актуальность документа."""
        try:
            # Приоритет: adoption_date > processed_at > created_at > document_date
            date_fields = ['adoption_date', 'processed_at', 'created_at', 'document_date']
            document_date = None

            for field in date_fields:
                if field in metadata and metadata[field]:
                    if isinstance(metadata[field], str):
                        try:
                            document_date = datetime.fromisoformat(metadata[field].replace('Z', '+00:00'))
                            break
                        except ValueError:
                            continue
                    elif isinstance(metadata[field], datetime):
                        document_date = metadata[field]
                        break

            if not document_date:
                return 0.0

            # Расчет возраста документа в днях
            age_days = (datetime.now() - document_date.replace(tzinfo=None)).days

            # Градированный бонус
            if age_days < 30:
                return 0.15 # Документы младше месяца
            elif age_days < 90:
                return 0.10 # Документы младше 3 месяцев
            elif age_days < 365:
                return 0.05 # Документы младше года
            elif age_days < 1825: # 5 лет
                return 0.02 # Документы младше 5 лет
            else:
                return 0.0

        except Exception as e:
            logger.debug(f"Ошибка расчета recency bonus: {e}")
            return 0.0

    def _calculate_intent_bonus(self, result: SearchResult, query_analysis: QueryAnalysis) -> float:
        """Расчет бонуса за соответствие интенции запроса."""
        content_lower = result.content.lower()

        intent_keywords = {
            'find_norm': ['статья', 'пункт', 'требования', 'нормы'],
            'explain_procedure': ['порядок', 'процедура', 'как', 'этапы'],
            'compare_requirements': ['различия', 'сравнение', 'отличия'],
            'find_responsibility': ['ответственность', 'штраф', 'санкции'],
            'get_definition': ['определение', 'понятие', 'означает'],
            'calculate_parameters': ['расчет', 'формула', 'параметры']
        }

        keywords = intent_keywords.get(query_analysis.intent.value, [])
        matches = sum(1 for keyword in keywords if keyword in content_lower)

        return min(matches * 0.05, 0.2) # Максимум 0.2 бонуса

    def _calculate_exact_match_bonus(self, result: SearchResult, query_analysis: QueryAnalysis) -> float:
        """Расчет бонуса за точные совпадения."""
        bonus = 0.0
        content_lower = result.content.lower()

        # Бонус за ключевые термины из запроса
        for term in query_analysis.key_concepts:
            if term.lower() in content_lower:
                bonus += 0.05

        # Бонус за точные ссылки
        for ref in query_analysis.extracted_references:
            if ref.lower() in content_lower:
                bonus += 0.10

        return min(bonus, 0.3) # Максимум 0.3 бонуса

    def _get_search_type_bonus(self, search_type: SearchType) -> float:
        """Получение бонуса в зависимости от типа поиска."""
        bonuses = {
            SearchType.EXACT_REFERENCE: 0.20, # Максимальный приоритет
            SearchType.SEMANTIC: 0.10,
            SearchType.CONTEXTUAL: 0.05,
            SearchType.TERMINOLOGICAL: 0.03
        }
        return bonuses.get(search_type, 0.0)

    def _expand_query(self, query: str, query_analysis: QueryAnalysis) -> List[str]:
        """Расширение запроса для улучшения поиска."""
        if not self.config.enable_query_expansion:
            return [query]

        expanded = [query]

        # Добавление синонимов
        synonyms = self.legal_ontology.expand_synonyms(query)
        expanded.extend(synonyms[:3]) # Максимум 3 синонима

        # Добавление ключевых терминов
        for term in query_analysis.key_concepts[:2]: # Максимум 2 термина
            if term not in query.lower():
                expanded.append(f"{query} {term}")

        return list(set(expanded)) # Убираем дубликаты

    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Удаление дубликатов из результатов поиска."""
        seen_documents = set()
        unique_results = []

        for result in results:
            # Создаем ключ для дедупликации
            dedup_key = (result.document_id, result.content[:100])

            if dedup_key not in seen_documents:
                seen_documents.add(dedup_key)
                unique_results.append(result)

        return unique_results

    def _apply_filters(self, results: List[SearchResult], filters: Dict[str, Any]) -> List[SearchResult]:
        """Применение фильтров к результатам."""
        filtered_results = results

        # Фильтр по типу документа
        if 'document_types' in filters:
            allowed_types = set(filters['document_types'])
            filtered_results = [r for r in filtered_results if r.document_type.value in allowed_types]

        # Фильтр по правовой отрасли
        if 'legal_domains' in filters:
            allowed_domains = set(filters['legal_domains'])
            filtered_results = [r for r in filtered_results if r.legal_domain.value in allowed_domains]

        # Фильтр по минимальному скору
        if 'min_score' in filters:
            min_score = filters['min_score']
            filtered_results = [r for r in filtered_results if r.boosted_score >= min_score]

        return filtered_results

    # Вспомогательные методы для интеграции с существующими компонентами

    async def _initialize_components(self):
        """Инициализация компонентов поиска."""
        try:
            # Здесь должна быть инициализация векторного хранилища
            # Интеграция с существующим ChromaDB
            from core.storage_coordinator import create_storage_coordinator
            self.storage_manager = await create_storage_coordinator()
            logger.info(" Компоненты поиска инициализированы")
        except Exception as e:
            logger.error(f" Ошибка инициализации компонентов: {e}")

    async def _query_vector_store(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Запрос к векторному хранилищу."""
        # Заглушка для интеграции с существующим векторным поиском
        # Здесь должна быть интеграция с ChromaDB через storage_manager
        try:
            if self.storage_manager:
                # Используем существующий метод поиска
                results = await self.storage_manager.search_documents(query, top_k)
                return results
            else:
                return []
        except Exception as e:
            logger.error(f" Ошибка запроса к векторному хранилищу: {e}")
            return []

    async def _search_by_article(self, article: str, document_type: DocumentType) -> List[Dict[str, Any]]:
        """Поиск по номеру статьи."""
        # Заглушка для поиска по точным ссылкам
        query = f"статья {article}"
        return await self._query_vector_store(query, top_k=3)

    def _parse_document_type(self, metadata: Dict[str, Any]) -> DocumentType:
        """Парсинг типа документа из метаданных."""
        doc_type_str = metadata.get('document_type', 'other')
        try:
            return DocumentType(doc_type_str)
        except ValueError:
            return DocumentType.OTHER

    def _infer_legal_domain(self, result: Dict[str, Any]) -> LegalDomain:
        """Определение правовой отрасли для результата."""
        content = result.get('content', '')
        domain, _ = self.legal_ontology.get_legal_domain(content)
        return domain

    def _extract_context_terms(self, user_history: List[Dict], legal_domain: LegalDomain) -> List[str]:
        """Извлечение контекстных терминов из истории пользователя."""
        context_terms = []

        for entry in user_history[-3:]: # Последние 3 записи
            question = entry.get('question', '')
            answer = entry.get('answer', '')

            # Извлекаем ключевые термины
            terms = []
            for text in [question, answer]:
                text_terms = self.legal_ontology.expand_synonyms(text)
                terms.extend(text_terms)

            context_terms.extend(terms)

        # Убираем дубликаты и возвращаем топ-5
        return list(set(context_terms))[:5]

    def _calculate_context_relevance(self, result: Dict[str, Any], user_history: List[Dict]) -> float:
        """Расчет релевантности контекста."""
        content = result.get('content', '').lower()
        relevance = 0.0

        for entry in user_history:
            question = entry.get('question', '').lower()
            # Простое пересечение слов
            question_words = set(question.split())
            content_words = set(content.split())

            intersection = question_words & content_words
            if question_words:
                relevance += len(intersection) / len(question_words)

        return min(relevance / len(user_history) if user_history else 0, 1.0)

    def _generate_cache_key(self, query: str, user_history: Optional[List[Dict]], filters: Optional[Dict[str, Any]]) -> str:
        """Генерация ключа для кэширования."""
        history_hash = hash(str(user_history)) if user_history else 0
        filters_hash = hash(str(filters)) if filters else 0
        return f"{hash(query)}_{history_hash}_{filters_hash}"

    def _get_cached_result(self, cache_key: str) -> Optional[List[SearchResult]]:
        """Получение результата из кэша."""
        if cache_key in self.search_cache:
            cached_entry = self.search_cache[cache_key]
            if time.time() - cached_entry['timestamp'] < self.cache_ttl:
                return cached_entry['results']
            else:
                del self.search_cache[cache_key]
        return None

    def _cache_result(self, cache_key: str, results: List[SearchResult]) -> None:
        """Кэширование результата."""
        self.search_cache[cache_key] = {
            'results': results,
            'timestamp': time.time()
        }

        # Ограничиваем размер кэша
        if len(self.search_cache) > 100:
            oldest_key = min(self.search_cache.keys(),
                           key=lambda k: self.search_cache[k]['timestamp'])
            del self.search_cache[oldest_key]


# Глобальный экземпляр гибридного поиска
_hybrid_search = None

def get_hybrid_search() -> HybridLegalSearch:
    """Получение глобального экземпляра гибридного поиска."""
    global _hybrid_search
    if _hybrid_search is None:
        _hybrid_search = HybridLegalSearch()
    return _hybrid_search


if __name__ == "__main__":
    # Демонстрация возможностей гибридного поиска
    print(" Hybrid Legal Search - Демонстрация")
    print("=" * 50)

    async def demo():
        search = HybridLegalSearch()

        test_queries = [
            "Статья 51 ГрК РФ о разрешениях на строительство",
            "Как получить разрешение на строительство?",
            "Требования к отоплению жилых зданий",
            "Ответственность за нарушение 44-ФЗ"
        ]

        for query in test_queries:
            print(f"\n Запрос: {query}")

            try:
                results = await search.search_with_legal_context(
                    query=query,
                    user_history=[],
                    filters={'min_score': 0.3}
                )

                print(f" Найдено результатов: {len(results)}")

                for i, result in enumerate(results[:3]):
                    print(f" {i+1}. Тип поиска: {result.search_type.value}")
                    print(f" Скор: {result.boosted_score:.3f}")
                    print(f" Тип документа: {result.document_type.value}")
                    print(f" Контент: {result.content[:100]}...")

            except Exception as e:
                print(f" Ошибка: {e}")

    asyncio.run(demo())