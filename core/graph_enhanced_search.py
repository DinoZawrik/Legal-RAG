#!/usr/bin/env python3
"""
Graph-Enhanced Hybrid Search (Day 2-3)
Комбинирует BM25 + Semantic + Neo4j Graph Traversal

Архитектура:
1. Hybrid BM25+Semantic поиск находит TOP-K релевантных статей
2. Neo4j Graph Traversal обогащает контекст связанными статьями
3. Финальное ранжирование с учетом графовой близости
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from neo4j import AsyncGraphDatabase
import os

logger = logging.getLogger(__name__)


@dataclass
class GraphEnrichedResult:
    """Результат поиска с графовым обогащением"""
    # Оригинальный результат
    text: str
    metadata: Dict[str, Any]
    hybrid_score: float
    bm25_score: float
    semantic_score: float

    # Графовое обогащение
    graph_context: List[Dict[str, Any]] # Связанные статьи из графа
    graph_score: float # Бонус за графовую релевантность
    final_score: float # Итоговая оценка

    # Дополнительно
    article_number: Optional[str] = None
    law_number: Optional[str] = None


class GraphEnhancedHybridSearch:
    """
    График-обогащенный гибридный поиск

    Стратегия:
    1. Hybrid Search (BM25 + Semantic) TOP-K статей
    2. Для каждой найденной статьи:
       - Извлекаем связанные статьи из Neo4j (RELATED_TO, REFERENCES)
       - Анализируем графовую близость
    3. Обогащаем контекст связанными статьями
    4. Пересчитываем финальный score с учетом графа
    """

    def __init__(
        self,
        neo4j_uri: str = None,
        neo4j_user: str = None,
        neo4j_password: str = None
    ):
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD", "change_me_in_env")

        self.driver = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def connect(self) -> bool:
        """
        Подключение к Neo4j
        Context7 best practice: Use AsyncGraphDatabase with async context manager
        """
        try:
            # Context7 pattern: AsyncGraphDatabase.driver with async/await
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )

            # Проверка соединения с async session
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                test_value = record["test"]

                if test_value == 1:
                    self.logger.info(f"[GRAPH] Connected to Neo4j at {self.neo4j_uri}")
                    return True
                else:
                    self.logger.error("[GRAPH] Neo4j connection test failed")
                    return False

        except Exception as e:
            self.logger.error(f"[GRAPH] Failed to connect to Neo4j: {e}")
            return False

    def extract_article_info(self, metadata: Dict[str, Any], text: str = "") -> tuple:
        """
        Извлечение номера статьи и закона из metadata и текста

        Args:
            metadata: Метаданные документа
            text: Текст документа (для извлечения номера статьи)

        Returns:
            tuple: (law_number, article_number)
        """
        import re

        law = metadata.get('law', '')

        # Сначала проверяем metadata
        article = metadata.get('article', metadata.get('article_number', ''))

        # Если в metadata нет статьи, извлекаем из текста
        if not article and text:
            # Паттерн: "Статья 123." или "Статья 12.3."
            match = re.search(r'Статья\s+(\d+(?:\.\d+)?)', text, re.IGNORECASE)
            if match:
                article = match.group(1)
                self.logger.debug(f"[GRAPH] Extracted article {article} from text")

        return law, article

    async def get_related_articles(
        self,
        law_number: str,
        article_number: str,
        depth: int = 1,
        max_related: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Получение связанных статей из Neo4j

        Args:
            law_number: Номер закона (например, "115-ФЗ")
            article_number: Номер статьи (например, "3")
            depth: Глубина графового обхода (1 или 2)
            max_related: Максимум связанных статей

        Returns:
            Список связанных статей с их текстами и метаданными
        """
        if not self.driver:
            self.logger.warning("[GRAPH] Neo4j not connected, skipping graph enrichment")
            return []

        try:
            # Context7 best practice: Use async with for session management
            async with self.driver.session() as session:
                # Cypher-запрос для поиска связанных статей
                query = f"""
                    MATCH (a:Article {{law_number: $law, article_number: $article}})
                    MATCH path = (a)-[r:RELATED_TO|REFERENCES*1..{depth}]-(related:Article)
                    WHERE related <> a
                    RETURN DISTINCT
                        related.law_number as law,
                        related.article_number as article,
                        related.title as title,
                        related.text as text,
                        length(path) as distance,
                        type(relationships(path)[0]) as rel_type
                    ORDER BY distance ASC, related.article_number ASC
                    LIMIT $max_related
                """

                # Context7: await async operations
                result = await session.run(query, {
                    'law': law_number,
                    'article': article_number,
                    'max_related': max_related
                })

                related_articles = []
                # Context7: iterate async result
                async for record in result:
                    related_articles.append({
                        'law_number': record['law'],
                        'article_number': record['article'],
                        'title': record['title'],
                        'text': record['text'][:2000], # Первые 2000 символов
                        'distance': record['distance'],
                        'relation_type': record['rel_type']
                    })

                self.logger.info(
                    f"[GRAPH] Found {len(related_articles)} related articles "
                    f"for {law_number} Article {article_number}"
                )

                return related_articles

        except Exception as e:
            self.logger.error(f"[GRAPH] Error getting related articles: {e}")
            return []

    def calculate_graph_score(
        self,
        related_articles: List[Dict[str, Any]],
        base_score: float
    ) -> float:
        """
        Расчет графового бонуса

        Стратегия:
        - Наличие связанных статей = +0.05 до +0.15 к score
        - Чем ближе статьи (distance=1), тем выше бонус
        - REFERENCES связи важнее чем RELATED_TO
        """
        if not related_articles:
            return 0.0

        graph_bonus = 0.0

        # Бонус за количество связанных статей (до 0.05)
        article_count_bonus = min(0.05, len(related_articles) * 0.01)
        graph_bonus += article_count_bonus

        # Бонус за близкие статьи (distance=1)
        close_articles = [a for a in related_articles if a['distance'] == 1]
        if close_articles:
            proximity_bonus = min(0.05, len(close_articles) * 0.025)
            graph_bonus += proximity_bonus

        # Бонус за REFERENCES связи (прямые ссылки)
        reference_articles = [a for a in related_articles if a['relation_type'] == 'REFERENCES']
        if reference_articles:
            reference_bonus = min(0.05, len(reference_articles) * 0.03)
            graph_bonus += reference_bonus

        return graph_bonus

    async def enrich_with_graph(
        self,
        hybrid_results: List[Dict[str, Any]],
        graph_depth: int = 1,
        max_related_per_article: int = 3
    ) -> List[GraphEnrichedResult]:
        """
        Обогащение гибридных результатов графовым контекстом

        Args:
            hybrid_results: Результаты Hybrid BM25+Semantic поиска
            graph_depth: Глубина графового обхода (1 или 2)
            max_related_per_article: Макс. связанных статей на результат

        Returns:
            Список обогащенных результатов с графовым контекстом
        """
        enriched_results = []

        for result in hybrid_results:
            text = result.get('text', result.get('document', ''))
            metadata = result.get('metadata', {})

            # Извлекаем информацию о статье (из metadata и текста)
            law_number, article_number = self.extract_article_info(metadata, text)

            hybrid_score = result.get('hybrid_score', result.get('similarity', 0))
            bm25_score = result.get('bm25_score', 0)
            semantic_score = result.get('semantic_score', 0)

            # Получаем связанные статьи из графа
            graph_context = []
            if law_number and article_number:
                graph_context = await self.get_related_articles(
                    law_number=law_number,
                    article_number=article_number,
                    depth=graph_depth,
                    max_related=max_related_per_article
                )

            # Расчет графового score
            graph_score = self.calculate_graph_score(graph_context, hybrid_score)

            # Финальный score = Hybrid score + Graph bonus
            final_score = hybrid_score + graph_score

            enriched_result = GraphEnrichedResult(
                text=text,
                metadata=metadata,
                hybrid_score=hybrid_score,
                bm25_score=bm25_score,
                semantic_score=semantic_score,
                graph_context=graph_context,
                graph_score=graph_score,
                final_score=final_score,
                article_number=article_number,
                law_number=law_number
            )

            enriched_results.append(enriched_result)

        # Пересортировка по final_score
        enriched_results.sort(key=lambda x: x.final_score, reverse=True)

        self.logger.info(
            f"[GRAPH] Enriched {len(enriched_results)} results with graph context. "
            f"Average graph bonus: {sum(r.graph_score for r in enriched_results) / len(enriched_results):.3f}"
        )

        return enriched_results

    async def close(self):
        """
        Закрытие соединения с Neo4j
        Context7 best practice: await driver.close()
        """
        if self.driver:
            await self.driver.close()
            self.logger.info("[GRAPH] Neo4j connection closed")


# Convenience функция для использования в Search Service
async def graph_enhanced_hybrid_search(
    chroma_collection,
    query: str,
    k: int = 5,
    graph_depth: int = 1,
    max_related_per_article: int = 3
) -> List[Dict[str, Any]]:
    """
    Выполняет график-обогащенный гибридный поиск

    Args:
        chroma_collection: ChromaDB коллекция
        query: Поисковый запрос
        k: Количество результатов
        graph_depth: Глубина графового обхода
        max_related_per_article: Макс. связанных статей

    Returns:
        Список обогащенных результатов в dict формате
    """
    # 1. Hybrid BM25+Semantic search
    from core.hybrid_bm25_search import hybrid_search

    hybrid_results = await hybrid_search(
        chroma_collection=chroma_collection,
        query=query,
        k=k
    )

    # 2. Graph enrichment
    graph_searcher = GraphEnhancedHybridSearch()

    try:
        # Подключаемся к Neo4j
        connected = await graph_searcher.connect()

        if not connected:
            logger.warning("[GRAPH] Neo4j unavailable, returning pure hybrid results")
            return hybrid_results

        # Обогащаем результаты графом
        enriched_results = await graph_searcher.enrich_with_graph(
            hybrid_results=hybrid_results,
            graph_depth=graph_depth,
            max_related_per_article=max_related_per_article
        )

        # Конвертируем в dict формат
        final_results = []
        for enriched in enriched_results:
            result_dict = {
                'text': enriched.text,
                'document': enriched.text,
                'metadata': enriched.metadata,
                'similarity': enriched.final_score,
                'hybrid_score': enriched.hybrid_score,
                'bm25_score': enriched.bm25_score,
                'semantic_score': enriched.semantic_score,
                'graph_score': enriched.graph_score,
                'graph_context': enriched.graph_context,
                'law_number': enriched.law_number,
                'article_number': enriched.article_number
            }
            final_results.append(result_dict)

        return final_results

    finally:
        graph_searcher.close()
