"""Post-processing utilities for legal chunks."""

from typing import List

from .definitions import LegalChunk


class ChunkPostProcessor:
    """Adjusts chunk relationships and sizes after segmentation."""

    def __init__(self, min_chunk_size: int, max_chunk_size: int) -> None:
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def establish_relationships(self, chunks: List[LegalChunk]) -> None:
        for index, chunk in enumerate(chunks):
            if index == 0:
                continue

            previous = chunks[index - 1]
            if (
                chunk.structure_metadata.article_number
                and chunk.structure_metadata.article_number
                == previous.structure_metadata.article_number
            ):
                chunk.parent_chunk_id = previous.chunk_id
                previous.child_chunk_ids.append(chunk.chunk_id)

    def optimize_chunk_sizes(self, chunks: List[LegalChunk]) -> List[LegalChunk]:
        optimized: List[LegalChunk] = []
        index = 0

        while index < len(chunks):
            current = chunks[index]

            if (
                len(current.content) < self.min_chunk_size
                and index + 1 < len(chunks)
            ):
                nxt = chunks[index + 1]

                if (
                    current.structure_metadata.article_number
                    and current.structure_metadata.article_number
                    == nxt.structure_metadata.article_number
                ):
                    merged_content = f"{current.content}\n\n{nxt.content}"

                    if len(merged_content) <= self.max_chunk_size:
                        merged_chunk = LegalChunk(
                            content=merged_content,
                            structure_metadata=current.structure_metadata,
                            document_type=current.document_type,
                            legal_domain=current.legal_domain,
                            references=list(set(current.references + nxt.references)),
                            key_terms=list(set(current.key_terms + nxt.key_terms)),
                            start_position=current.start_position,
                            end_position=nxt.end_position,
                            chunk_id=current.chunk_id,
                            parent_chunk_id=current.parent_chunk_id,
                            child_chunk_ids=current.child_chunk_ids + nxt.child_chunk_ids,
                        )
                        optimized.append(merged_chunk)
                        index += 2
                        continue

            optimized.append(current)
            index += 1

        return optimized
