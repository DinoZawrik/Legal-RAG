#!/usr/bin/env python3
"""
🧬 Parental Legal Document Chunker
Система чанкинга с иерархическими parent-child связями для правовых документов.

МИГРАЦИЯ v3.0

Parental chunking техника:
- Создает parent-child отношения между чанками
- Сохраняет иерархическую структуру документа
- Позволяет эффективно находить связанные нормы
- Улучшает качество поиска и генерации ответов

Architecture:
- Родительские чанки (статьи) содержат метаданные о детях
- Дочерние чанки (пункты) ссылаются на родителя
- Поддержка многоуровневой иерархии (глава → статья → пункт → подпункт)
- Семантическая связность через hierarchy_path

Usage:
    from core.parental_legal_chunker import ParentalLegalChunker
    
    chunker = ParentalLegalChunker()
    chunks = await chunker.chunk_document_with_hierarchy(text, document_id)
"""

import logging
import re
import asyncio
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid

from core.advanced_legal_chunker import (
    AdvancedLegalChunker,
    EnhancedLegalChunk,
    LegalElementType,
    ModalityType,
    NumericalConstraint,
    LegalReference
)

logger = logging.getLogger(__name__)


class ChunkRelationType(Enum):
    """Типы связей между чанками."""
    PARENT_CHILD = "parent_child"      # Статья → Пункт
    SIBLING = "sibling"               # Пункт 1 ↔ Пункт 2
    CROSS_REFERENCE = "cross_reference"  # Ссылки между статьями
    SEQUENTIAL = "sequential"         # Последовательные части
    CONTEXTUAL = "contextual"         # Контекстуальная связь


@dataclass
class ParentalChunk(EnhancedLegalChunk):
    """
    Расширенный чанк с parent-child связями.
    Добавляет к EnhancedLegalChunk иерархические связи.
    """
    
    # Иерархические связи
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: List[str] = field(default_factory=list)
    sibling_chunk_ids: List[str] = field(default_factory=list)
    related_chunk_ids: List[str] = field(default_factory=list)
    
    # Структурная иерархия
    hierarchy_level: int = 0  # 0=документ, 1=раздел, 2=глава, 3=статья, 4=пункт, 5=подпункт
    full_hierarchy_path: List[str] = field(default_factory=list)
    
    # Метаданные для связей
    relation_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Качество связей
    parent_confidence: float = 1.0
    child_confidence: float = 1.0
    relationship_strength: float = 1.0
    
    # Семейный размер (property для динамического вычисления)
    _family_size: Optional[int] = field(default=None, init=False, compare=False)

    def add_parent(self, parent_chunk: 'ParentalChunk'):
        """Добавить родительский чанк."""
        self.parent_chunk_id = parent_chunk.chunk_id
        self.parent_confidence = 0.9
        
        # Обновить hierarchy_path
        self.full_hierarchy_path = parent_chunk.full_hierarchy_path + [
            f"{self.article_number or ''}".strip()
        ]
        
        # Обновить hierarchy_level
        self.hierarchy_level = parent_chunk.hierarchy_level + 1

    def add_child(self, child_chunk: 'ParentalChunk'):
        """Добавить дочерний чанк."""
        if child_chunk.chunk_id not in self.child_chunk_ids:
            self.child_chunk_ids.append(child_chunk.chunk_id)
            self.child_confidence = 0.9

    def add_sibling(self, sibling_chunk: 'ParentalChunk'):
        """Добавить сиблинга (братский чанк)."""
        if sibling_chunk.chunk_id not in self.sibling_chunk_ids:
            self.sibling_chunk_ids.append(sibling_chunk.chunk_id)

    @property
    def family_size(self) -> int:
        """Размер семейного узла (родитель + дети + сиблинги + сам)."""
        return 1 + len(self.child_chunk_ids) + len(self.sibling_chunk_ids)

    def get_family_tree(self) -> Dict[str, Any]:
        """Получить семейное дерево (родители, дети, сиблинги)."""
        return {
            "chunk_id": self.chunk_id,
            "parent": self.parent_chunk_id,
            "children": self.child_chunk_ids,
            "siblings": self.sibling_chunk_ids,
            "level": self.hierarchy_level,
            "path": self.full_hierarchy_path,
            "family_size": self.family_size
        }

    def to_parental_metadata(self) -> Dict[str, Any]:
        """Преобразование в метаданные для ChromaDB с parental связями."""
        base_metadata = super().to_chromadb_metadata()
        
        # Добавляем parental метаданные
        parental_metadata = {
            **base_metadata,
            "parent_chunk_id": self.parent_chunk_id or "",
            "child_chunk_ids": "|".join(self.child_chunk_ids),
            "sibling_chunk_ids": "|".join(self.sibling_chunk_ids),
            "hierarchy_level": self.hierarchy_level,
            "full_hierarchy_path": "|".join(self.full_hierarchy_path),
            "parent_confidence": self.parent_confidence,
            "child_confidence": self.child_confidence,
            "relationship_strength": self.relationship_strength,
            "has_parents": self.parent_chunk_id is not None,
            "has_children": len(self.child_chunk_ids) > 0,
            "has_siblings": len(self.sibling_chunk_ids) > 0,
            "family_size": 1 + len(self.child_chunk_ids) + len(self.sibling_chunk_ids)
        }
        
        return parental_metadata


class ParentalLegalChunker:
    """
    Чанкер с поддержкой parent-child связей.
    
    Особенности:
    - Автоматическое создание иерархических связей
    - Сохранение контекстуальных отношений
    - Поддержка многоуровневых структур
    - Умное разрешение parent-child связей
    - Валидация структурной целостности
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Базовый чанкер для первоначального разбиения
        self.base_chunker = AdvancedLegalChunker()
        
        # Кэш для быстрого доступа к чанкам
        self._chunk_cache: Dict[str, ParentalChunk] = {}
        
        # Структурные паттерны для определения parent-child связей
        self.structure_patterns = self._load_structure_patterns()

        self.logger.info("🧬 Parental Legal Chunker инициализирован")

    def _load_structure_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Паттерны для определения структурных связей."""
        return {
            "article_parent": [
                re.compile(r'^Статья\s+(\d+(?:\.\d+)?)\.', re.IGNORECASE),
                re.compile(r'^Ст\.\s*(\d+(?:\.\d+)?)\.', re.IGNORECASE),
            ],
            "part_child": [
                re.compile(r'^(\d+)\.\s+', re.MULTILINE),
            ],
            "point_child": [
                re.compile(r'^(\d+)\)\s+', re.MULTILINE),
            ],
            "subpoint_child": [
                re.compile(r'^([а-я])\)\s+', re.MULTILINE),
            ]
        }

    async def chunk_document_with_hierarchy(
        self, 
        text: str, 
        document_id: str,
        law_number: Optional[str] = None
    ) -> List[ParentalChunk]:
        """
        Разбиение документа с созданием parent-child связей.
        
        Args:
            text: Текст документа
            document_id: Идентификатор документа
            law_number: Номер закона (опционально)
            
        Returns:
            Список чанков с иерархическими связями
        """
        self.logger.info(f"[PARENTAL_CHUNKER] Processing document {document_id}")

        # 1. Первоначальное разбиение через базовый чанкер
        base_chunks = self.base_chunker.chunk_document(text, document_id, law_number)
        
        # 2. Преобразование в ParentalChunk
        parental_chunks = await self._convert_to_parental_chunks(base_chunks, text, document_id)
        
        # 3. Создание parent-child связей
        parental_chunks = await self._establish_parent_child_relations(parental_chunks, text)
        
        # 4. Создание sibling связей
        await self._establish_sibling_relations(parental_chunks)
        
        # 5. Валидация связей
        self._validate_relationships(parental_chunks)
        
        # 6. Кэширование
        self._cache_chunks(parental_chunks)

        self.logger.info(f"[PARENTAL_CHUNKER] Created {len(parental_chunks)} parental chunks")
        return parental_chunks

    async def _convert_to_parental_chunks(
        self, 
        base_chunks: List[EnhancedLegalChunk],
        full_text: str,
        document_id: str
    ) -> List[ParentalChunk]:
        """Преобразование базовых чанков в parental чанки."""
        parental_chunks = []
        
        for base_chunk in base_chunks:
            # Создаем ParentalChunk на основе EnhancedLegalChunk
            parental_chunk = ParentalChunk(
                content=base_chunk.content,
                chunk_id=base_chunk.chunk_id,
                document_id=base_chunk.document_id,
                law_number=base_chunk.law_number,
                section_number=base_chunk.section_number,
                chapter_number=base_chunk.chapter_number,
                article_number=base_chunk.article_number,
                part_number=base_chunk.part_number,
                point_number=base_chunk.point_number,
                subpoint_number=base_chunk.subpoint_number,
                element_type=base_chunk.element_type,
                modality=base_chunk.modality,
                legal_concepts=base_chunk.legal_concepts,
                key_terms=base_chunk.key_terms,
                numerical_constraints=base_chunk.numerical_constraints,
                legal_references=base_chunk.legal_references,
                cross_references=base_chunk.cross_references,
                parent_context=base_chunk.parent_context,
                children_chunks=base_chunk.children_chunks,
                hierarchy_path=base_chunk.hierarchy_path,
                search_keywords=base_chunk.search_keywords,
                importance_score=base_chunk.importance_score,
                confidence_score=base_chunk.confidence_score
            )
            
            # Определяем уровень иерархии
            parental_chunk.hierarchy_level = self._determine_hierarchy_level(parental_chunk)
            parental_chunk.full_hierarchy_path = self._build_full_hierarchy_path(parental_chunk)
            
            parental_chunks.append(parental_chunk)
        
        return parental_chunks

    def _determine_hierarchy_level(self, chunk: ParentalChunk) -> int:
        """Определение уровня иерархии для чанка."""
        if not chunk.element_type:
            return 0
        
        level_mapping = {
            LegalElementType.FEDERAL_LAW: 0,
            LegalElementType.CHAPTER: 1,
            LegalElementType.SECTION: 2,
            LegalElementType.ARTICLE: 3,
            LegalElementType.PART: 4,
            LegalElementType.POINT: 5,
            LegalElementType.SUBPOINT: 6,
        }
        
        return level_mapping.get(chunk.element_type, 3)

    def _build_full_hierarchy_path(self, chunk: ParentalChunk) -> List[str]:
        """Построение полного пути иерархии."""
        path = []
        
        # Добавляем номер закона
        if chunk.law_number:
            path.append(chunk.law_number)
        
        # Добавляем раздел
        if chunk.section_number:
            path.append(f"Раздел {chunk.section_number}")
        
        # Добавляем главу
        if chunk.chapter_number:
            path.append(f"Глава {chunk.chapter_number}")
        
        # Добавляем статью
        if chunk.article_number:
            path.append(f"Статья {chunk.article_number}")
        
        # Добавляем часть
        if chunk.part_number:
            path.append(f"Часть {chunk.part_number}")
        
        # Добавляем пункт
        if chunk.point_number:
            path.append(f"Пункт {chunk.point_number}")
        
        # Добавляем подпункт
        if chunk.subpoint_number:
            path.append(f"Подпункт {chunk.subpoint_number}")
        
        return path

    async def _establish_parent_child_relations(
        self, 
        chunks: List[ParentalChunk], 
        full_text: str
    ) -> List[ParentalChunk]:
        """Создание parent-child связей."""
        # Группируем чанки по структурному уровню
        level_groups = {}
        for chunk in chunks:
            level = chunk.hierarchy_level
            if level not in level_groups:
                level_groups[level] = []
            level_groups[level].append(chunk)
        
        # Создаем связи для каждого уровня
        for level in sorted(level_groups.keys()):
            if level == 0:  # Уровень документа - нет родителя
                continue
                
            parent_level = level - 1
            if parent_level not in level_groups:
                continue
            
            # Для каждого чанка текущего уровня ищем родителя
            for child in level_groups[level]:
                parent = self._find_parent_chunk(child, level_groups[parent_level], full_text)
                if parent:
                    child.add_parent(parent)
                    parent.add_child(child)
        
        return chunks

    def _find_parent_chunk(
        self, 
        child: ParentalChunk, 
        potential_parents: List[ParentalChunk],
        full_text: str
    ) -> Optional[ParentalChunk]:
        """Поиск родительского чанка для дочернего."""
        if not potential_parents:
            return None
        
        best_parent = None
        best_score = 0.0
        
        # Критерии для выбора родителя:
        # 1. Статья → пункт/часть
        # 2. Ближайшая позиция в тексте
        # 3. Совпадающий контекст
        
        child_start_pos = full_text.find(child.content)
        if child_start_pos == -1:
            return None
        
        for parent in potential_parents:
            parent_start_pos = full_text.find(parent.content)
            if parent_start_pos == -1:
                continue
            
            # Родитель должен быть перед ребенком в тексте
            if parent_start_pos >= child_start_pos:
                continue
            
            # Вычисляем score
            score = self._calculate_parent_child_score(child, parent, child_start_pos, parent_start_pos)
            
            if score > best_score:
                best_score = score
                best_parent = parent
        
        return best_parent

    def _calculate_parent_child_score(
        self, 
        child: ParentalChunk, 
        parent: ParentalChunk,
        child_pos: int,
        parent_pos: int
    ) -> float:
        """Расчет score для parent-child связи."""
        score = 0.0
        
        # Структурная совместимость
        if (child.article_number and parent.article_number and 
            child.article_number == parent.article_number):
            score += 0.8
        
        # Близость в тексте (чем ближе, тем лучше)
        distance = abs(child_pos - parent_pos)
        proximity_score = max(0, 1.0 - (distance / 10000))  # Нормализация
        score += proximity_score * 0.2
        
        return score

    async def _establish_sibling_relations(self, chunks: List[ParentalChunk]):
        """Создание sibling (братских) связей."""
        # Группируем чанки по родителю
        parent_groups = {}
        for chunk in chunks:
            if chunk.parent_chunk_id:
                if chunk.parent_chunk_id not in parent_groups:
                    parent_groups[chunk.parent_chunk_id] = []
                parent_groups[chunk.parent_chunk_id].append(chunk)
        
        # Создаем sibling связи в каждой группе
        for parent_id, siblings in parent_groups.items():
            if len(siblings) > 1:
                for i, sibling1 in enumerate(siblings):
                    for sibling2 in siblings[i+1:]:
                        sibling1.add_sibling(sibling2)
                        sibling2.add_sibling(sibling1)

    def _validate_relationships(self, chunks: List[ParentalChunk]):
        """Валидация созданных связей."""
        validation_errors = []
        
        for chunk in chunks:
            # Проверяем циклические ссылки
            if self._has_cycle(chunk.chunk_id, chunks, visited=set()):
                validation_errors.append(f"Cycle detected for chunk {chunk.chunk_id}")
            
            # Проверяем корректность hierarchy_level
            if chunk.parent_chunk_id:
                parent = next((c for c in chunks if c.chunk_id == chunk.parent_chunk_id), None)
                if parent and chunk.hierarchy_level <= parent.hierarchy_level:
                    validation_errors.append(
                        f"Invalid hierarchy level for {chunk.chunk_id}: {chunk.hierarchy_level} <= parent {parent.hierarchy_level}"
                    )
        
        if validation_errors:
            self.logger.warning(f"⚠️ Relationship validation errors: {len(validation_errors)}")
            for error in validation_errors:
                self.logger.warning(f"  - {error}")
        else:
            self.logger.info("✅ All relationships validated successfully")

    def _has_cycle(self, chunk_id: str, chunks: List[ParentalChunk], visited: Set[str]) -> bool:
        """Проверка циклических ссылок."""
        if chunk_id in visited:
            return True
        
        visited.add(chunk_id)
        
        chunk = next((c for c in chunks if c.chunk_id == chunk_id), None)
        if not chunk:
            return False
        
        # Проверяем связи через children
        for child_id in chunk.child_chunk_ids:
            if self._has_cycle(child_id, chunks, visited.copy()):
                return True
        
        return False

    def _cache_chunks(self, chunks: List[ParentalChunk]):
        """Кэширование чанков для быстрого доступа."""
        self._chunk_cache.clear()
        for chunk in chunks:
            self._chunk_cache[chunk.chunk_id] = chunk

    def get_chunk_family(self, chunk_id: str) -> Dict[str, Any]:
        """Получить семейное дерево для чанка."""
        if chunk_id not in self._chunk_cache:
            return {}
        
        chunk = self._chunk_cache[chunk_id]
        return chunk.get_family_tree()

    def find_related_chunks(self, chunk_id: str, relation_types: List[ChunkRelationType]) -> List[str]:
        """Найти связанные чанки по типам связей."""
        if chunk_id not in self._chunk_cache:
            return []
        
        chunk = self._chunk_cache[chunk_id]
        related = []
        
        if ChunkRelationType.PARENT_CHILD in relation_types:
            # Добавляем детей
            related.extend(chunk.child_chunk_ids)
            
            # Добавляем родителя
            if chunk.parent_chunk_id:
                related.append(chunk.parent_chunk_id)
        
        if ChunkRelationType.SIBLING in relation_types:
            related.extend(chunk.sibling_chunk_ids)
        
        return related

    def get_hierarchy_statistics(self) -> Dict[str, Any]:
        """Получить статистику иерархии."""
        if not self._chunk_cache:
            return {}
        
        chunks = list(self._chunk_cache.values())
        
        # Подсчет по уровням
        level_counts = {}
        for chunk in chunks:
            level = chunk.hierarchy_level
            level_counts[level] = level_counts.get(level, 0) + 1
        
        # Подсчет связей
        total_parents = sum(1 for c in chunks if c.parent_chunk_id)
        total_children = sum(len(c.child_chunk_ids) for c in chunks)
        total_siblings = sum(len(c.sibling_chunk_ids) for c in chunks) // 2  # Избегаем двойного счета
        avg_family_size = sum(c.family_size for c in chunks) / len(chunks) if chunks else 0
        
        return {
            "total_chunks": len(chunks),
            "level_distribution": level_counts,
            "parent_relationships": total_parents,
            "child_relationships": total_children,
            "sibling_relationships": total_siblings,
            "average_family_size": avg_family_size
        }


# Глобальный экземпляр
_parental_chunker: Optional[ParentalLegalChunker] = None


def get_parental_chunker() -> ParentalLegalChunker:
    """Получить глобальный экземпляр parental chunker."""
    global _parental_chunker
    if _parental_chunker is None:
        _parental_chunker = ParentalLegalChunker()
    return _parental_chunker


# Пример использования
if __name__ == "__main__":
    async def main():
        print("🧬 Parental Legal Chunker - Демонстрация")
        print("=" * 60)

        chunker = ParentalLegalChunker()

        demo_text = """
        Федеральный закон № 115-ФЗ "О концессионных соглашениях"

        Глава 1. ОБЩИЕ ПОЛОЖЕНИЯ

        Статья 1. Основные понятия

        1. В настоящем Федеральном законе используются следующие основные понятия:
        а) концессионное соглашение - договор, заключаемый между концедентом и концессионером;
        б) концессионер - лицо, которому предоставляется право на создание и (или) реконструкцию объекта концессионного соглашения;

        2. Концессионное соглашение заключается в соответствии с настоящим Федеральным законом.

        Статья 2. Стороны концессионного соглашения

        1. Концедентом может выступать:
        а) Российская Федерация;
        б) субъект Российской Федерации;
        в) муниципальное образование.

        2. Концессионером может выступать:
        а) индивидуальный предприниматель;
        б) коммерческая организация;
        в) некоммерческая организация.
        """

        # Создание parental chunks
        parental_chunks = await chunker.chunk_document_with_hierarchy(
            demo_text, 
            document_id="demo_law_115fz"
        )

        print(f"\n✅ Создано {len(parental_chunks)} parental chunks")

        # Анализ семейных связей
        for chunk in parental_chunks:
            if chunk.article_number:  # Показываем только статьи
                family = chunk.get_family_tree()
                print(f"\n🔍 Статья {chunk.article_number}:")
                print(f"   Уровень: {family['level']}")
                print(f"   Путь: {' → '.join(family['path'])}")
                print(f"   Родитель: {family['parent']}")
                print(f"   Дети: {family['children']}")
                print(f"   Сиблинги: {family['siblings']}")

        # Статистика иерархии
        stats = chunker.get_hierarchy_statistics()
        print(f"\n📊 Статистика иерархии:")
        print(f"   Всего чанков: {stats['total_chunks']}")
        print(f"   Parent-связи: {stats['parent_relationships']}")
        print(f"   Child-связи: {stats['child_relationships']}")
        print(f"   Sibling-связи: {stats['sibling_relationships']}")

        print("\n✅ Демонстрация завершена")

    asyncio.run(main())