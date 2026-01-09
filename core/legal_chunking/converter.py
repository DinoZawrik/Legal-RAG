"""Conversion helpers between legal chunks and generic text chunks."""

from typing import List

from ..infrastructure_suite import TextChunk
from .definitions import LegalChunk


def legal_chunks_to_text_chunks(legal_chunks: List[LegalChunk]) -> List[TextChunk]:
    text_chunks: List[TextChunk] = []

    for chunk in legal_chunks:
        metadata = {
            "document_type": chunk.document_type.value,
            "legal_domain": chunk.legal_domain.value,
            "structure_level": chunk.structure_metadata.structure_level.value,
            "article_number": chunk.structure_metadata.article_number,
            "hierarchy_path": chunk.structure_metadata.hierarchy_path,
            "references": chunk.references,
            "key_terms": chunk.key_terms,
            "chunk_id": chunk.chunk_id,
        }

        text_chunks.append(
            TextChunk(
                content=chunk.content,
                metadata=metadata,
                start_position=chunk.start_position,
                end_position=chunk.end_position,
            )
        )

    return text_chunks
