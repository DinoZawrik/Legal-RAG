#!/usr/bin/env python3
"""
Document Reranker для улучшения качества retrieval

Supports:
- BGE Reranker v2-m3 (open-source, бесплатный)
- Cross-encoder architecture для точного scoring
- Russian language support

Usage:
    from core.reranker import get_reranker

    reranker = get_reranker()
    reranked = await reranker.rerank(
        query="Что такое плата концедента?",
        documents=hybrid_search_results,
        top_k=5
    )
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class RerankedDocument:
    """Document with reranking score."""
    text: str
    metadata: Dict[str, Any]
    original_score: float # Hybrid BM25 score
    rerank_score: float # Cross-encoder score
    final_score: float # Combined score
    doc_id: str
    rank: int # Position in reranked list


class BaseReranker:
    """Base class for rerankers."""

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        combine_weight: float = 0.6 # Weight for rerank_score (vs original_score)
    ) -> List[RerankedDocument]:
        """
        Rerank documents using cross-encoder.

        Args:
            query: User query
            documents: List of documents from hybrid search
            top_k: Number of top results to return
            combine_weight: Weight for rerank score (0.6 = 60% rerank, 40% original)

        Returns:
            List of RerankedDocument sorted by final_score
        """
        raise NotImplementedError


class BGEReranker(BaseReranker):
    """
    BGE Reranker v2-m3 (BAAI)

    Open-source, Apache 2.0 license
    ~600M parameters, runs on CPU
    Multilingual (including Russian)

    Installation:
        pip install sentence-transformers
        # Model auto-downloads on first use

    Model: BAAI/bge-reranker-v2-m3
    """

    def __init__(self):
        self.model = None
        self._model_name = "BAAI/bge-reranker-v2-m3"
        self._initialized = False

    def _lazy_load_model(self):
        """Lazy load model on first use (избегаем загрузки если reranker не используется)."""
        if self._initialized:
            return

        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"Loading BGE Reranker model: {self._model_name}...")
            # WARNING: This might trigger a large download (~1GB)
            logger.warning(f"Downloading/Loading heavy model ({self._model_name}). This may take a while on first run.")
            
            self.model = CrossEncoder(self._model_name, max_length=512)
            self._initialized = True
            logger.info("[OK] BGE Reranker loaded successfully")

        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to load BGE Reranker: {e}")
            raise

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        combine_weight: float = 0.6
    ) -> List[RerankedDocument]:
        """
        Rerank using BGE cross-encoder.

        Process:
        1. Prepare (query, document) pairs
        2. Score all pairs with cross-encoder
        3. Combine with original scores
        4. Sort and return top_k
        """
        # Lazy load model
        self._lazy_load_model()

        if not documents:
            return []

        # Limit input to top 20 candidates (для скорости)
        candidates = documents[:20]

        logger.info(f"[BGE-RERANK] Reranking {len(candidates)} documents for query: '{query[:50]}...'")

        # 1. Prepare (query, document) pairs
        pairs = []
        for doc in candidates:
            # INCREASED TRUNCATION: 500 -> 4000 chars for legal documents
            text = doc.get("text", "")[:4000] 
            pairs.append([query, text])

        # 2. Score with cross-encoder (CPU intensive, run in thread pool)
        loop = asyncio.get_event_loop()
        rerank_scores = await loop.run_in_executor(
            None,
            lambda: self.model.predict(pairs, show_progress_bar=False)
        )

        # Convert to list if numpy array
        if hasattr(rerank_scores, 'tolist'):
            rerank_scores = rerank_scores.tolist()

        # 3. Combine scores
        reranked_docs = []

        for i, doc in enumerate(candidates):
            original_score = doc.get("hybrid_score") or doc.get("semantic_score") or 0.0
            rerank_score = float(rerank_scores[i])

            # Normalize rerank_score to [0, 1] (BGE reranker outputs ~[-10, 10])
            # Use sigmoid for normalization
            import math
            normalized_rerank = 1 / (1 + math.exp(-rerank_score))

            # Combine scores (weighted average)
            final_score = (
                combine_weight * normalized_rerank +
                (1 - combine_weight) * original_score
            )

            reranked_docs.append(RerankedDocument(
                text=doc.get("text", ""),
                metadata=doc.get("metadata", {}),
                original_score=original_score,
                rerank_score=normalized_rerank,
                final_score=final_score,
                doc_id=doc.get("id") or doc.get("doc_id", f"doc_{i}"),
                rank=0 # Will be set after sorting
            ))

        # 4. Sort by final_score
        reranked_docs.sort(key=lambda x: x.final_score, reverse=True)

        # Set ranks
        for rank, doc in enumerate(reranked_docs[:top_k], 1):
            doc.rank = rank

        # Log top-3
        logger.info(f"[BGE-RERANK] Top-3 results:")
        for i, doc in enumerate(reranked_docs[:3], 1):
            law = doc.metadata.get('law', 'N/A')
            article = doc.metadata.get('article', 'N/A')
            logger.info(
                f" {i}. Final={doc.final_score:.3f} "
                f"(Original={doc.original_score:.3f}, Rerank={doc.rerank_score:.3f}) "
                f"Law={law}, Article={article}"
            )

        return reranked_docs[:top_k]


class NoOpReranker(BaseReranker):
    """
    No-op reranker (passthrough).

    Используется как fallback если reranker не нужен или недоступен.
    """

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        combine_weight: float = 0.6
    ) -> List[RerankedDocument]:
        """Return documents as-is with original scores."""
        logger.info(f"[NO-OP-RERANK] Passthrough reranking for {len(documents)} documents")

        result = []
        for i, doc in enumerate(documents[:top_k], 1):
            original_score = doc.get("hybrid_score") or doc.get("semantic_score") or 0.0
            result.append(RerankedDocument(
                text=doc.get("text", ""),
                metadata=doc.get("metadata", {}),
                original_score=original_score,
                rerank_score=original_score, # Same as original
                final_score=original_score,
                doc_id=doc.get("id") or doc.get("doc_id", f"doc_{i}"),
                rank=i
            ))

        return result


# Factory function
_global_reranker = None


def get_reranker(
    reranker_type: str = "bge",
    use_reranker: bool = True
) -> BaseReranker:
    """
    Get reranker instance (singleton).

    Args:
        reranker_type: "bge" or "noop"
        use_reranker: Enable/disable reranking globally

    Returns:
        Reranker instance
    """
    global _global_reranker

    if not use_reranker:
        return NoOpReranker()

    if _global_reranker is None:
        if reranker_type == "bge":
            _global_reranker = BGEReranker()
        else:
            _global_reranker = NoOpReranker()

    return _global_reranker


def convert_to_dict(reranked_docs: List[RerankedDocument]) -> List[Dict[str, Any]]:
    """
    Convert RerankedDocument list to dict format (для совместимости с существующим кодом).

    Returns:
        List of dicts with keys: text, metadata, similarity, id, rerank_score, final_score
    """
    return [
        {
            'text': doc.text,
            'metadata': doc.metadata,
            'similarity': doc.final_score, # Use final_score as similarity
            'id': doc.doc_id,
            'original_score': doc.original_score,
            'rerank_score': doc.rerank_score,
            'final_score': doc.final_score,
            'rank': doc.rank
        }
        for doc in reranked_docs
    ]
