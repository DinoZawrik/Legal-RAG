#!/usr/bin/env python3
"""
Advanced Legal Document Chunker
Решает проблему 33% error rate через структурно-осведомленное разбиение.

Ключевые улучшения:
- Распознавание российской правовой структуры (статья часть пункт)
- Сохранение численных ограничений (80%, сроки, суммы)
- Обнаружение запретов и ограничений
- Создание rich metadata для точного поиска
- Контекстные связи между нормами

Решает выявленные проблемы:
Статья 10.1 не найдена Точное распознавание структуры статей
80% лимит потерян Специальная обработка численных данных
Запреты не обнаружены Детекция модальности (можно/нельзя/должен)
Уклончивые ответы Rich metadata для точного сопоставления
"""

import logging
import re
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class LegalElementType(Enum):
    """Типы правовых элементов в российском законодательстве."""
    FEDERAL_LAW = "federal_law" # Федеральный закон
    ARTICLE = "article" # Статья
    PART = "part" # Часть
    POINT = "point" # Пункт
    SUBPOINT = "subpoint" # Подпункт
    CHAPTER = "chapter" # Глава
    SECTION = "section" # Раздел
    DEFINITION = "definition" # Определение
    PROHIBITION = "prohibition" # Запрет
    PERMISSION = "permission" # Разрешение
    OBLIGATION = "obligation" # Обязанность
    NUMERICAL_CONSTRAINT = "numerical_constraint" # Численное ограничение


class ModalityType(Enum):
    """Типы правовой модальности."""
    PROHIBITION = "prohibition" # не может, не вправе, запрещено
    PERMISSION = "permission" # может, вправе, разрешено
    OBLIGATION = "obligation" # должен, обязан, необходимо
    CONDITIONAL = "conditional" # если, в случае, при условии
    NEUTRAL = "neutral" # описательные нормы


@dataclass
class NumericalConstraint:
    """Численное ограничение в правовой норме."""
    value: str # "80", "три года"
    unit: str # "%", "лет", "рублей"
    operator: str # "не более", "не менее", "до"
    context: str # контекст ограничения
    constraint_type: str # "размер", "срок", "количество"
    full_expression: str # полное выражение


@dataclass
class LegalReference:
    """Ссылка на другую правовую норму."""
    law_number: Optional[str] = None # "115-ФЗ"
    article: Optional[str] = None # "10.1"
    part: Optional[str] = None # "1"
    point: Optional[str] = None # "1"
    full_reference: str = "" # полная ссылка
    reference_type: str = "internal" # internal, external


@dataclass
class EnhancedLegalChunk:
    """Улучшенный правовой чанк с богатыми метаданными."""
    # Основное содержимое
    content: str
    chunk_id: str
    document_id: str

    # Структурная информация
    law_number: Optional[str] = None
    section_number: Optional[str] = None
    chapter_number: Optional[str] = None
    article_number: Optional[str] = None
    part_number: Optional[str] = None
    point_number: Optional[str] = None
    subpoint_number: Optional[str] = None

    # Правовая семантика
    element_type: LegalElementType = LegalElementType.ARTICLE
    modality: ModalityType = ModalityType.NEUTRAL
    legal_concepts: List[str] = field(default_factory=list)
    key_terms: List[str] = field(default_factory=list)

    # Численные ограничения
    numerical_constraints: List[NumericalConstraint] = field(default_factory=list)

    # Ссылки и связи
    legal_references: List[LegalReference] = field(default_factory=list)
    cross_references: List[str] = field(default_factory=list)

    # Иерархический контекст
    parent_context: Optional[str] = None
    children_chunks: List[str] = field(default_factory=list)
    hierarchy_path: List[str] = field(default_factory=list)

    # Метаданные для поиска
    search_keywords: List[str] = field(default_factory=list)
    importance_score: float = 1.0
    confidence_score: float = 1.0

    def to_chromadb_metadata(self) -> Dict[str, Any]:
        """Преобразование в метаданные ChromaDB."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "law_number": self.law_number or "",
            "section_number": self.section_number or "",
            "chapter_number": self.chapter_number or "",
            "article_number": self.article_number or "",
            "part_number": self.part_number or "",
            "point_number": self.point_number or "",
            "element_type": self.element_type.value,
            "modality": self.modality.value,
            "legal_concepts": json.dumps(self.legal_concepts, ensure_ascii=False),
            "key_terms": json.dumps(self.key_terms, ensure_ascii=False),
            "numerical_constraints": json.dumps([
                {
                    "value": nc.value,
                    "unit": nc.unit,
                    "operator": nc.operator,
                    "type": nc.constraint_type,
                    "expression": nc.full_expression
                }
                for nc in self.numerical_constraints
            ], ensure_ascii=False),
            "has_constraints": len(self.numerical_constraints) > 0,
            "has_prohibitions": self.modality == ModalityType.PROHIBITION,
            "hierarchy_path": "|".join(self.hierarchy_path),
            "importance_score": self.importance_score,
            "search_keywords": "|".join(self.search_keywords)
        }


class AdvancedLegalChunker:
    """
    Продвинутый чанкер для российских правовых документов.
    Решает проблему потери структуры и численных данных.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Паттерны для российского законодательства
        self.law_patterns = {
            "federal_law": re.compile(
                r'Федеральный\s+закон\s+.*?\s*(\d+)-ФЗ',
                re.IGNORECASE
            ),
            "article": re.compile(
                r'Статья\s+(\d+(?:\.\d+)?)\.',
                re.IGNORECASE
            ),
            "part": re.compile(
                r'(\d+)\.\s+',
                re.MULTILINE
            ),
            "point": re.compile(
                r'(\d+)\)\s+',
                re.MULTILINE
            ),
            "subpoint": re.compile(
                r'([а-я])\)\s+',
                re.MULTILINE
            ),
            "chapter": re.compile(
                r'Глава\s+(\d+(?:\.\d+)?)\.\s+(.+?)(?:\n|$)',
                re.IGNORECASE
            ),
            "section": re.compile(
                r'Раздел\s+([IVXLC]+)\.\s+(.+?)(?:\n|$)',
                re.IGNORECASE
            )
        }

        # Паттерны для численных ограничений
        self.numerical_patterns = {
            "percentage": re.compile(
                r'(не\s+более|не\s+менее|до|свыше|более)?\s*(\d+(?:\.\d+)?)\s*(процент[а-я]*|%)',
                re.IGNORECASE
            ),
            "money": re.compile(
                r'(не\s+более|не\s+менее|до|свыше)?\s*(\d+(?:\s+\d+)*)\s*(рубл[а-я]*|тысяч|миллион[а-я]*)',
                re.IGNORECASE
            ),
            "time_period": re.compile(
                r'(не\s+более|не\s+менее|до|свыше)?\s*(\d+)\s*(лет|года?|месяц[а-я]*|дн[а-я]*)',
                re.IGNORECASE
            ),
            "numeric_limit": re.compile(
                r'(размер|объем|количество|число).*?(не\s+может\s+превышать|не\s+более|до)\s*(\d+(?:\.\d+)?)\s*([а-я%]*)',
                re.IGNORECASE
            )
        }

        # Паттерны модальности
        self.modality_patterns = {
            ModalityType.PROHIBITION: [
                r'не\s+вправе',
                r'не\s+может',
                r'запрещ[а-я]+',
                r'недопустим[а-я]*',
                r'не\s+допускается',
                r'исключается'
            ],
            ModalityType.PERMISSION: [
                r'вправе',
                r'может',
                r'разрешается',
                r'допускается',
                r'имеет\s+право'
            ],
            ModalityType.OBLIGATION: [
                r'должен',
                r'обязан',
                r'необходимо',
                r'требуется',
                r'подлежит',
                r'осуществляется'
            ],
            ModalityType.CONDITIONAL: [
                r'если',
                r'в\s+случае',
                r'при\s+условии',
                r'в\s+том\s+случае',
                r'при\s+наличии'
            ]
        }

        # Ключевые правовые концепции
        self.legal_concepts = {
            "концессионное_соглашение": [
                "концессионное соглашение", "концессия", "концессионер", "концедент"
            ],
            "финансовое_участие": [
                "плата концедента", "капитальный грант", "финансовое участие",
                "возмещение расходов", "субсидия"
            ],
            "объект_концессии": [
                "объект концессионного соглашения", "имущество", "инфраструктура",
                "создание объекта", "реконструкция объекта"
            ],
            "права_и_обязанности": [
                "права концессионера", "обязанности концедента", "ответственность",
                "гарантии", "обеспечение"
            ],
            "досрочное_прекращение": [
                "досрочное расторжение", "прекращение соглашения", "расторжение",
                "последствия прекращения"
            ]
        }

    def chunk_document(self, text: str, document_id: str,
                      law_number: Optional[str] = None) -> List[EnhancedLegalChunk]:
        """
        Основной метод чанкинга правового документа.
        """
        self.logger.info(f"[ADVANCED_CHUNKER] Processing document {document_id}")

        chunks: List[EnhancedLegalChunk] = []

        if not law_number:
            law_number = self._extract_law_number(text)

        section_contexts = self._split_by_sections(text, document_id, law_number)
        if not section_contexts:
            section_contexts = [
                (
                    "",
                    "",
                    "",
                    text,
                )
            ]

        for section_id, section_title, section_number, section_text in section_contexts:
            chapter_contexts = self._split_by_chapters(
                section_text,
                document_id,
                law_number,
                section_number,
                section_title,
            )
            if not chapter_contexts:
                chapter_contexts = [
                    (
                        section_id,
                        section_title,
                        section_number,
                        "",
                        "",
                        section_text,
                    )
                ]

            for (
                base_section_id,
                section_title,
                base_section_number,
                chapter_id,
                chapter_number,
                chapter_title,
                chapter_text,
            ) in chapter_contexts:
                article_chunks = self._split_by_articles(
                    chapter_text,
                    document_id,
                    law_number,
                    section_number=base_section_number,
                    chapter_number=chapter_number,
                )

                for article_chunk in article_chunks:
                    part_chunks = self._split_article_by_parts(article_chunk)
                    final_chunks: List[EnhancedLegalChunk] = []
                    for part_chunk in part_chunks:
                        final_chunks.extend(self._split_part_by_points(part_chunk))

                    for chunk in final_chunks:
                        chunk.section_number = base_section_number or chunk.section_number
                        chunk.chapter_number = chapter_number or chunk.chapter_number
                        if not chunk.parent_context:
                            contexts = []
                            if section_title:
                                contexts.append(section_title)
                            if chapter_title:
                                contexts.append(chapter_title)
                            chunk.parent_context = " | ".join(contexts) if contexts else None
                        chunks.append(chunk)

        for chunk in chunks:
            self._enrich_chunk_metadata(chunk)

        self.logger.info(f"[ADVANCED_CHUNKER] Created {len(chunks)} enhanced chunks")
        return chunks

    def _extract_law_number(self, text: str) -> Optional[str]:
        """Извлечение номера федерального закона."""
        match = self.law_patterns["federal_law"].search(text)
        if match:
            return f"{match.group(1)}-ФЗ"
        return None

    def _split_by_sections(
        self,
        text: str,
        document_id: str,
        law_number: Optional[str],
    ) -> List[Tuple[str, str, str, str]]:
        sections: List[Tuple[str, str, str, str]] = []
        matches = list(self.law_patterns["section"].finditer(text)) if self.law_patterns.get("section") else []
        if not matches:
            return sections

        for idx, match in enumerate(matches):
            section_number = match.group(1)
            section_title = match.group(2).strip()
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()

            sections.append(
                (
                    f"{document_id}_section_{section_number}",
                    section_title,
                    section_number,
                    section_text,
                )
            )
        return sections

    def _split_by_chapters(
        self,
        section_text: str,
        document_id: str,
        law_number: Optional[str],
        section_number: Optional[str],
        section_title: str,
    ) -> List[Tuple[str, str, str, str, str, str, str]]:
        chapters: List[Tuple[str, str, str, str, str, str, str]] = []
        matches = list(self.law_patterns["chapter"].finditer(section_text)) if self.law_patterns.get("chapter") else []
        if not matches:
            return chapters

        for idx, match in enumerate(matches):
            chapter_number = match.group(1)
            chapter_title = match.group(2).strip()
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section_text)
            chapter_text = section_text[start:end].strip()

            chapters.append(
                (
                    f"{document_id}_section_{section_number or '0'}",
                    section_title,
                    section_number or "",
                    f"{document_id}_section_{section_number or '0'}_chapter_{chapter_number}",
                    chapter_number,
                    chapter_title,
                    chapter_text,
                )
            )
        return chapters

    def _split_by_articles(
        self,
        text: str,
        document_id: str,
        law_number: Optional[str],
        section_number: Optional[str] = None,
        chapter_number: Optional[str] = None,
    ) -> List[EnhancedLegalChunk]:
        chunks: List[EnhancedLegalChunk] = []
        article_matches = list(self.law_patterns["article"].finditer(text))

        for i, match in enumerate(article_matches):
            article_number = match.group(1)
            start = match.start()
            end = article_matches[i + 1].start() if i + 1 < len(article_matches) else len(text)
            content = text[start:end].strip()

            chunk = EnhancedLegalChunk(
                content=content,
                chunk_id=f"{document_id}_article_{article_number}",
                document_id=document_id,
                law_number=law_number,
                section_number=section_number,
                chapter_number=chapter_number,
                article_number=article_number,
                element_type=LegalElementType.ARTICLE,
                parent_context="".join(
                    filter(
                        None,
                        [
                            f"Раздел {section_number}" if section_number else None,
                            f"Глава {chapter_number}" if chapter_number else None,
                        ],
                    )
                ) or None,
                hierarchy_path=[
                    law_number or "unknown",
                    *(
                        [f"раздел {section_number}"]
                        if section_number
                        else []
                    ),
                    *([
                        f"глава {chapter_number}"
                    ] if chapter_number else []),
                    f"статья {article_number}",
                ],
            )
            chunks.append(chunk)

        return chunks

    def _split_article_by_parts(self, article_chunk: EnhancedLegalChunk) -> List[EnhancedLegalChunk]:
        chunks: List[EnhancedLegalChunk] = []
        content = article_chunk.content
        part_matches = list(self.law_patterns["part"].finditer(content))

        if not part_matches:
            return [article_chunk]

        for i, match in enumerate(part_matches):
            part_number = match.group(1)
            start = match.start()
            end = part_matches[i + 1].start() if i + 1 < len(part_matches) else len(content)
            part_content = content[start:end].strip()

            chunk = EnhancedLegalChunk(
                content=part_content,
                chunk_id=f"{article_chunk.chunk_id}_part_{part_number}",
                document_id=article_chunk.document_id,
                law_number=article_chunk.law_number,
                section_number=article_chunk.section_number,
                chapter_number=article_chunk.chapter_number,
                article_number=article_chunk.article_number,
                part_number=part_number,
                element_type=LegalElementType.PART,
                parent_context=
                    " ".join(
                        filter(
                            None,
                            [
                                f"Статья {article_chunk.article_number}",
                                f"Раздел {article_chunk.section_number}" if article_chunk.section_number else None,
                                f"Глава {article_chunk.chapter_number}" if article_chunk.chapter_number else None,
                            ],
                        )
                    )
                ,
                hierarchy_path=article_chunk.hierarchy_path + [f"часть {part_number}"],
            )
            chunks.append(chunk)

        return chunks

    def _split_part_by_points(self, part_chunk: EnhancedLegalChunk) -> List[EnhancedLegalChunk]:
        content = part_chunk.content
        point_matches = list(self.law_patterns["point"].finditer(content))
        if not point_matches:
            return [part_chunk]

        chunks: List[EnhancedLegalChunk] = []
        for i, match in enumerate(point_matches):
            point_number = match.group(1)
            start = match.start()
            end = point_matches[i + 1].start() if i + 1 < len(point_matches) else len(content)
            point_content = content[start:end].strip()

            chunk = EnhancedLegalChunk(
                content=point_content,
                chunk_id=f"{part_chunk.chunk_id}_point_{point_number}",
                document_id=part_chunk.document_id,
                law_number=part_chunk.law_number,
                section_number=part_chunk.section_number,
                chapter_number=part_chunk.chapter_number,
                article_number=part_chunk.article_number,
                part_number=part_chunk.part_number,
                point_number=point_number,
                element_type=LegalElementType.POINT,
                parent_context=" ".join(
                    filter(
                        None,
                        [
                            f"Часть {part_chunk.part_number}",
                            f"Статья {part_chunk.article_number}" if part_chunk.article_number else None,
                            f"Раздел {part_chunk.section_number}" if part_chunk.section_number else None,
                        ],
                    )
                ),
                hierarchy_path=part_chunk.hierarchy_path + [f"пункт {point_number}"],
            )
            chunks.append(chunk)

        final_chunks: List[EnhancedLegalChunk] = []
        for candidate in chunks:
            final_chunks.extend(self._split_point_by_subpoints(candidate))
        return final_chunks

    def _split_point_by_subpoints(self, point_chunk: EnhancedLegalChunk) -> List[EnhancedLegalChunk]:
        content = point_chunk.content
        subpoint_matches = list(self.law_patterns["subpoint"].finditer(content))
        if not subpoint_matches:
            return [point_chunk]

        chunks: List[EnhancedLegalChunk] = []
        for i, match in enumerate(subpoint_matches):
            subpoint_number = match.group(1)
            start = match.start()
            end = subpoint_matches[i + 1].start() if i + 1 < len(subpoint_matches) else len(content)
            subpoint_content = content[start:end].strip()

            chunk = EnhancedLegalChunk(
                content=subpoint_content,
                chunk_id=f"{point_chunk.chunk_id}_subpoint_{subpoint_number}",
                document_id=point_chunk.document_id,
                law_number=point_chunk.law_number,
                section_number=point_chunk.section_number,
                chapter_number=point_chunk.chapter_number,
                article_number=point_chunk.article_number,
                part_number=point_chunk.part_number,
                point_number=point_chunk.point_number,
                subpoint_number=subpoint_number,
                element_type=LegalElementType.SUBPOINT,
                parent_context=" ".join(
                    filter(
                        None,
                        [
                            f"Пункт {point_chunk.point_number}",
                            f"Часть {point_chunk.part_number}" if point_chunk.part_number else None,
                        ],
                    )
                ),
                hierarchy_path=point_chunk.hierarchy_path + [f"подпункт {subpoint_number}"],
            )
            chunks.append(chunk)

        return chunks

    def _enrich_chunk_metadata(self, chunk: EnhancedLegalChunk):
        """Обогащение чанка метаданными."""
        content = chunk.content.lower()

        # Определение модальности
        chunk.modality = self._detect_modality(content)

        # Извлечение численных ограничений
        chunk.numerical_constraints = self._extract_numerical_constraints(chunk.content)

        # Извлечение правовых концепций
        chunk.legal_concepts = self._extract_legal_concepts(content)

        # Извлечение ключевых терминов
        chunk.key_terms = self._extract_key_terms(content)

        # Поиск правовых ссылок
        chunk.legal_references = self._extract_legal_references(chunk.content)

        # Создание поисковых ключевых слов
        chunk.search_keywords = self._generate_search_keywords(chunk)

        # Расчет важности
        chunk.importance_score = self._calculate_importance_score(chunk)

    def _detect_modality(self, content: str) -> ModalityType:
        """Определение правовой модальности текста."""
        for modality, patterns in self.modality_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return modality
        return ModalityType.NEUTRAL

    def _extract_numerical_constraints(self, content: str) -> List[NumericalConstraint]:
        """Извлечение численных ограничений."""
        constraints = []

        for constraint_type, pattern in self.numerical_patterns.items():
            matches = pattern.finditer(content)
            for match in matches:
                groups = match.groups()

                if constraint_type == "percentage":
                    operator = groups[0] or ""
                    value = groups[1]
                    unit = "процент" if "процент" in groups[2] else "%"

                    constraint = NumericalConstraint(
                        value=value,
                        unit=unit,
                        operator=operator.strip(),
                        context=match.group(0),
                        constraint_type="процент",
                        full_expression=match.group(0)
                    )
                    constraints.append(constraint)

                elif constraint_type == "time_period":
                    operator = groups[0] or ""
                    value = groups[1]
                    unit = groups[2]

                    constraint = NumericalConstraint(
                        value=value,
                        unit=unit,
                        operator=operator.strip(),
                        context=match.group(0),
                        constraint_type="срок",
                        full_expression=match.group(0)
                    )
                    constraints.append(constraint)

        return constraints

    def _extract_legal_concepts(self, content: str) -> List[str]:
        """Извлечение правовых концепций."""
        concepts = []

        for concept, terms in self.legal_concepts.items():
            for term in terms:
                if term.lower() in content:
                    concepts.append(concept)
                    break

        return concepts

    def _extract_key_terms(self, content: str) -> List[str]:
        """Извлечение ключевых правовых терминов."""
        # Простая эвристика: существительные в правовом контексте
        legal_terms_pattern = re.compile(
            r'\b([а-я]{4,}(?:ние|тие|ость|ство|ция|сия))\b',
            re.IGNORECASE
        )

        terms = []
        matches = legal_terms_pattern.finditer(content)
        for match in matches:
            term = match.group(1).lower()
            if term not in terms and len(term) > 4:
                terms.append(term)

        return terms[:10] # Ограничиваем количество

    def _extract_legal_references(self, content: str) -> List[LegalReference]:
        """Извлечение ссылок на другие правовые нормы."""
        references = []

        # Паттерн для ссылок вида "статья 10.1"
        article_ref_pattern = re.compile(
            r'стать[а-я]*\s+(\d+(?:\.\d+)?)',
            re.IGNORECASE
        )

        matches = article_ref_pattern.finditer(content)
        for match in matches:
            reference = LegalReference(
                article=match.group(1),
                full_reference=match.group(0),
                reference_type="internal"
            )
            references.append(reference)

        return references

    def _generate_search_keywords(self, chunk: EnhancedLegalChunk) -> List[str]:
        """Генерация ключевых слов для поиска."""
        keywords = []

        # Структурные ключевые слова
        if chunk.article_number:
            keywords.append(f"статья_{chunk.article_number}")
        if chunk.part_number:
            keywords.append(f"часть_{chunk.part_number}")

        # Концептуальные ключевые слова
        keywords.extend(chunk.legal_concepts)

        # Модальность
        if chunk.modality != ModalityType.NEUTRAL:
            keywords.append(chunk.modality.value)

        # Численные ограничения
        if chunk.numerical_constraints:
            keywords.append("численные_ограничения")
            for constraint in chunk.numerical_constraints:
                if constraint.constraint_type == "процент":
                    keywords.append("процентные_ограничения")

        return keywords

    def _calculate_importance_score(self, chunk: EnhancedLegalChunk) -> float:
        """Расчет коэффициента важности чанка."""
        score = 1.0

        # Увеличиваем важность для чанков с численными ограничениями
        if chunk.numerical_constraints:
            score += 0.5

        # Увеличиваем важность для запретов
        if chunk.modality == ModalityType.PROHIBITION:
            score += 0.3

        # Увеличиваем важность для ключевых концепций
        important_concepts = ["финансовое_участие", "досрочное_прекращение"]
        for concept in chunk.legal_concepts:
            if concept in important_concepts:
                score += 0.2

        return min(score, 2.0) # Максимальный score 2.0