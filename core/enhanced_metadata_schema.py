"""
Enhanced Metadata Schema with Legal Concepts
Расширенная схема метаданных для правовых документов
Интеграция с advanced legal chunker и specialized NER
"""

from typing import Dict, List, Any, Optional, Set, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Типы правовых документов с приоритетами"""
    CONSTITUTION = "constitution"          # Приоритет 1
    FEDERAL_LAW = "federal_law"           # Приоритет 2
    CODE = "code"                         # Приоритет 3
    PRESIDENTIAL_DECREE = "presidential_decree"  # Приоритет 4
    GOVERNMENT_RESOLUTION = "government_resolution"  # Приоритет 5
    MINISTERIAL_ORDER = "ministerial_order"  # Приоритет 6
    DEPARTMENTAL_INSTRUCTION = "departmental_instruction"  # Приоритет 7
    LOCAL_REGULATION = "local_regulation"  # Приоритет 8


class LegalEntityType(Enum):
    """Типы правовых сущностей"""
    PERSON = "person"                     # Физическое лицо
    LEGAL_ENTITY = "legal_entity"         # Юридическое лицо
    STATE_ORGAN = "state_organ"           # Государственный орган
    OFFICIAL = "official"                 # Должностное лицо
    DOCUMENT = "document"                 # Документ
    PROCEDURE = "procedure"               # Процедура
    OBLIGATION = "obligation"             # Обязательство
    RIGHT = "right"                       # Право
    PROHIBITION = "prohibition"           # Запрет
    SANCTION = "sanction"                 # Санкция


class JurisdictionLevel(Enum):
    """Уровни юрисдикции"""
    FEDERAL = "federal"
    REGIONAL = "regional"
    MUNICIPAL = "municipal"
    DEPARTMENTAL = "departmental"


@dataclass
class LegalConcept:
    """Правовая концепция"""
    concept_id: str
    name: str
    definition: str
    entity_type: LegalEntityType
    related_articles: List[str] = field(default_factory=list)
    related_concepts: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'concept_id': self.concept_id,
            'name': self.name,
            'definition': self.definition,
            'entity_type': self.entity_type.value,
            'related_articles': self.related_articles,
            'related_concepts': self.related_concepts,
            'keywords': self.keywords,
            'confidence': self.confidence
        }


@dataclass
class LegalConstraint:
    """Правовое ограничение с численными значениями"""
    constraint_id: str
    constraint_type: str  # percentage, monetary, temporal, quantity
    value: str
    normalized_value: float
    modality: str  # mandatory, prohibited, permitted, conditional
    applies_to: str
    article_ref: Optional[str] = None
    part_ref: Optional[str] = None
    exceptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'constraint_id': self.constraint_id,
            'constraint_type': self.constraint_type,
            'value': self.value,
            'normalized_value': self.normalized_value,
            'modality': self.modality,
            'applies_to': self.applies_to,
            'article_ref': self.article_ref,
            'part_ref': self.part_ref,
            'exceptions': self.exceptions
        }


@dataclass
class LegalRelationship:
    """Правовая связь между сущностями"""
    relationship_id: str
    source_entity: str
    target_entity: str
    relationship_type: str  # regulates, defines, references, modifies, repeals
    strength: float = 1.0
    context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'relationship_id': self.relationship_id,
            'source_entity': self.source_entity,
            'target_entity': self.target_entity,
            'relationship_type': self.relationship_type,
            'strength': self.strength,
            'context': self.context
        }


@dataclass
class ArticleStructure:
    """Структура статьи закона"""
    article_number: str
    article_title: str
    parts: List[Dict[str, Any]] = field(default_factory=list)
    points: List[Dict[str, Any]] = field(default_factory=list)
    subpoints: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_part(self, part_number: str, content: str, constraints: List[LegalConstraint] = None):
        """Добавить часть статьи"""
        part = {
            'part_number': part_number,
            'content': content,
            'constraints': [c.to_dict() for c in (constraints or [])],
            'concepts': []
        }
        self.parts.append(part)

    def add_point(self, point_number: str, content: str, part_ref: Optional[str] = None):
        """Добавить пункт"""
        point = {
            'point_number': point_number,
            'content': content,
            'part_ref': part_ref,
            'constraints': [],
            'concepts': []
        }
        self.points.append(point)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'article_number': self.article_number,
            'article_title': self.article_title,
            'parts': self.parts,
            'points': self.points,
            'subpoints': self.subpoints,
            'notes': self.notes
        }


@dataclass
class EnhancedDocumentMetadata:
    """Расширенные метаданные документа"""
    # Основная информация
    document_id: str
    title: str
    document_type: DocumentType
    document_number: Optional[str] = None
    adoption_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    jurisdiction: JurisdictionLevel = JurisdictionLevel.FEDERAL

    # Правовая структура
    articles: List[ArticleStructure] = field(default_factory=list)
    legal_concepts: List[LegalConcept] = field(default_factory=list)
    legal_constraints: List[LegalConstraint] = field(default_factory=list)
    legal_relationships: List[LegalRelationship] = field(default_factory=list)

    # Связи с другими документами
    references_to: List[str] = field(default_factory=list)  # Ссылки на другие документы
    referenced_by: List[str] = field(default_factory=list)  # Ссылки из других документов
    amends: List[str] = field(default_factory=list)        # Документы, которые изменяет
    amended_by: List[str] = field(default_factory=list)    # Документы, которые изменяют данный

    # Классификация содержания
    subject_areas: List[str] = field(default_factory=list)  # Предметные области
    keywords: List[str] = field(default_factory=list)       # Ключевые слова
    legal_institutes: List[str] = field(default_factory=list)  # Правовые институты

    # Обработка и качество
    processing_metadata: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    completeness_score: float = 0.0

    def add_article(self, article: ArticleStructure):
        """Добавить статью"""
        self.articles.append(article)

    def add_legal_concept(self, concept: LegalConcept):
        """Добавить правовую концепцию"""
        self.legal_concepts.append(concept)

    def add_legal_constraint(self, constraint: LegalConstraint):
        """Добавить правовое ограничение"""
        self.legal_constraints.append(constraint)

    def add_legal_relationship(self, relationship: LegalRelationship):
        """Добавить правовую связь"""
        self.legal_relationships.append(relationship)

    def get_priority_level(self) -> int:
        """Получить уровень приоритета документа"""
        priority_map = {
            DocumentType.CONSTITUTION: 1,
            DocumentType.FEDERAL_LAW: 2,
            DocumentType.CODE: 3,
            DocumentType.PRESIDENTIAL_DECREE: 4,
            DocumentType.GOVERNMENT_RESOLUTION: 5,
            DocumentType.MINISTERIAL_ORDER: 6,
            DocumentType.DEPARTMENTAL_INSTRUCTION: 7,
            DocumentType.LOCAL_REGULATION: 8
        }
        return priority_map.get(self.document_type, 8)

    def get_constraints_by_type(self, constraint_type: str) -> List[LegalConstraint]:
        """Получить ограничения по типу"""
        return [c for c in self.legal_constraints if c.constraint_type == constraint_type]

    def get_concepts_by_entity_type(self, entity_type: LegalEntityType) -> List[LegalConcept]:
        """Получить концепции по типу сущности"""
        return [c for c in self.legal_concepts if c.entity_type == entity_type]

    def find_article_by_number(self, article_number: str) -> Optional[ArticleStructure]:
        """Найти статью по номеру"""
        for article in self.articles:
            if article.article_number == article_number:
                return article
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для сериализации"""
        return {
            'document_id': self.document_id,
            'title': self.title,
            'document_type': self.document_type.value,
            'document_number': self.document_number,
            'adoption_date': self.adoption_date.isoformat() if self.adoption_date else None,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'jurisdiction': self.jurisdiction.value,
            'articles': [a.to_dict() for a in self.articles],
            'legal_concepts': [c.to_dict() for c in self.legal_concepts],
            'legal_constraints': [c.to_dict() for c in self.legal_constraints],
            'legal_relationships': [r.to_dict() for r in self.legal_relationships],
            'references_to': self.references_to,
            'referenced_by': self.referenced_by,
            'amends': self.amends,
            'amended_by': self.amended_by,
            'subject_areas': self.subject_areas,
            'keywords': self.keywords,
            'legal_institutes': self.legal_institutes,
            'processing_metadata': self.processing_metadata,
            'quality_score': self.quality_score,
            'completeness_score': self.completeness_score,
            'priority_level': self.get_priority_level()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedDocumentMetadata':
        """Создать из словаря"""
        metadata = cls(
            document_id=data['document_id'],
            title=data['title'],
            document_type=DocumentType(data['document_type']),
            document_number=data.get('document_number'),
            jurisdiction=JurisdictionLevel(data.get('jurisdiction', 'federal'))
        )

        # Восстановление дат
        if data.get('adoption_date'):
            metadata.adoption_date = datetime.fromisoformat(data['adoption_date'])
        if data.get('effective_date'):
            metadata.effective_date = datetime.fromisoformat(data['effective_date'])

        # Восстановление структур
        for article_data in data.get('articles', []):
            article = ArticleStructure(
                article_number=article_data['article_number'],
                article_title=article_data['article_title'],
                parts=article_data.get('parts', []),
                points=article_data.get('points', []),
                subpoints=article_data.get('subpoints', []),
                notes=article_data.get('notes', [])
            )
            metadata.add_article(article)

        # Восстановление концепций
        for concept_data in data.get('legal_concepts', []):
            concept = LegalConcept(
                concept_id=concept_data['concept_id'],
                name=concept_data['name'],
                definition=concept_data['definition'],
                entity_type=LegalEntityType(concept_data['entity_type']),
                related_articles=concept_data.get('related_articles', []),
                related_concepts=concept_data.get('related_concepts', []),
                keywords=concept_data.get('keywords', []),
                confidence=concept_data.get('confidence', 1.0)
            )
            metadata.add_legal_concept(concept)

        # Восстановление ограничений
        for constraint_data in data.get('legal_constraints', []):
            constraint = LegalConstraint(
                constraint_id=constraint_data['constraint_id'],
                constraint_type=constraint_data['constraint_type'],
                value=constraint_data['value'],
                normalized_value=constraint_data['normalized_value'],
                modality=constraint_data['modality'],
                applies_to=constraint_data['applies_to'],
                article_ref=constraint_data.get('article_ref'),
                part_ref=constraint_data.get('part_ref'),
                exceptions=constraint_data.get('exceptions', [])
            )
            metadata.add_legal_constraint(constraint)

        # Восстановление связей
        for relationship_data in data.get('legal_relationships', []):
            relationship = LegalRelationship(
                relationship_id=relationship_data['relationship_id'],
                source_entity=relationship_data['source_entity'],
                target_entity=relationship_data['target_entity'],
                relationship_type=relationship_data['relationship_type'],
                strength=relationship_data.get('strength', 1.0),
                context=relationship_data.get('context', '')
            )
            metadata.add_legal_relationship(relationship)

        # Остальные поля
        metadata.references_to = data.get('references_to', [])
        metadata.referenced_by = data.get('referenced_by', [])
        metadata.amends = data.get('amends', [])
        metadata.amended_by = data.get('amended_by', [])
        metadata.subject_areas = data.get('subject_areas', [])
        metadata.keywords = data.get('keywords', [])
        metadata.legal_institutes = data.get('legal_institutes', [])
        metadata.processing_metadata = data.get('processing_metadata', {})
        metadata.quality_score = data.get('quality_score', 0.0)
        metadata.completeness_score = data.get('completeness_score', 0.0)

        return metadata


@dataclass
class EnhancedChunkMetadata:
    """Расширенные метаданные для фрагмента документа"""
    # Основная информация
    chunk_id: str
    document_id: str
    chunk_type: str  # article, part, point, paragraph, table, list
    content_hash: str

    # Структурная информация
    article_number: Optional[str] = None
    part_number: Optional[str] = None
    point_number: Optional[str] = None
    subpoint_number: Optional[str] = None

    # Правовое содержание
    legal_concepts: List[str] = field(default_factory=list)
    legal_constraints: List[str] = field(default_factory=list)
    numerical_entities: List[Dict[str, Any]] = field(default_factory=list)

    # Связи
    references_articles: List[str] = field(default_factory=list)
    references_laws: List[str] = field(default_factory=list)
    modality_indicators: List[str] = field(default_factory=list)

    # Качество и релевантность
    importance_score: float = 0.0
    completeness_score: float = 0.0
    search_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'chunk_type': self.chunk_type,
            'content_hash': self.content_hash,
            'article_number': self.article_number,
            'part_number': self.part_number,
            'point_number': self.point_number,
            'subpoint_number': self.subpoint_number,
            'legal_concepts': self.legal_concepts,
            'legal_constraints': self.legal_constraints,
            'numerical_entities': self.numerical_entities,
            'references_articles': self.references_articles,
            'references_laws': self.references_laws,
            'modality_indicators': self.modality_indicators,
            'importance_score': self.importance_score,
            'completeness_score': self.completeness_score,
            'search_keywords': self.search_keywords
        }


class MetadataBuilder:
    """Строитель расширенных метаданных"""

    def __init__(self):
        self.document_metadata = None
        self.chunk_metadata_list = []

    def create_document_metadata(self, document_id: str, title: str,
                               document_type: DocumentType) -> EnhancedDocumentMetadata:
        """Создать метаданные документа"""
        self.document_metadata = EnhancedDocumentMetadata(
            document_id=document_id,
            title=title,
            document_type=document_type
        )
        return self.document_metadata

    def add_article_from_chunker(self, article_data: Dict[str, Any]):
        """Добавить статью из advanced legal chunker"""
        if not self.document_metadata:
            raise ValueError("Document metadata not initialized")

        article = ArticleStructure(
            article_number=article_data['article_number'],
            article_title=article_data.get('title', '')
        )

        # Добавляем части и пункты
        for part_data in article_data.get('parts', []):
            article.add_part(
                part_number=part_data['part_number'],
                content=part_data['content']
            )

        for point_data in article_data.get('points', []):
            article.add_point(
                point_number=point_data['point_number'],
                content=point_data['content'],
                part_ref=point_data.get('part_ref')
            )

        self.document_metadata.add_article(article)

    def add_constraints_from_ner(self, ner_entities: List[Dict[str, Any]]):
        """Добавить ограничения из specialized NER"""
        if not self.document_metadata:
            raise ValueError("Document metadata not initialized")

        for entity in ner_entities:
            if entity.get('type') == 'numerical_entity':
                constraint = LegalConstraint(
                    constraint_id=f"constraint_{len(self.document_metadata.legal_constraints)}",
                    constraint_type=entity['constraint_type'],
                    value=entity['value'],
                    normalized_value=entity['normalized_value'],
                    modality=entity['modality'],
                    applies_to=entity.get('context', ''),
                    article_ref=entity.get('article_ref'),
                    part_ref=entity.get('part_ref')
                )
                self.document_metadata.add_legal_constraint(constraint)

    def build_chunk_metadata(self, chunk_id: str, document_id: str,
                           chunk_type: str, content: str) -> EnhancedChunkMetadata:
        """Создать метаданные фрагмента"""
        import hashlib

        chunk_metadata = EnhancedChunkMetadata(
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_type=chunk_type,
            content_hash=hashlib.md5(content.encode()).hexdigest()
        )

        self.chunk_metadata_list.append(chunk_metadata)
        return chunk_metadata

    def get_complete_metadata(self) -> Dict[str, Any]:
        """Получить полные метаданные"""
        return {
            'document_metadata': self.document_metadata.to_dict() if self.document_metadata else None,
            'chunk_metadata': [cm.to_dict() for cm in self.chunk_metadata_list]
        }


# Фабричные функции
def create_metadata_builder() -> MetadataBuilder:
    """Создать строитель метаданных"""
    return MetadataBuilder()


def create_legal_concept(name: str, definition: str, entity_type: LegalEntityType) -> LegalConcept:
    """Создать правовую концепцию"""
    import uuid
    return LegalConcept(
        concept_id=str(uuid.uuid4()),
        name=name,
        definition=definition,
        entity_type=entity_type
    )


def create_legal_constraint(constraint_type: str, value: str, normalized_value: float,
                          modality: str, applies_to: str) -> LegalConstraint:
    """Создать правовое ограничение"""
    import uuid
    return LegalConstraint(
        constraint_id=str(uuid.uuid4()),
        constraint_type=constraint_type,
        value=value,
        normalized_value=normalized_value,
        modality=modality,
        applies_to=applies_to
    )


# Пример использования
if __name__ == "__main__":
    # Создание метаданных для 115-ФЗ
    builder = create_metadata_builder()

    # Создаем метаданные документа
    doc_metadata = builder.create_document_metadata(
        document_id="115_fz",
        title="О концессионных соглашениях",
        document_type=DocumentType.FEDERAL_LAW
    )

    doc_metadata.document_number = "115-ФЗ"
    doc_metadata.subject_areas = ["концессии", "государственно-частное партнерство"]
    doc_metadata.keywords = ["концессионное соглашение", "концедент", "концессионер"]

    # Добавляем правовую концепцию
    concept = create_legal_concept(
        name="плата концедента",
        definition="Плата за предоставление прав по концессионному соглашению",
        entity_type=LegalEntityType.OBLIGATION
    )
    doc_metadata.add_legal_concept(concept)

    # Добавляем ограничение
    constraint = create_legal_constraint(
        constraint_type="percentage",
        value="80%",
        normalized_value=80.0,
        modality="prohibited",
        applies_to="плата концедента"
    )
    constraint.article_ref = "7"
    constraint.part_ref = "1"
    doc_metadata.add_legal_constraint(constraint)

    print("Метаданные созданы:")
    print(f"Документ: {doc_metadata.title}")
    print(f"Концепции: {len(doc_metadata.legal_concepts)}")
    print(f"Ограничения: {len(doc_metadata.legal_constraints)}")
    print(f"Приоритет: {doc_metadata.get_priority_level()}")