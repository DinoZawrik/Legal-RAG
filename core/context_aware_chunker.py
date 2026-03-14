#!/usr/bin/env python3
"""Context-aware chunker orchestrator preserving legal context integrity."""

import logging
from typing import Any, Dict, List, Optional

from .context_chunker import (
    BoundaryOptimizer,
    ChunkBoundary,
    ChunkPriority,
    ProtectedZone,
    ProtectedZoneAnalyzer,
    SmartChunk,
    SmartChunkBuilder,
    default_boundary_patterns,
)
from .infrastructure_suite import TextChunk
# MIGRATED: deprecated wrapper
from .ner import UniversalLegalNER

def get_universal_legal_ner():
    """Legacy compatibility."""
    return UniversalLegalNER()

logger = logging.getLogger(__name__)

__all__ = [
    "ContextAwareChunker",
    "get_context_aware_chunker",
    "ChunkPriority",
    "ChunkBoundary",
    "ProtectedZone",
    "SmartChunk",
]


class ContextAwareChunker:
    """Высокоуровневый оркестратор умного чанкинга правовых документов."""

    def __init__(
        self,
        base_chunk_size: int = 1000,
        min_chunk_size: int = 200,
        max_chunk_size: int = 2500,
        overlap_size: int = 150,
        protection_margin: int = 100,
    ) -> None:
        self.base_chunk_size = base_chunk_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.protection_margin = protection_margin

        self.ner_engine = get_universal_legal_ner()
        self.natural_boundaries = default_boundary_patterns()
        self.zone_analyzer = ProtectedZoneAnalyzer(protection_margin)
        self.boundary_optimizer = BoundaryOptimizer(
            base_chunk_size=base_chunk_size,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
            natural_boundaries=self.natural_boundaries,
        )
        self.chunk_builder = SmartChunkBuilder(
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
            overlap_size=overlap_size,
            base_chunk_size=base_chunk_size,
        )

        logger.info(" Context-Aware Universal Chunker инициализирован")

    def chunk_document(
        self,
        text: str,
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SmartChunk]:
        logger.info(" Начало умного чанкинга документа длиной %s символов", len(text))

        try:
            entities = self.ner_engine.extract_entities(text, document_metadata)
            logger.info(" Извлечено %s правовых сущностей", len(entities.get_all_entities()))

            protected_zones = self.zone_analyzer.identify_protected_zones(text, entities)
            logger.info(" Определено %s защищенных зон", len(protected_zones))

            boundaries = self.boundary_optimizer.find_optimal_boundaries(text, protected_zones)
            logger.info(" Найдено %s оптимальных границ", len(boundaries))

            chunks = self.chunk_builder.create_smart_chunks(text, boundaries, entities, protected_zones)
            logger.info(" Создано %s умных чанков", len(chunks))

            chunks = self.chunk_builder.add_chunk_overlaps(text, chunks)
            self.chunk_builder.validate_chunking_quality(chunks, protected_zones)

            logger.info(" Умный чанкинг завершен: %s чанков", len(chunks))
            return chunks

        except Exception as exc: # noqa: BLE001
            logger.error(" Ошибка умного чанкинга: %s", exc)
            return self.chunk_builder.fallback_chunking(text)

    def convert_to_text_chunks(self, smart_chunks: List[SmartChunk]) -> List[TextChunk]:
        return self.chunk_builder.convert_to_text_chunks(smart_chunks)


_context_aware_chunker: Optional[ContextAwareChunker] = None


def get_context_aware_chunker() -> ContextAwareChunker:
    """Получение глобального экземпляра Context-Aware Chunker."""

    global _context_aware_chunker
    if _context_aware_chunker is None:
        _context_aware_chunker = ContextAwareChunker()
    return _context_aware_chunker


if __name__ == "__main__":
    print(" Context-Aware Universal Chunker - Демонстрация")
    print("=" * 60)

    chunker = ContextAwareChunker()

    demo_text = """
    Статья 10.1. Капитальный грант и плата концедента

    1. Размер капитального гранта не может превышать восемьдесят процентов расходов на создание объекта концессионного соглашения.

    2. Срок действия концессионного соглашения составляет не менее трех лет с даты его заключения.

    3. Концессионер обязан:
    а) обеспечить создание и (или) реконструкцию объекта концессионного соглашения;
    б) обеспечить эксплуатацию объекта концессионного соглашения;
    в) передать объект концессионного соглашения концеденту по истечении срока действия концессионного соглашения.

    4. Концессионер вправе привлекать третьих лиц для исполнения своих обязательств по концессионному соглашению на основании договоров, заключенных в соответствии с гражданским законодательством.

    5. В случае досрочного прекращения концессионного соглашения по основаниям, предусмотренным пунктом 1 части 1 статьи 15.1 настоящего Федерального закона, или по вине концедента концессионер имеет право потребовать возмещения понесенных им расходов.

    Статья 11. Объект концессионного соглашения

    1. Под объектом концессионного соглашения понимается недвижимое имущество, используемое для осуществления деятельности, предусмотренной концессионным соглашением.

    2. Право собственности на объект концессионного соглашения принадлежит концеденту или иному лицу.
    """

    demo_chunks = chunker.chunk_document(demo_text)
    print(f" Создано {len(demo_chunks)} умных чанков")

    for idx, chunk in enumerate(demo_chunks):
        print(f"\n Чанк {idx + 1}:")
        print(f" Размер: {len(chunk.content)} символов")
        print(f" Приоритет: {chunk.priority.value}")
        print(f" Критичность: {chunk.criticality_score:.2f}")
        print(f" Качество границ: {chunk.boundary_quality:.2f}")
        print(f" Сущностей: {len(chunk.entities.get_all_entities())}")
        print(f" Защищенных зон: {len(chunk.protected_zones)}")

    demo_text_chunks = chunker.convert_to_text_chunks(demo_chunks)
    print(f"\n Конвертировано в {len(demo_text_chunks)} TextChunk объектов")
    print("\n Демонстрация завершена")
