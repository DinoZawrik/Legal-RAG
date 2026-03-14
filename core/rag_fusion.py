"""
RAG-Fusion Implementation for LegalRAG
Improves retrieval through multi-query approach
"""

import asyncio
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RAGFusion:
    """
    RAG-Fusion: улучшенный retrieval через multiple queries

    Подход:
    1. Генерируем несколько вариаций исходного запроса
    2. Выполняем поиск для каждой вариации
    3. Объединяем результаты с Reciprocal Rank Fusion
    4. Возвращаем топ-N переранжированных документов
    """

    def __init__(self, storage_manager, inference_system=None):
        self.storage = storage_manager
        self.inference = inference_system
        self.logger = logger

    def generate_query_variations(self, original_query: str) -> List[str]:
        """
        Генерирует вариации запроса без AI (rule-based)

        Стратегии:
        1. Оригинальный запрос
        2. Добавление контекста (115-ФЗ, концессия)
        3. Переформулирование (что/какой/как определение/описание)
        4. Разбиение сложных вопросов
        """
        variations = [original_query]

        query_lower = original_query.lower()

        # Стратегия 1: Добавляем правовой контекст если не указан
        if '115-фз' not in query_lower and '224-фз' not in query_lower:
            if 'концесс' in query_lower:
                variations.append(f"{original_query} по 115-ФЗ")
            if 'партнер' in query_lower or 'гчп' in query_lower or 'мчп' in query_lower:
                variations.append(f"{original_query} по 224-ФЗ")

        # Стратегия 2: Переформулирование вопросов в определения
        replacements = [
            ('что такое', 'определение'),
            ('какие права', 'права перечень'),
            ('какие обязанности', 'обязанности перечень'),
            ('может ли', 'возможность допустимость'),
            ('как заключается', 'порядок заключения'),
            ('какой срок', 'срок период действия'),
            ('кто может быть', 'субъекты'),
            ('в каких случаях', 'основания причины')
        ]

        for old, new in replacements:
            if old in query_lower:
                reformulated = original_query.lower().replace(old, new)
                variations.append(reformulated)
                break

        # Стратегия 3: Извлечение ключевых терминов
        key_terms = []
        legal_terms = [
            'концессионное соглашение', 'концедент', 'концессионер',
            'плата концедента', 'объект концессионного соглашения',
            'конкурсная документация', 'государственно-частное партнерство',
            'частная инициатива'
        ]

        for term in legal_terms:
            if term in query_lower:
                key_terms.append(term)

        if key_terms:
            # Создаем запрос только с ключевыми терминами
            variations.append(' '.join(key_terms))

        # Убираем дубликаты
        seen = set()
        unique_variations = []
        for v in variations:
            v_normalized = v.lower().strip()
            if v_normalized not in seen:
                seen.add(v_normalized)
                unique_variations.append(v)

        # PHASE 2.1: Enhanced logging for debugging
        self.logger.info(f"[ RAG-FUSION] Generated {len(unique_variations)} query variations from: '{original_query}'")
        for i, var in enumerate(unique_variations, 1):
            self.logger.info(f" Variation {i}: {var}")

        return unique_variations

    async def reciprocal_rank_fusion(
        self,
        results_per_query: List[List[Dict]],
        k: int = 60
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF) для объединения результатов

        Formula: RRF_score(doc) = Σ(1 / (k + rank(doc, query_i)))

        Args:
            results_per_query: Список результатов для каждого запроса
            k: Константа сглаживания (обычно 60)

        Returns:
            Отсортированный список документов с RRF scores
        """
        doc_scores = {} # doc_id -> {score, doc_data}

        for query_idx, results in enumerate(results_per_query):
            for rank, doc in enumerate(results, start=1):
                doc_id = doc.get('id', f"doc_{rank}_q{query_idx}")

                # RRF score
                rrf_score = 1.0 / (k + rank)

                if doc_id in doc_scores:
                    doc_scores[doc_id]['score'] += rrf_score
                    doc_scores[doc_id]['query_count'] += 1
                else:
                    doc_scores[doc_id] = {
                        'score': rrf_score,
                        'doc': doc,
                        'query_count': 1,
                        'ranks': [rank]
                    }
                    doc_scores[doc_id]['ranks'].append(rank)

        # Сортируем по RRF score (выше = лучше)
        ranked_docs = sorted(
            doc_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )

        # Добавляем RRF метаданные к документам
        final_results = []
        for item in ranked_docs:
            doc = item['doc'].copy()
            doc['rrf_score'] = item['score']
            doc['query_appearances'] = item['query_count']
            final_results.append(doc)

        # PHASE 2.1: Enhanced RRF logging
        self.logger.info(f"[ RRF] Fused {len(doc_scores)} unique documents from {len(results_per_query)} queries")
        if final_results:
            self.logger.info(f"[ TOP-3 RRF SCORES]:")
            for i, doc in enumerate(final_results[:3], 1):
                law = doc.get('metadata', {}).get('law', 'unknown')
                similarity = doc.get('similarity', doc.get('distance', 0))
                self.logger.info(f" {i}. RRF={doc['rrf_score']:.4f}, Law={law}, Similarity={similarity:.3f}, Appearances={doc['query_appearances']}")

        return final_results

    async def search_with_fusion(
        self,
        query: str,
        top_k: int = 10,
        queries_per_variation: int = 3
    ) -> List[Dict]:
        """
        Выполняет RAG-Fusion search

        Args:
            query: Исходный запрос пользователя
            top_k: Количество итоговых документов
            queries_per_variation: Сколько вариаций запроса использовать

        Returns:
            Список документов с RRF scores
        """
        try:
            # 1. Генерируем вариации запроса
            variations = self.generate_query_variations(query)
            variations = variations[:queries_per_variation]

            self.logger.info(f"[RAG-FUSION] Searching with {len(variations)} queries")

            # 2. Параллельный поиск для всех вариаций
            search_tasks = []
            for variation in variations:
                task = self.storage.search_documents(
                    query=variation,
                    k=top_k * 2, # Больше результатов для fusion
                    similarity_threshold=0.0 # Берем все
                )
                search_tasks.append(task)

            results_per_query = await asyncio.gather(*search_tasks)

            # Логируем результаты
            for i, results in enumerate(results_per_query):
                self.logger.debug(f" Query {i+1} returned {len(results)} docs")

            # 3. Применяем Reciprocal Rank Fusion
            fused_results = await self.reciprocal_rank_fusion(results_per_query)

            # 4. Возвращаем топ-K
            final_results = fused_results[:top_k]

            self.logger.info(
                f"[RAG-FUSION] Complete: {len(final_results)} docs, "
                f"avg RRF score: {sum(d['rrf_score'] for d in final_results) / len(final_results):.3f}"
            )

            return final_results

        except Exception as e:
            self.logger.error(f"[RAG-FUSION] Error: {e}")
            # Fallback к обычному поиску
            return await self.storage.search_documents(query, k=top_k)

    async def search_with_expansion(
        self,
        query: str,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Упрощенная версия: query expansion без RRF
        Быстрее но менее точно чем full RAG-Fusion
        """
        try:
            variations = self.generate_query_variations(query)

            # Создаем единый расширенный запрос
            expanded_query = ' | '.join(variations[:3])

            self.logger.info(f"[QUERY-EXPANSION] {len(variations)} variations single query")

            results = await self.storage.search_documents(
                query=expanded_query,
                k=top_k
            )

            return results

        except Exception as e:
            self.logger.error(f"[QUERY-EXPANSION] Error: {e}")
            return await self.storage.search_documents(query, k=top_k)


# Вспомогательная функция для интеграции
async def enhance_retrieval_with_fusion(
    storage_manager,
    query: str,
    method: str = 'fusion', # 'fusion' или 'expansion'
    top_k: int = 10
) -> List[Dict]:
    """
    Публичный API для использования RAG-Fusion

    Args:
        storage_manager: Менеджер хранилища (с search_documents методом)
        query: Запрос пользователя
        method: 'fusion' (медленнее, точнее) или 'expansion' (быстрее)
        top_k: Количество документов

    Returns:
        Список документов
    """
    rag_fusion = RAGFusion(storage_manager)

    if method == 'fusion':
        return await rag_fusion.search_with_fusion(query, top_k)
    elif method == 'expansion':
        return await rag_fusion.search_with_expansion(query, top_k)
    else:
        # Fallback
        return await storage_manager.search_documents(query, k=top_k)