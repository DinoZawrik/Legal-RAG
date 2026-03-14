#!/usr/bin/env python3
"""
Hybrid BM25 + Semantic Search для компенсации низких Gemini similarity scores

ПРОБЛЕМА: Google Gemini embeddings дают similarity 0.1-0.5 для русского юридического языка
РЕШЕНИЕ: BM25 (keyword) + Semantic (meaning) = Hybrid scoring

Преимущества BM25 для юридических текстов:
- Точные термины: "плата концедента" встречается только в нужных статьях
- IDF компенсирует частые слова: "договор", "соглашение" получают низкий вес
- Exact match: Если пользователь спрашивает "плата концедента", BM25 найдет это точно

Ожидаемое улучшение: 40-50% (с 2/10 до 6/10 правильных ответов)
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
import re
from dataclasses import dataclass
from google import genai

from core.gemini_rate_limiter import GeminiRateLimiter

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """Результат гибридного поиска с scores"""
    text: str
    metadata: Dict[str, Any]
    bm25_score: float
    semantic_score: float
    hybrid_score: float
    doc_id: str


class LegalTokenizer:
    """
    Токенизатор для русских юридических текстов
    """

    # Юридические термины для сохранения целостности (расширено до 100+)
    LEGAL_TERMS = [
        # Базовые определения
        'концессионное соглашение',
        'плата концедента',
        'объект концессионного соглашения',
        'концедент',
        'концессионер',
        'конкурсная документация',
        'концессия',
        'имущество концедента',
        'право собственности концедента',
        'концессионная плата',
        'финансовое участие',

        # ГЧП и инфраструктурные модели
        'государственно-частное партнерство',
        'соглашение о гчп',
        'соглашение о государственно-частном партнерстве',
        'частный партнер',
        'публичный партнер',
        'объект соглашения',
        'сторона соглашения',

        # Процедуры и действия
        'досрочное расторжение',
        'досрочное прекращение',
        'замена концессионера',
        'замена партнера',
        'передача прав',
        'передача обязательств',
        'уступка прав',
        'конкурсный отбор',
        'конкурсное предложение',
        'проведение конкурса',
        'заключение соглашения',
        'расторжение соглашения',
        'прекращение соглашения',
        'изменение условий',

        # Права и обязанности
        'право собственности',
        'право владения',
        'право пользования',
        'право распоряжения',
        'залоговые права',
        'передача в залог',
        'обременение залогом',
        'имущественные права',
        'неимущественные права',

        # Финансовые термины
        'финансирование проекта',
        'инвестиционные обязательства',
        'капитальные вложения',
        'эксплуатационные расходы',
        'возмещение затрат',
        'платежи концессионера',
        'платежи частного партнера',
        'минимальный размер',
        'максимальный размер',

        # Объекты и имущество
        'объекты теплоснабжения',
        'объекты водоснабжения',
        'объекты транспорта',
        'объекты здравоохранения',
        'объекты образования',
        'объекты культуры',
        'объекты спорта',
        'земельный участок',
        'земельные участки',
        'недвижимое имущество',
        'движимое имущество',

        # Сроки и периоды
        'срок действия',
        'срок соглашения',
        'минимальный срок',
        'максимальный срок',
        'период эксплуатации',
        'период строительства',
        'срок окупаемости',

        # Гарантии и обеспечение
        'государственные гарантии',
        'обеспечение обязательств',
        'банковская гарантия',
        'страхование рисков',

        # Требования и критерии
        'требования к концессионеру',
        'требования к партнеру',
        'квалификационные требования',
        'финансовые требования',
        'технические требования',
        'критерии отбора',
        'критерии оценки',

        # Органы и стороны
        'уполномоченный орган',
        'федеральный орган',
        'исполнительный орган',
        'орган местного самоуправления',
        'российская федерация',
        'субъект российской федерации',
        'муниципальное образование',

        # Документы и процедуры
        'технико-экономическое обоснование',
        'проектная документация',
        'конкурсная документация',
        'инвестиционная программа',
        'бизнес-план',
        'технический проект',

        # Контроль и надзор
        'контроль за исполнением',
        'надзор за деятельностью',
        'мониторинг реализации',
        'оценка эффективности',
        'проверка соблюдения',

        # Синонимы и вариации
        'гчп соглашение',
        'соглашение гчп',
        'концедентская плата',
        'плата от концессионера',
    ]

    def tokenize(self, text: str) -> List[str]:
        """
        Токенизация с сохранением юридических терминов

        Пример:
        "плата концедента по Федеральному закону 123-ФЗ" ["плата концедента", "123-фз"]
        (а не ["плата", "концедента", "по", "115", "фз"])
        """
        text_lower = text.lower()

        # 1. Заменяем юридические термины на placeholders
        term_map = {}
        for i, term in enumerate(self.LEGAL_TERMS):
            if term in text_lower:
                placeholder = f"__LEGAL_TERM_{i}__"
                text_lower = text_lower.replace(term, placeholder)
                term_map[placeholder] = term

        # 2. Сохраняем номера законов (формат "123-ФЗ" и вариации)
        law_pattern = r'\d+-?\s?фз'
        laws = re.findall(law_pattern, text_lower)
        for i, law in enumerate(laws):
            placeholder = f"__LAW_{i}__"
            text_lower = text_lower.replace(law, placeholder)
            term_map[placeholder] = law.replace(' ', '')

        # 3. Сохраняем номера статей (статья 3, статья 7)
        article_pattern = r'статья\s+\d+\.?\d*'
        articles = re.findall(article_pattern, text_lower)
        for i, article in enumerate(articles):
            placeholder = f"__ARTICLE_{i}__"
            text_lower = text_lower.replace(article, placeholder)
            term_map[placeholder] = article.replace(' ', '_')

        # 4. Простая токенизация по пробелам
        tokens = text_lower.split()

        # 5. Восстанавливаем placeholders
        final_tokens = []
        for token in tokens:
            if token in term_map:
                final_tokens.append(term_map[token])
            elif len(token) > 2: # Убираем короткие слова (по, в, и, etc.)
                # Убираем пунктуацию
                token_clean = re.sub(r'[^\w-]', '', token)
                if token_clean:
                    final_tokens.append(token_clean)

        return final_tokens


async def hybrid_search(
    chroma_collection,
    query: str,
    k: int = 5,
    bm25_weight: float = 0.5,
    semantic_weight: float = 0.5,
) -> List[HybridSearchResult]:
    searcher = HybridBM25Search(chroma_collection)
    await searcher.initialize()
    return await searcher.search(query, k=k, bm25_weight=bm25_weight, semantic_weight=semantic_weight)


class HybridBM25Search:
    """
    Гибридный поиск: BM25 (keyword matching) + Semantic (cosine similarity)

    Использование:
    ```python
    searcher = HybridBM25Search(chromadb_collection)
    await searcher.initialize()

    results = await searcher.search("Что такое плата концедента?", k=5)
    # Результат: hybrid_score ~0.65 (вместо 0.156 от чистого semantic)
    ```
    """

    def __init__(self, chromadb_collection):
        self.chroma = chromadb_collection
        self.tokenizer = LegalTokenizer()

        # Будут инициализированы в initialize()
        self.bm25 = None
        self.documents = []
        self.metadatas = []
        self.ids = []
        self.doc_id_to_index = {}

        self.logger = logging.getLogger(self.__class__.__name__)

    async def initialize(self):
        """
        Инициализация BM25 индекса

        ВАЖНО: Вызвать один раз при старте!
        """
        try:
            self.logger.info("Initializing Hybrid BM25 Search...")

            # Загружаем документы из ChromaDB пакетами для ограничения памяти
            BATCH_SIZE = 2000
            offset = 0
            self.documents = []
            self.metadatas = []
            self.ids = []

            while True:
                batch = await self.chroma.get(limit=BATCH_SIZE, offset=offset)
                if not batch or not batch.get('ids'):
                    break
                batch_ids = batch['ids']
                if not batch_ids:
                    break
                self.ids.extend(batch_ids)
                self.documents.extend(batch.get('documents', []))
                self.metadatas.extend(batch.get('metadatas', []))
                if len(batch_ids) < BATCH_SIZE:
                    break
                offset += BATCH_SIZE

            if not self.documents:
                raise ValueError("ChromaDB collection is empty!")

            # Создаем mapping doc_id -> index
            self.doc_id_to_index = {doc_id: i for i, doc_id in enumerate(self.ids)}

            # Токенизируем все документы для BM25
            self.logger.info(f"Tokenizing {len(self.documents)} documents for BM25...")
            tokenized_docs = [self.tokenizer.tokenize(doc) for doc in self.documents]

            # Строим BM25 индекс с оптимизированными параметрами
            # k1=1.5 (было 1.2): больше влияния частоты термина для юридических текстов
            # b=0.8 (было 0.75): больше влияния длины документа
            # Эти параметры лучше подходят для Russian legal text
            self.bm25 = BM25Okapi(tokenized_docs, k1=1.5, b=0.8)

            self.logger.info(f"[OK] BM25 index built: {len(self.documents)} documents")

        except Exception as e:
            self.logger.error(f"[ERROR] Failed to initialize BM25: {e}")
            raise

    def _normalize_scores(self, scores: List[float]) -> np.ndarray:
        """
        Нормализация scores в диапазон [0, 1]
        """
        scores_array = np.array(scores, dtype=np.float32)

        if len(scores_array) == 0:
            return scores_array

        min_score = scores_array.min()
        max_score = scores_array.max()

        if max_score == min_score:
            return np.zeros_like(scores_array, dtype=np.float32)

        normalized = (scores_array - min_score) / (max_score - min_score)
        return normalized.astype(np.float32)

    async def search(
        self,
        query: str,
        k: int = 5,
        bm25_weight: float = 0.5,
        semantic_weight: float = 0.5
    ) -> List[HybridSearchResult]:
        """
        Гибридный поиск: BM25 + Semantic

        Args:
            query: Запрос пользователя
            k: Количество результатов
            bm25_weight: Вес BM25 (default: 0.5 - точный поиск терминов)
            semantic_weight: Вес Semantic (default: 0.5 - смысловая близость)

        Returns:
            Список HybridSearchResult отсортированный по hybrid_score
        """
        if not self.bm25:
            raise RuntimeError("BM25 not initialized! Call initialize() first.")

        self.logger.info(f"[HYBRID SEARCH] Query: '{query[:100]}...'")

        # 1. BM25 scores для всех документов
        tokenized_query = self.tokenizer.tokenize(query)
        self.logger.info(f"[BM25] Tokenized query: {tokenized_query}")

        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_normalized = self._normalize_scores(bm25_scores)

        top_bm25_idx = np.argsort(bm25_scores)[-3:][::-1]
        self.logger.info(f"[BM25] Top-3 scores: {[bm25_scores[i] for i in top_bm25_idx]}")

        # 2. Semantic scores из ChromaDB
        # Создаем Gemini embedding вручную (384-dim) вместо использования collection.query()
        try:
            from core.api_key_manager import get_key_manager
            key_manager = get_key_manager()
            api_key = key_manager.get_next_key()

            if not api_key:
                self.logger.warning("No Gemini/Google API key found, falling back to default embeddings")
                raise ValueError("No API key")

            await GeminiRateLimiter.wait("flash")
            client = genai.Client(api_key=api_key)

            embedding_result = client.models.embed_content(
                model='text-embedding-004',
                contents=query,
            )
            query_embedding = None
            if embedding_result is not None:
                if hasattr(embedding_result, 'embeddings') and embedding_result.embeddings:
                    first = embedding_result.embeddings[0]
                    if hasattr(first, 'values') and first.values is not None:
                        query_embedding = list(first.values)
                elif isinstance(embedding_result, dict):
                    if 'embeddings' in embedding_result and embedding_result['embeddings']:
                        first = embedding_result['embeddings'][0]
                        if isinstance(first, dict) and 'values' in first:
                            query_embedding = first['values']
                    elif 'embedding' in embedding_result:
                        query_embedding = embedding_result['embedding']

            if not query_embedding:
                raise ValueError("No embedding values returned")

            # Query ChromaDB with manual embedding
            semantic_results = await self.chroma.query(
                query_embeddings=[query_embedding],
                n_results=min(k * 10, 50)
            )
        except Exception as e:
            from core.api_key_manager import get_key_manager
            get_key_manager().report_error(api_key if 'api_key' in locals() else '', is_quota_error="quota" in str(e).lower() or "429" in str(e))
            self.logger.error(f"Failed to create Gemini embedding: {e}")
            # Fallback: use default embeddings if Gemini fails
            # Жесткая деградация: отключаем семантическую часть вовсе, чтобы избежать
            # несовпадения размерности эмбеддингов коллекции при client-side embed
            self.logger.warning("[SEMANTIC-FALLBACK] Disabling semantic component due to embedding errors; using BM25 only")
            semantic_results = {"ids": [[]], "distances": [[]]}

        # Создаем mapping semantic doc_id -> similarity
        semantic_scores_map = {}
        if semantic_results and semantic_results['ids'] and semantic_results['ids'][0]:
            for i, doc_id in enumerate(semantic_results['ids'][0]):
                distance = semantic_results['distances'][0][i]
                similarity = 1 - distance # ChromaDB возвращает distance, конвертируем в similarity
                semantic_scores_map[doc_id] = similarity

        self.logger.info(f"[SEMANTIC] Retrieved {len(semantic_scores_map)} results")
        if semantic_scores_map:
            top_semantic = sorted(semantic_scores_map.items(), key=lambda x: x[1], reverse=True)[:3]
            self.logger.info(f"[SEMANTIC] Top-3 similarities: {[s for _, s in top_semantic]}")

        # 3. Hybrid scoring для каждого документа
        hybrid_scores = []

        for i, doc_id in enumerate(self.ids):
            # BM25 score (normalized)
            bm25_score = float(bm25_normalized[i])

            # Semantic score (из ChromaDB или 0 если не найден)
            semantic_score = semantic_scores_map.get(doc_id, 0.0)

            # Hybrid score: max-based formula
            # Не наказываем документы, которые сильны по одной оси
            # max обеспечивает базовый score, бонус за совпадение обеих осей
            major = max(bm25_score, semantic_score)
            minor = min(bm25_score, semantic_score)
            hybrid_score = major + 0.3 * minor

            hybrid_scores.append(HybridSearchResult(
                text=self.documents[i],
                metadata=self.metadatas[i],
                bm25_score=bm25_score,
                semantic_score=semantic_score,
                hybrid_score=hybrid_score,
                doc_id=doc_id
            ))

        # 4. Сортируем по hybrid_score и берем TOP-K
        hybrid_scores.sort(key=lambda x: x.hybrid_score, reverse=True)
        top_k_results = hybrid_scores[:k]

        # Логируем TOP-3
        self.logger.info(f"[HYBRID] TOP-{k} results:")
        for i, result in enumerate(top_k_results[:3], 1):
            law = result.metadata.get('law', 'N/A')
            article = result.metadata.get('article', 'N/A')
            self.logger.info(
                f" {i}. Hybrid={result.hybrid_score:.3f} "
                f"(BM25={result.bm25_score:.3f}, Semantic={result.semantic_score:.3f}) "
                f"Law={law}, Article={article}"
            )

        return top_k_results

    def convert_to_dict(self, results: List[HybridSearchResult]) -> List[Dict[str, Any]]:
        """
        Конвертация HybridSearchResult в dict для совместимости с существующим кодом
        """
        return [
            {
                'text': r.text,
                'metadata': r.metadata,
                'similarity': r.hybrid_score, # Используем hybrid_score как similarity
                'id': r.doc_id,
                'bm25_score': r.bm25_score,
                'semantic_score': r.semantic_score,
                'hybrid_score': r.hybrid_score
            }
            for r in results
        ]
