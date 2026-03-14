"""Chunk creation helpers for regulatory documents."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from ..common import TextChunk, logger
from ..errors import ProcessingPipelineError
from .metadata_utils import extract_law_number, is_legal_document


def create_chunks(
    pipeline: "RegulatoryPipeline",
    text: str,
    metadata: Dict[str, Any] | None = None,
) -> List[TextChunk]:
    metadata = metadata or {}

    try:
        from core.advanced_legal_chunker import AdvancedLegalChunker
        from core.specialized_legal_ner import SpecializedLegalNER

        if is_legal_document(text, metadata):
            legal_chunker = AdvancedLegalChunker()
            ner = SpecializedLegalNER()
            law_number = extract_law_number(text, metadata)
            document_id = metadata.get("document_id", str(uuid.uuid4()))

            enhanced_chunks = legal_chunker.chunk_document(text, document_id, law_number)
            ner_results = ner.extract_legal_entities(text)

            text_chunks = []
            for i, chunk in enumerate(enhanced_chunks):
                chunk_metadata = {
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(enhanced_chunks),
                    "chunk_type": chunk.chunk_type,
                    "law_number": law_number,
                    "legal_entities": ner_results.get(str(i), []),
                }

                text_chunks.append(
                    TextChunk(
                        id=chunk.id,
                        text=chunk.text,
                        metadata=chunk_metadata,
                    )
                )

            logger.info(" Создано %s legal chunks с улучшенным анализом", len(text_chunks))
            return text_chunks
    except Exception:
        # Fallback на упрощённый legal-aware chunking по границам статей
        if is_legal_document(text, metadata):
            import re
            law_number = extract_law_number(text, metadata)
            # Находим начала статей: "статья N" (в разных падежах)
            pattern = re.compile(r'(^|\n)\s*стат(?:ья|и|ей)\s+(\d+(?:\.\d+)?)\b', re.IGNORECASE)
            matches = list(pattern.finditer(text))

            chunks: List[TextChunk] = []
            if matches:
                for idx, m in enumerate(matches):
                    start = m.start(0)
                    article_num = m.group(2)
                    end = matches[idx + 1].start(0) if idx + 1 < len(matches) else len(text)
                    chunk_text = text[start:end].strip()
                    if not chunk_text:
                        continue

                    chunk_meta: Dict[str, Any] = {
                        **(metadata or {}),
                        "chunk_index": idx,
                        "chunk_type": "legal_article",
                        "article_number": article_num,
                        "law_number": law_number,
                    }
                    chunks.append(
                        TextChunk(
                            id=str(uuid.uuid4()),
                            text=chunk_text,
                            metadata=chunk_meta,
                        )
                    )

                logger.info(" Создано %s legal-aware article chunks", len(chunks))
                return chunks

        chunks = pipeline.text_splitter.split_text(text)
        text_chunks = [
            TextChunk(
                id=str(uuid.uuid4()),
                text=chunk_text,
                metadata={
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "chunk_type": "text",
                },
            )
            for i, chunk_text in enumerate(chunks)
        ]

        logger.info(" Создано %s текстовых чанков", len(text_chunks))
        return text_chunks

    except Exception as exc:
        logger.error(" Ошибка создания чанков: %s", exc)
        raise ProcessingPipelineError(f"Chunk creation failed: {exc}") from exc


__all__ = ["create_chunks"]
