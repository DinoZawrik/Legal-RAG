"""Smart chunk construction and validation utilities."""

from __future__ import annotations

import logging
from typing import Iterable, List, Sequence

from ..infrastructure_suite import TextChunk
from ..universal_legal_ner import UniversalLegalEntities
from .definitions import ChunkBoundary, ChunkPriority, ProtectedZone, SmartChunk

logger = logging.getLogger(__name__)


class SmartChunkBuilder:
    """Creates, validates and converts smart chunks."""

    def __init__(
        self,
        min_chunk_size: int,
        max_chunk_size: int,
        overlap_size: int,
        base_chunk_size: int,
    ) -> None:
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.base_chunk_size = base_chunk_size

    def create_smart_chunks(
        self,
        text: str,
        boundaries: Sequence[ChunkBoundary],
        entities: UniversalLegalEntities,
        protected_zones: Sequence[ProtectedZone],
    ) -> List[SmartChunk]:
        chunks: List[SmartChunk] = []

        for i in range(len(boundaries) - 1):
            start_pos = boundaries[i].position
            end_pos = boundaries[i + 1].position
            chunk_text = text[start_pos:end_pos].strip()

            if len(chunk_text) < self.min_chunk_size and i < len(boundaries) - 2:
                continue

            chunk_entities = self._extract_chunk_entities(entities, start_pos, end_pos)
            chunk_protected = [
                zone
                for zone in protected_zones
                if not (zone.end_pos < start_pos or zone.start_pos > end_pos)
            ]

            priority = self._calculate_chunk_priority(chunk_entities)
            criticality = self._calculate_chunk_criticality(chunk_entities, chunk_protected)
            boundary_quality = (
                boundaries[i].quality_score + boundaries[i + 1].quality_score
            ) / 2

            chunks.append(
                SmartChunk(
                    content=chunk_text,
                    start_pos=start_pos,
                    end_pos=end_pos,
                    chunk_index=len(chunks),
                    entities=chunk_entities,
                    priority=priority,
                    criticality_score=criticality,
                    protected_zones=chunk_protected,
                    boundary_quality=boundary_quality,
                    metadata={
                        "entity_count": len(chunk_entities.get_all_entities()),
                        "has_numerical_constraints": bool(chunk_entities.numerical_constraints),
                        "has_definitions": bool(chunk_entities.definitions),
                        "protected_zones_count": len(chunk_protected),
                        "chunk_size": len(chunk_text),
                    },
                )
            )

        return chunks

    def add_chunk_overlaps(self, text: str, chunks: Sequence[SmartChunk]) -> List[SmartChunk]:
        for i in range(len(chunks) - 1):
            current = chunks[i]
            nxt = chunks[i + 1]

            overlap_start = max(0, current.end_pos - self.overlap_size)
            overlap_end = min(len(text), nxt.start_pos + self.overlap_size)

            if overlap_start < current.end_pos:
                current.next_chunk_overlap = text[overlap_start:current.end_pos]

            if overlap_end > nxt.start_pos:
                nxt.previous_chunk_overlap = text[nxt.start_pos:overlap_end]

        return list(chunks)

    def validate_chunking_quality(
        self,
        chunks: Sequence[SmartChunk],
        protected_zones: Sequence[ProtectedZone],
    ) -> None:
        issues: List[str] = []

        for zone in protected_zones:
            if not any(chunk.start_pos <= zone.start_pos and chunk.end_pos >= zone.end_pos for chunk in chunks):
                issues.append(f"Защищенная зона нарушена: {zone.reason}")

        for chunk in chunks:
            length = len(chunk.content)
            if length < self.min_chunk_size:
                issues.append(f"Чанк {chunk.chunk_index} слишком маленький: {length} символов")
            elif length > self.max_chunk_size:
                issues.append(f"Чанк {chunk.chunk_index} слишком большой: {length} символов")

        for i in range(len(chunks) - 1):
            current_end = chunks[i].end_pos
            next_start = chunks[i + 1].start_pos
            if next_start > current_end + 10:
                issues.append(
                    f"Пропуск текста между чанками {i} и {i + 1}: {next_start - current_end} символов"
                )

        if issues:
            logger.warning(" Найдены проблемы качества чанкинга: %s", "; ".join(issues))
        else:
            logger.info(" Валидация чанкинга прошла успешно")

    def fallback_chunking(self, text: str) -> List[SmartChunk]:
        logger.warning(" Использование fallback чанкинга")
        chunks: List[SmartChunk] = []

        for index, start in enumerate(range(0, len(text), self.base_chunk_size)):
            chunk_text = text[start : start + self.base_chunk_size]
            chunks.append(
                SmartChunk(
                    content=chunk_text,
                    start_pos=start,
                    end_pos=start + len(chunk_text),
                    chunk_index=index,
                    entities=UniversalLegalEntities(),
                    priority=ChunkPriority.NORMAL,
                    criticality_score=0.5,
                    protected_zones=[],
                    boundary_quality=0.5,
                    metadata={"fallback": True},
                )
            )

        return chunks

    def convert_to_text_chunks(self, smart_chunks: Iterable[SmartChunk]) -> List[TextChunk]:
        text_chunks: List[TextChunk] = []

        for smart_chunk in smart_chunks:
            metadata = dict(smart_chunk.metadata)
            metadata.update(
                {
                    "chunk_priority": smart_chunk.priority.value,
                    "criticality_score": smart_chunk.criticality_score,
                    "boundary_quality": smart_chunk.boundary_quality,
                    "protected_zones_count": len(smart_chunk.protected_zones),
                    "entity_types_present": list(
                        {
                            entity.entity_type.value
                            for entity in smart_chunk.entities.get_all_entities()
                        }
                    ),
                    "search_boost_factor": self._calculate_search_boost(smart_chunk),
                    "context_preservation_required": smart_chunk.priority
                    in {ChunkPriority.CRITICAL, ChunkPriority.HIGH},
                }
            )

            if smart_chunk.entities.numerical_constraints:
                metadata["numerical_constraints"] = [
                    {
                        "type": constraint.constraint_type.value,
                        "value": constraint.value,
                        "unit": constraint.unit,
                        "operator": constraint.operator,
                        "subject": constraint.subject,
                    }
                    for constraint in smart_chunk.entities.numerical_constraints
                ]

            if smart_chunk.entities.definitions:
                metadata["definitions"] = [
                    {
                        "term": definition.metadata.get("term", ""),
                        "definition": definition.metadata.get("definition", ""),
                    }
                    for definition in smart_chunk.entities.definitions
                ]

            content = smart_chunk.content
            if smart_chunk.previous_chunk_overlap:
                content = (
                    f"[ПРЕДЫДУЩИЙ КОНТЕКСТ]: {smart_chunk.previous_chunk_overlap}\n\n" f"{content}"
                )
            if smart_chunk.next_chunk_overlap:
                content = f"{content}\n\n[СЛЕДУЮЩИЙ КОНТЕКСТ]: {smart_chunk.next_chunk_overlap}"

            text_chunks.append(
                TextChunk(
                    content=content,
                    metadata=metadata,
                    start_position=smart_chunk.start_pos,
                    end_position=smart_chunk.end_pos,
                )
            )

        return text_chunks

    def _extract_chunk_entities(
        self,
        all_entities: UniversalLegalEntities,
        start_pos: int,
        end_pos: int,
    ) -> UniversalLegalEntities:
        chunk_entities = UniversalLegalEntities()

        chunk_entities.numerical_constraints = [
            entity
            for entity in all_entities.numerical_constraints
            if start_pos <= entity.start_pos < end_pos
        ]

        chunk_entities.authority_modals = [
            entity
            for entity in all_entities.authority_modals
            if start_pos <= entity.start_pos < end_pos
        ]

        chunk_entities.procedure_steps = [
            entity
            for entity in all_entities.procedure_steps
            if start_pos <= entity.start_pos < end_pos
        ]

        chunk_entities.document_references = [
            entity
            for entity in all_entities.document_references
            if start_pos <= entity.start_pos < end_pos
        ]

        chunk_entities.definitions = [
            entity
            for entity in all_entities.definitions
            if start_pos <= entity.start_pos < end_pos
        ]

        chunk_entities.conditions = [
            entity
            for entity in all_entities.conditions
            if start_pos <= entity.start_pos < end_pos
        ]

        return chunk_entities

    def _calculate_chunk_priority(self, entities: UniversalLegalEntities) -> ChunkPriority:
        if entities.numerical_constraints or entities.definitions:
            return ChunkPriority.CRITICAL
        if entities.procedure_steps or entities.authority_modals:
            return ChunkPriority.HIGH
        if entities.document_references or entities.conditions:
            return ChunkPriority.NORMAL
        return ChunkPriority.LOW

    def _calculate_chunk_criticality(
        self,
        entities: UniversalLegalEntities,
        protected_zones: Sequence[ProtectedZone],
    ) -> float:
        criticality = 0.0
        criticality += len(entities.numerical_constraints) * 0.4
        criticality += len(entities.definitions) * 0.3
        criticality += len(entities.procedure_steps) * 0.2
        criticality += len(entities.authority_modals) * 0.15
        criticality += len(entities.document_references) * 0.1
        criticality += len(entities.conditions) * 0.05
        for zone in protected_zones:
            criticality += zone.criticality * 0.1
        return min(criticality, 1.0)

    def _calculate_search_boost(self, smart_chunk: SmartChunk) -> float:
        boost = 1.0
        boost *= {
            ChunkPriority.CRITICAL: 1.5,
            ChunkPriority.HIGH: 1.3,
            ChunkPriority.NORMAL: 1.0,
            ChunkPriority.LOW: 0.8,
        }.get(smart_chunk.priority, 1.0)
        boost *= 1.0 + smart_chunk.criticality_score * 0.3
        boost *= 1.0 + smart_chunk.boundary_quality * 0.1
        return round(boost, 2)
