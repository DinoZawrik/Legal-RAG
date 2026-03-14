#!/usr/bin/env python3
"""
Legal Document Chunker
Улучшенная система чанкинга с учетом правовой структуры документов.

Обеспечивает:
- Сохранение целостности правовых норм
- Понимание иерархии (статья пункт подпункт)
- Контекстуальные связи между элементами
- Метаданные структуры для каждого чанка
"""

import logging
import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

from core.legal_ontology import get_legal_ontology, DocumentType, LegalDomain
from core.infrastructure_suite import TextChunk

logger = logging.getLogger(__name__)


class StructureLevel(Enum):
    """Уровни структуры правового документа."""
    DOCUMENT = "document"
    CHAPTER = "chapter"
    SECTION = "section"
    ARTICLE = "article"
    PARAGRAPH = "paragraph"
    SUBPARAGRAPH = "subparagraph"
    ITEM = "item"


@dataclass
class LegalStructureMetadata:
    """Метаданные правовой структуры чанка."""
    structure_level: StructureLevel
    article_number: Optional[str] = None
    paragraph_number: Optional[str] = None
    subparagraph_number: Optional[str] = None
    item_number: Optional[str] = None
    chapter_title: Optional[str] = None
    section_title: Optional[str] = None
    parent_context: Optional[str] = None
    children_count: int = 0
    hierarchy_path: List[str] = None


@dataclass
class LegalChunk:
    """Расширенный чанк с правовыми метаданными."""
    content: str
    structure_metadata: LegalStructureMetadata
    document_type: DocumentType
    legal_domain: LegalDomain
    references: List[str]
    key_terms: List[str]
    start_position: int
    end_position: int
    chunk_id: str
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: List[str] = None


class LegalDocumentChunker:
    """
    Улучшенная система чанкинга для правовых документов.

    Особенности:
    - Понимание правовой структуры
    - Сохранение контекстуальных связей
    - Адаптивный размер чанков
    - Метаданные иерархии
    """

    def __init__(self,
                 base_chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 min_chunk_size: int = 100,
                 max_chunk_size: int = 2000):
        """
        Инициализация чанкера.

        Args:
            base_chunk_size: Базовый размер чанка
            chunk_overlap: Размер перекрытия
            min_chunk_size: Минимальный размер чанка
            max_chunk_size: Максимальный размер чанка
        """
        self.base_chunk_size = base_chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.legal_ontology = get_legal_ontology()

        # Паттерны для распознавания структуры
        self.structure_patterns = self._load_structure_patterns()

        # Паттерны критически важных числовых ограничений
        self.critical_numerical_patterns = self._load_critical_numerical_patterns()

        logger.info(" Legal Document Chunker инициализирован")

    def _load_structure_patterns(self) -> Dict[StructureLevel, List[str]]:
        """Загрузка паттернов для распознавания структуры."""
        return {
            StructureLevel.CHAPTER: [
                r"^Глава\s+([IVXLC]+|\d+)\.?\s*(.+)$",
                r"^ГЛАВА\s+([IVXLC]+|\d+)\.?\s*(.+)$",
                r"^Раздел\s+([IVXLC]+|\d+)\.?\s*(.+)$"
            ],

            StructureLevel.SECTION: [
                r"^§\s*(\d+)\.?\s*(.+)$",
                r"^Параграф\s+(\d+)\.?\s*(.+)$",
                r"^Подраздел\s+(\d+)\.?\s*(.+)$"
            ],

            StructureLevel.ARTICLE: [
                r"^Статья\s+(\d+(?:\.\d+)*)\.?\s*(.*)$",
                r"^Ст\.\s*(\d+(?:\.\d+)*)\.?\s*(.*)$",
                r"^(\d+(?:\.\d+)*)\.?\s+(.+)$" # Простая нумерация
            ],

            StructureLevel.PARAGRAPH: [
                r"^(\d+)\.?\s+(.+)$",
                r"^(\d+)\)\s+(.+)$",
                r"^\((\d+)\)\s+(.+)$"
            ],

            StructureLevel.SUBPARAGRAPH: [
                r"^([а-я])\)\s+(.+)$",
                r"^\(([а-я])\)\s+(.+)$",
                r"^([а-я])\.?\s+(.+)$"
            ],

            StructureLevel.ITEM: [
                r"^-\s+(.+)$",
                r"^\*\s+(.+)$",
                r"^•\s+(.+)$",
                r"^(\w+)\s*:\s*(.+)$" # Определения
            ]
        }

    def _load_critical_numerical_patterns(self) -> List[str]:
        """Загрузка паттернов критически важных числовых ограничений."""
        return [
            # Процентные ограничения
            r'(?:размер|сумма|объем).{0,50}(?:не\s+)?может\s+превышать\s+восемьдесят\s+процент[а-я]*',
            r'(?:размер|сумма|объем).{0,50}(?:не\s+)?может\s+превышать\s+80\s*%',
            r'капитальный\s+грант.{0,50}не\s+может\s+превышать\s+восемьдесят\s+процент[а-я]*',
            r'капитальный\s+грант.{0,50}не\s+может\s+превышать\s+80\s*%',

            # Временные ограничения
            r'срок.{0,50}не\s+менее\s+(?:чем\s+)?три\s+года',
            r'срок.{0,50}не\s+менее\s+(?:чем\s+)?3\s+лет',
            r'минимальный\s+срок.{0,30}три\s+года',

            # Предельные размеры
            r'предельный\s+размер.{0,100}финансового?\s+участия',
            r'максимальный\s+размер.{0,100}(?:гранта|участия|финансирования)',
            r'ограничение.{0,50}процент[а-я]*',

            # Статьи с числовыми ограничениями (проблемные случаи)
            r'статья\s+10\.1.{0,200}восемьдесят\s+процент[а-я]*',
            r'статья\s+12\.1.{0,200}восемьдесят\s+процент[а-я]*',
            r'статья\s+3.{0,200}не\s+менее.{0,50}три\s+года'
        ]

    def chunk_legal_document(self,
                           text: str,
                           document_type: DocumentType,
                           filename: str = "",
                           preserve_structure: bool = True) -> List[LegalChunk]:
        """
        Разбиение правового документа на чанки с сохранением структуры.

        Args:
            text: Текст документа
            document_type: Тип документа
            filename: Имя файла
            preserve_structure: Сохранять ли структуру

        Returns:
            Список чанков с метаданными
        """
        logger.info(f" Чанкинг документа {filename}, тип: {document_type.value}")

        # 1. Определение правовой отрасли
        legal_domain, _ = self.legal_ontology.get_legal_domain(text)

        # 2. Анализ структуры документа
        structure_map = self._analyze_document_structure(text) if preserve_structure else {}

        # 3. Разбиение на базовые сегменты
        if preserve_structure and structure_map:
            segments = self._split_by_structure(text, structure_map)
        else:
            segments = self._split_by_sentences(text)

        # 4. Создание чанков с метаданными
        chunks = []
        current_position = 0

        for i, segment in enumerate(segments):
            # Определение структурных метаданных
            structure_metadata = self._extract_structure_metadata(
                segment, current_position, structure_map
            )

            # Извлечение ссылок и терминов
            references = self.legal_ontology.extract_legal_references(segment)
            ref_strings = [f"статья {ref.article}" for ref in references if ref.article]

            key_terms = self._extract_key_terms(segment)

            # Создание чанка
            chunk = LegalChunk(
                content=segment,
                structure_metadata=structure_metadata,
                document_type=document_type,
                legal_domain=legal_domain,
                references=ref_strings,
                key_terms=key_terms,
                start_position=current_position,
                end_position=current_position + len(segment),
                chunk_id=f"{filename}_{i}",
                child_chunk_ids=[]
            )

            chunks.append(chunk)
            current_position += len(segment)

        # 5. Установка связей между чанками
        self._establish_chunk_relationships(chunks)

        # 6. Оптимизация размеров чанков
        optimized_chunks = self._optimize_chunk_sizes(chunks)

        logger.info(f" Создано {len(optimized_chunks)} чанков для документа {filename}")
        return optimized_chunks

    def _analyze_document_structure(self, text: str) -> Dict[int, Dict[str, Any]]:
        """
        Анализ структуры документа.

        Args:
            text: Текст документа

        Returns:
            Карта структуры документа
        """
        structure_map = {}
        lines = text.split('\n')

        current_chapter = None
        current_section = None
        current_article = None

        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Поиск структурных элементов
            for level, patterns in self.structure_patterns.items():
                for pattern in patterns:
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match:
                        groups = match.groups()

                        structure_info = {
                            'level': level,
                            'line_number': line_num,
                            'text': line,
                            'number': groups[0] if groups else None,
                            'title': groups[1] if len(groups) > 1 else None
                        }

                        # Обновление текущего контекста
                        if level == StructureLevel.CHAPTER:
                            current_chapter = structure_info
                            current_section = None
                            current_article = None
                        elif level == StructureLevel.SECTION:
                            current_section = structure_info
                            current_article = None
                        elif level == StructureLevel.ARTICLE:
                            current_article = structure_info

                        # Добавление контекстной информации
                        structure_info['parent_chapter'] = current_chapter
                        structure_info['parent_section'] = current_section
                        structure_info['parent_article'] = current_article

                        structure_map[line_num] = structure_info
                        break

        return structure_map

    def _split_by_structure(self, text: str, structure_map: Dict[int, Dict[str, Any]]) -> List[str]:
        """
        Разбиение текста по структурным элементам.

        Args:
            text: Текст документа
            structure_map: Карта структуры

        Returns:
            Список сегментов
        """
        lines = text.split('\n')
        segments = []
        current_segment = []

        # Сортируем структурные элементы по номеру строки
        structure_points = sorted(structure_map.keys())

        current_structure_idx = 0

        for line_num, line in enumerate(lines):
            # Проверяем, начинается ли новый структурный элемент
            if (current_structure_idx < len(structure_points) and
                line_num == structure_points[current_structure_idx]):

                # Сохраняем предыдущий сегмент
                if current_segment:
                    segment_text = '\n'.join(current_segment).strip()
                    if len(segment_text) > self.min_chunk_size:
                        segments.append(segment_text)
                    current_segment = []

                current_structure_idx += 1

            current_segment.append(line)

            # Проверяем размер текущего сегмента
            current_text = '\n'.join(current_segment)
            if len(current_text) > self.max_chunk_size:
                # Разбиваем по предложениям
                sentence_chunks = self._split_large_segment(current_text)
                segments.extend(sentence_chunks)
                current_segment = []

        # Добавляем последний сегмент
        if current_segment:
            segment_text = '\n'.join(current_segment).strip()
            if len(segment_text) > self.min_chunk_size:
                segments.append(segment_text)

        return segments

    def _split_by_sentences(self, text: str) -> List[str]:
        """
        Разбиение текста по предложениям (fallback метод).

        Args:
            text: Текст для разбиения

        Returns:
            Список сегментов
        """
        # Разбиение по предложениям с учетом правовой специфики
        sentence_endings = r'[.!?]\s+(?=[А-ЯЁ])'
        sentences = re.split(sentence_endings, text)

        segments = []
        current_segment = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Проверяем, поместится ли предложение в текущий сегмент
            potential_segment = current_segment + " " + sentence if current_segment else sentence

            if len(potential_segment) <= self.base_chunk_size:
                current_segment = potential_segment
            else:
                # Сохраняем текущий сегмент
                if current_segment:
                    segments.append(current_segment.strip())

                # Если предложение слишком длинное, разбиваем его
                if len(sentence) > self.max_chunk_size:
                    sub_segments = self._split_large_segment(sentence)
                    segments.extend(sub_segments)
                    current_segment = ""
                else:
                    current_segment = sentence

        # Добавляем последний сегмент
        if current_segment:
            segments.append(current_segment.strip())

        return segments

    def _split_large_segment(self, text: str) -> List[str]:
        """
        Разбиение слишком большого сегмента.

        Args:
            text: Текст для разбиения

        Returns:
            Список подсегментов
        """
        # Разбиение по запятым и точкам с запятой
        parts = re.split(r'[;,]\s+', text)

        segments = []
        current_segment = ""

        for part in parts:
            potential_segment = current_segment + ", " + part if current_segment else part

            if len(potential_segment) <= self.base_chunk_size:
                current_segment = potential_segment
            else:
                if current_segment:
                    segments.append(current_segment.strip())

                if len(part) > self.max_chunk_size:
                    # Принудительное разбиение по словам
                    word_segments = self._split_by_words(part)
                    segments.extend(word_segments)
                    current_segment = ""
                else:
                    current_segment = part

        if current_segment:
            segments.append(current_segment.strip())

        return segments

    def _split_by_words(self, text: str) -> List[str]:
        """
        Принудительное разбиение по словам.

        Args:
            text: Текст для разбиения

        Returns:
            Список сегментов
        """
        words = text.split()
        segments = []
        current_segment = []
        current_length = 0

        for word in words:
            word_length = len(word) + 1 # +1 для пробела

            if current_length + word_length <= self.base_chunk_size:
                current_segment.append(word)
                current_length += word_length
            else:
                if current_segment:
                    segments.append(' '.join(current_segment))
                current_segment = [word]
                current_length = len(word)

        if current_segment:
            segments.append(' '.join(current_segment))

        return segments

    def _extract_structure_metadata(self,
                                  segment: str,
                                  position: int,
                                  structure_map: Dict[int, Dict[str, Any]]) -> LegalStructureMetadata:
        """
        Извлечение метаданных структуры для сегмента.

        Args:
            segment: Текст сегмента
            position: Позиция в документе
            structure_map: Карта структуры

        Returns:
            Метаданные структуры
        """
        # Поиск ближайшего структурного элемента
        closest_structure = None
        min_distance = float('inf')

        for line_num, structure_info in structure_map.items():
            distance = abs(position - line_num * 50) # Приблизительная позиция строки
            if distance < min_distance:
                min_distance = distance
                closest_structure = structure_info

        if closest_structure:
            level = closest_structure['level']
            hierarchy_path = self._build_hierarchy_path(closest_structure)

            return LegalStructureMetadata(
                structure_level=level,
                article_number=closest_structure.get('number') if level == StructureLevel.ARTICLE else None,
                chapter_title=closest_structure.get('title') if level == StructureLevel.CHAPTER else None,
                section_title=closest_structure.get('title') if level == StructureLevel.SECTION else None,
                hierarchy_path=hierarchy_path
            )
        else:
            # Попытка определить структуру из содержимого
            return self._infer_structure_from_content(segment)

    def _build_hierarchy_path(self, structure_info: Dict[str, Any]) -> List[str]:
        """
        Построение пути иерархии для структурного элемента.

        Args:
            structure_info: Информация о структурном элементе

        Returns:
            Путь иерархии
        """
        path = []

        if structure_info.get('parent_chapter'):
            chapter = structure_info['parent_chapter']
            path.append(f"Глава {chapter.get('number', '')}: {chapter.get('title', '')}")

        if structure_info.get('parent_section'):
            section = structure_info['parent_section']
            path.append(f"Раздел {section.get('number', '')}: {section.get('title', '')}")

        if structure_info.get('parent_article'):
            article = structure_info['parent_article']
            path.append(f"Статья {article.get('number', '')}")

        return path

    def _infer_structure_from_content(self, segment: str) -> LegalStructureMetadata:
        """
        Определение структуры из содержимого сегмента.

        Args:
            segment: Текст сегмента

        Returns:
            Инferred метаданные структуры
        """
        lines = segment.split('\n')
        first_line = lines[0].strip() if lines else ""

        # Проверка паттернов в первой строке
        for level, patterns in self.structure_patterns.items():
            for pattern in patterns:
                match = re.match(pattern, first_line, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    return LegalStructureMetadata(
                        structure_level=level,
                        article_number=groups[0] if level == StructureLevel.ARTICLE and groups else None
                    )

        # Определение по умолчанию
        return LegalStructureMetadata(structure_level=StructureLevel.PARAGRAPH)

    def _extract_key_terms(self, text: str) -> List[str]:
        """
        Извлечение ключевых терминов из текста.

        Args:
            text: Текст для анализа

        Returns:
            Список ключевых терминов
        """
        text_lower = text.lower()
        key_terms = []

        # Термины из правовой онтологии
        for term in self.legal_ontology.LEGAL_SYNONYMS.keys():
            if term in text_lower:
                key_terms.append(term)

        # Аббревиатуры
        for abbr in self.legal_ontology.ABBREVIATIONS.keys():
            if abbr in text_lower:
                key_terms.append(abbr)

        # КРИТИЧНО: Числовые ограничения и временные рамки
        numerical_patterns = [
            r'восемьдесят\s+процент[а-я]*',
            r'80\s*%',
            r'не\s+может\s+превышать\s+восемьдесят\s+процент[а-я]*',
            r'не\s+менее\s+(?:чем\s+)?три\s+года',
            r'не\s+менее\s+(?:чем\s+)?3\s+лет',
            r'минимальный\s+срок.*три\s+года',
            r'срок.*не\s+менее.*года',
            r'размер.*не\s+может\s+превышать',
            r'предельный\s+размер',
            r'ограничение.*процент[а-я]*',
            r'максимальный\s+размер',
            r'минимальный\s+размер'
        ]

        for pattern in numerical_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                key_terms.append(match.strip())

        return list(set(key_terms))

    def _establish_chunk_relationships(self, chunks: List[LegalChunk]) -> None:
        """
        Установка связей между чанками.

        Args:
            chunks: Список чанков для установки связей
        """
        for i, chunk in enumerate(chunks):
            # Связь с предыдущим чанком
            if i > 0:
                prev_chunk = chunks[i - 1]
                # Если чанки относятся к одной структурной единице
                if (chunk.structure_metadata.article_number ==
                    prev_chunk.structure_metadata.article_number):
                    chunk.parent_chunk_id = prev_chunk.chunk_id
                    prev_chunk.child_chunk_ids.append(chunk.chunk_id)

    def _optimize_chunk_sizes(self, chunks: List[LegalChunk]) -> List[LegalChunk]:
        """
        Оптимизация размеров чанков.

        Args:
            chunks: Исходные чанки

        Returns:
            Оптимизированные чанки
        """
        optimized = []
        i = 0

        while i < len(chunks):
            current_chunk = chunks[i]

            # Если чанк слишком маленький, пытаемся объединить с следующим
            if (len(current_chunk.content) < self.min_chunk_size and
                i + 1 < len(chunks)):

                next_chunk = chunks[i + 1]

                # Объединяем, если чанки связаны структурно
                if (current_chunk.structure_metadata.article_number ==
                    next_chunk.structure_metadata.article_number):

                    merged_content = current_chunk.content + "\n\n" + next_chunk.content

                    if len(merged_content) <= self.max_chunk_size:
                        # Создаем объединенный чанк
                        merged_chunk = LegalChunk(
                            content=merged_content,
                            structure_metadata=current_chunk.structure_metadata,
                            document_type=current_chunk.document_type,
                            legal_domain=current_chunk.legal_domain,
                            references=list(set(current_chunk.references + next_chunk.references)),
                            key_terms=list(set(current_chunk.key_terms + next_chunk.key_terms)),
                            start_position=current_chunk.start_position,
                            end_position=next_chunk.end_position,
                            chunk_id=current_chunk.chunk_id,
                            parent_chunk_id=current_chunk.parent_chunk_id,
                            child_chunk_ids=current_chunk.child_chunk_ids + next_chunk.child_chunk_ids
                        )

                        optimized.append(merged_chunk)
                        i += 2 # Пропускаем следующий чанк
                        continue

            optimized.append(current_chunk)
            i += 1

        return optimized

    def convert_to_text_chunks(self, legal_chunks: List[LegalChunk]) -> List[TextChunk]:
        """
        Конвертация LegalChunk в TextChunk для совместимости.

        Args:
            legal_chunks: Список правовых чанков

        Returns:
            Список TextChunk объектов
        """
        text_chunks = []

        for legal_chunk in legal_chunks:
            # Создаем метаданные для TextChunk
            metadata = {
                'document_type': legal_chunk.document_type.value,
                'legal_domain': legal_chunk.legal_domain.value,
                'structure_level': legal_chunk.structure_metadata.structure_level.value,
                'article_number': legal_chunk.structure_metadata.article_number,
                'hierarchy_path': legal_chunk.structure_metadata.hierarchy_path,
                'references': legal_chunk.references,
                'key_terms': legal_chunk.key_terms,
                'chunk_id': legal_chunk.chunk_id
            }

            text_chunk = TextChunk(
                content=legal_chunk.content,
                metadata=metadata,
                start_position=legal_chunk.start_position,
                end_position=legal_chunk.end_position
            )

            text_chunks.append(text_chunk)

        return text_chunks


# Глобальный экземпляр чанкера
_legal_chunker = None

def get_legal_chunker() -> LegalDocumentChunker:
    """Получение глобального экземпляра правового чанкера."""
    global _legal_chunker
    if _legal_chunker is None:
        _legal_chunker = LegalDocumentChunker()
    return _legal_chunker


if __name__ == "__main__":
    # Демонстрация возможностей чанкера
    print(" Legal Document Chunker - Демонстрация")
    print("=" * 50)

    chunker = LegalDocumentChunker()

    # Тестовый правовой текст
    test_text = """
    Глава 1. ОБЩИЕ ПОЛОЖЕНИЯ

    Статья 1. Основные понятия

    1. В настоящем Федеральном законе используются следующие основные понятия:
    а) контрактная система - совокупность участников контрактной системы;
    б) закупка товара, работы, услуги для обеспечения государственных нужд;

    2. Контракт - гражданско-правовой договор, заключенный от имени Российской Федерации.

    Статья 2. Принципы контрактной системы

    1. Контрактная система в сфере закупок основывается на принципах:
    а) обеспечения конкуренции;
    б) профессионализма заказчиков;
    в) стимулирования инноваций.
    """

    # Тестирование чанкинга
    legal_chunks = chunker.chunk_legal_document(
        text=test_text,
        document_type=DocumentType.FEDERAL_LAW,
        filename="test_law.txt"
    )

    print(f"\n Создано {len(legal_chunks)} чанков")

    for i, chunk in enumerate(legal_chunks):
        print(f"\n Чанк {i + 1}:")
        print(f" Уровень структуры: {chunk.structure_metadata.structure_level.value}")
        if chunk.structure_metadata.article_number:
            print(f" Статья: {chunk.structure_metadata.article_number}")
        print(f" Размер: {len(chunk.content)} символов")
        print(f" Ключевые термины: {chunk.key_terms}")
        print(f" Ссылки: {chunk.references}")
        print(f" Содержимое: {chunk.content[:100]}...")

    # Конвертация в TextChunk
    text_chunks = chunker.convert_to_text_chunks(legal_chunks)
    print(f"\n Конвертировано в {len(text_chunks)} TextChunk объектов")