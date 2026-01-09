#!/usr/bin/env python3
"""
Иерархический chunking для российского законодательства
КРИТИЧЕСКОЕ УЛУЧШЕНИЕ: Сохранение структуры правовых документов
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import uuid

from core.infrastructure_suite import TextChunk


@dataclass
class LegalStructure:
    """Структурный элемент правового документа"""
    type: str  # 'law', 'chapter', 'article', 'paragraph', 'subparagraph'
    number: str
    title: Optional[str]
    content: str
    parent_id: Optional[str] = None
    hierarchy_path: str = ""


class RussianLegalChunker:
    """
    Chunker для российских правовых документов
    Сохраняет иерархическую структуру законов
    """

    def __init__(self):
        # Паттерны для российского законодательства
        self.legal_patterns = {
            'federal_law': r'Федеральный\s+закон\s+от\s+[\d\.]+\s+N\s+([\d\-ФЗ]+)',
            'chapter': r'(?:Глава|ГЛАВА)\s+([IVXLCDM]+|\d+(?:\.\d+)*)\.\s*(.+?)(?=\n|$)',
            'section': r'(?:Раздел|РАЗДЕЛ)\s+([IVXLCDM]+|\d+(?:\.\d+)*)\.\s*(.+?)(?=\n|$)',
            'article': r'Статья\s+(\d+(?:\.\d+)*)\.\s*(.+?)(?=\n|$)',
            'paragraph': r'^(\d+)\.\s+(.+?)(?=\n\d+\.\s+|\n\n|\nСтатья|\nГлава|\Z)',
            'subparagraph': r'^(\d+)\)\s+(.+?)(?=\n\d+\)\s+|\n\d+\.\s+|\n\n|\nСтатья|\nГлава|\Z)',
            'item': r'^([а-я]\))\s+(.+?)(?=\n[а-я]\)\s+|\n\d+\)\s+|\n\d+\.\s+|\n\n|\nСтатья|\nГлава|\Z)'
        }

        # Максимальные размеры для разных типов чанков
        self.chunk_limits = {
            'complete_article': 2000,    # Полная статья
            'article_paragraph': 1200,   # Пункт статьи
            'article_fragment': 800,     # Фрагмент статьи
            'context_chunk': 1500        # Чанк с контекстом
        }

    def chunk_legal_document(self, text: str, metadata: dict) -> List[TextChunk]:
        """
        Основной метод chunking российского правового документа
        """
        chunks = []
        law_number = self._extract_law_number(text, metadata)

        # 1. Парсинг структуры документа
        structure = self._parse_document_structure(text)

        # 2. Создание чанков на основе структуры
        for element in structure:
            element_chunks = self._create_chunks_from_element(element, law_number, metadata)
            chunks.extend(element_chunks)

        # 3. Создание дополнительных контекстных чанков для длинных статей
        context_chunks = self._create_context_chunks(structure, law_number, metadata)
        chunks.extend(context_chunks)

        # 4. Добавление метаданных иерархии
        self._enrich_with_hierarchy_metadata(chunks)

        return chunks

    def _extract_law_number(self, text: str, metadata: dict) -> str:
        """Извлечение номера закона"""
        if 'law_number' in metadata:
            return metadata['law_number']

        # Поиск в тексте
        federal_law_match = re.search(self.legal_patterns['federal_law'], text)
        if federal_law_match:
            return federal_law_match.group(1)

        return "unknown_law"

    def _parse_document_structure(self, text: str) -> List[LegalStructure]:
        """Парсинг иерархической структуры документа"""
        structures = []
        current_chapter = None
        current_section = None

        lines = text.split('\n')
        current_text = ""
        current_article = None

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Поиск главы
            chapter_match = re.match(self.legal_patterns['chapter'], line)
            if chapter_match:
                current_chapter = LegalStructure(
                    type='chapter',
                    number=chapter_match.group(1),
                    title=chapter_match.group(2).strip(),
                    content=line,
                    hierarchy_path=f"Глава {chapter_match.group(1)}"
                )
                structures.append(current_chapter)
                i += 1
                continue

            # Поиск раздела
            section_match = re.match(self.legal_patterns['section'], line)
            if section_match:
                current_section = LegalStructure(
                    type='section',
                    number=section_match.group(1),
                    title=section_match.group(2).strip(),
                    content=line,
                    parent_id=current_chapter.number if current_chapter else None,
                    hierarchy_path=f"Раздел {section_match.group(1)}"
                )
                structures.append(current_section)
                i += 1
                continue

            # Поиск статьи
            article_match = re.match(self.legal_patterns['article'], line)
            if article_match:
                article_number = article_match.group(1)
                article_title = article_match.group(2).strip()

                # Собираем содержимое статьи
                article_content = line + "\n"
                i += 1

                # Читаем содержимое до следующей статьи/главы
                while i < len(lines):
                    next_line = lines[i].strip()
                    if (re.match(self.legal_patterns['article'], next_line) or
                        re.match(self.legal_patterns['chapter'], next_line) or
                        re.match(self.legal_patterns['section'], next_line)):
                        break
                    article_content += lines[i] + "\n"
                    i += 1

                current_article = LegalStructure(
                    type='article',
                    number=article_number,
                    title=article_title,
                    content=article_content.strip(),
                    parent_id=current_section.number if current_section else (current_chapter.number if current_chapter else None),
                    hierarchy_path=f"Статья {article_number}"
                )
                structures.append(current_article)
                continue

            i += 1

        return structures

    def _create_chunks_from_element(self, element: LegalStructure, law_number: str, metadata: dict) -> List[TextChunk]:
        """Создание чанков из структурного элемента"""
        chunks = []

        if element.type == 'article':
            return self._chunk_article(element, law_number, metadata)
        elif element.type in ['chapter', 'section']:
            # Для глав и разделов создаем информационные чанки
            chunk = TextChunk(
                id=f"{law_number}_{element.type}_{element.number}",
                text=f"{element.hierarchy_path}. {element.title}\n{element.content}",
                metadata={
                    **metadata,
                    'element_type': element.type,
                    'element_number': element.number,
                    'element_title': element.title,
                    'hierarchy_path': element.hierarchy_path,
                    'chunk_type': f'{element.type}_header',
                    'law_number': law_number
                }
            )
            chunks.append(chunk)

        return chunks

    def _chunk_article(self, article: LegalStructure, law_number: str, metadata: dict) -> List[TextChunk]:
        """Специализированный chunking статьи"""
        chunks = []
        article_content = article.content

        # 1. Если статья короткая - создаем один чанк
        if len(article_content) <= self.chunk_limits['complete_article']:
            chunk = TextChunk(
                id=f"{law_number}_article_{article.number}",
                text=article_content,
                metadata={
                    **metadata,
                    'article_number': article.number,
                    'article_title': article.title,
                    'chunk_type': 'complete_article',
                    'hierarchy_path': article.hierarchy_path,
                    'law_number': law_number,
                    'legal_element': 'article'
                }
            )
            chunks.append(chunk)
            return chunks

        # 2. Для длинных статей - разбиваем по пунктам
        paragraphs = self._extract_paragraphs(article_content)

        if paragraphs:
            for i, (paragraph_num, paragraph_text) in enumerate(paragraphs):
                # Добавляем контекст статьи к каждому пункту
                contextual_text = f"Статья {article.number}. {article.title}\n\n{paragraph_num}. {paragraph_text}"

                chunk = TextChunk(
                    id=f"{law_number}_article_{article.number}_p{paragraph_num}",
                    text=contextual_text,
                    metadata={
                        **metadata,
                        'article_number': article.number,
                        'article_title': article.title,
                        'paragraph_number': paragraph_num,
                        'chunk_type': 'article_paragraph',
                        'hierarchy_path': f"{article.hierarchy_path}, пункт {paragraph_num}",
                        'law_number': law_number,
                        'legal_element': 'paragraph'
                    }
                )
                chunks.append(chunk)
        else:
            # 3. Если пункты не найдены - разбиваем по размеру с сохранением контекста
            fragments = self._split_with_context(article_content, article.number, article.title)
            for i, fragment in enumerate(fragments):
                chunk = TextChunk(
                    id=f"{law_number}_article_{article.number}_f{i+1}",
                    text=fragment,
                    metadata={
                        **metadata,
                        'article_number': article.number,
                        'article_title': article.title,
                        'fragment_number': i+1,
                        'chunk_type': 'article_fragment',
                        'hierarchy_path': f"{article.hierarchy_path}, фрагмент {i+1}",
                        'law_number': law_number,
                        'legal_element': 'fragment'
                    }
                )
                chunks.append(chunk)

        return chunks

    def _extract_paragraphs(self, article_text: str) -> List[Tuple[str, str]]:
        """Извлечение пунктов статьи"""
        paragraphs = []

        # Поиск нумерованных пунктов
        paragraph_pattern = r'^(\d+)\.\s+(.+?)(?=\n\d+\.\s+|\n\n|\Z)'
        matches = re.finditer(paragraph_pattern, article_text, re.MULTILINE | re.DOTALL)

        for match in matches:
            paragraph_num = match.group(1)
            paragraph_text = match.group(2).strip()
            paragraphs.append((paragraph_num, paragraph_text))

        return paragraphs

    def _split_with_context(self, text: str, article_num: str, article_title: str) -> List[str]:
        """Разбиение текста с сохранением контекста статьи"""
        fragments = []
        max_fragment_size = self.chunk_limits['article_fragment'] - 200  # Резерв для контекста

        # Заголовок статьи для контекста
        context_header = f"Статья {article_num}. {article_title}\n\n"

        words = text.split()
        current_fragment = ""

        for word in words:
            if len(current_fragment + " " + word) <= max_fragment_size:
                current_fragment += " " + word if current_fragment else word
            else:
                if current_fragment:
                    fragments.append(context_header + current_fragment.strip())
                current_fragment = word

        # Добавляем последний фрагмент
        if current_fragment:
            fragments.append(context_header + current_fragment.strip())

        return fragments

    def _create_context_chunks(self, structures: List[LegalStructure], law_number: str, metadata: dict) -> List[TextChunk]:
        """Создание дополнительных контекстных чанков"""
        chunks = []

        # Группируем статьи по главам для создания обзорных чанков
        chapters = {}
        for structure in structures:
            if structure.type == 'chapter':
                chapters[structure.number] = {
                    'title': structure.title,
                    'articles': []
                }

        # Собираем статьи по главам
        for structure in structures:
            if structure.type == 'article' and structure.parent_id:
                if structure.parent_id in chapters:
                    chapters[structure.parent_id]['articles'].append(structure)

        # Создаем обзорные чанки глав
        for chapter_num, chapter_data in chapters.items():
            if chapter_data['articles']:
                overview_text = f"Глава {chapter_num}. {chapter_data['title']}\n\n"
                overview_text += "Содержание главы:\n"

                for article in chapter_data['articles'][:5]:  # Ограничиваем количество статей
                    overview_text += f"- Статья {article.number}. {article.title}\n"

                chunk = TextChunk(
                    id=f"{law_number}_chapter_{chapter_num}_overview",
                    text=overview_text,
                    metadata={
                        **metadata,
                        'chapter_number': chapter_num,
                        'chunk_type': 'chapter_overview',
                        'hierarchy_path': f"Глава {chapter_num} - обзор",
                        'law_number': law_number,
                        'legal_element': 'overview'
                    }
                )
                chunks.append(chunk)

        return chunks

    def _enrich_with_hierarchy_metadata(self, chunks: List[TextChunk]):
        """Обогащение чанков метаданными иерархии"""
        for chunk in chunks:
            # Добавляем поисковые теги
            search_tags = []

            if 'article_number' in chunk.metadata:
                search_tags.append(f"статья_{chunk.metadata['article_number']}")

            if 'chapter_number' in chunk.metadata:
                search_tags.append(f"глава_{chunk.metadata['chapter_number']}")

            if 'law_number' in chunk.metadata:
                search_tags.append(f"закон_{chunk.metadata['law_number']}")

            chunk.metadata['search_tags'] = search_tags

            # Добавляем уровень важности
            importance_levels = {
                'complete_article': 1.0,
                'article_paragraph': 0.9,
                'article_fragment': 0.7,
                'chapter_overview': 0.6,
                'chapter_header': 0.5
            }

            chunk_type = chunk.metadata.get('chunk_type', 'unknown')
            chunk.metadata['importance_level'] = importance_levels.get(chunk_type, 0.5)

            # Добавляем правовой контекст
            legal_contexts = {
                'концессионное соглашение': 1.0,
                'концедент': 0.9,
                'концессионер': 0.9,
                'государственно-частное партнерство': 0.8,
                'плата концедента': 0.8
            }

            text_lower = chunk.text.lower()
            relevant_contexts = []
            max_context_weight = 0.0

            for context, weight in legal_contexts.items():
                if context in text_lower:
                    relevant_contexts.append(context)
                    max_context_weight = max(max_context_weight, weight)

            chunk.metadata['legal_contexts'] = relevant_contexts
            chunk.metadata['context_weight'] = max_context_weight


class LegalChunkOptimizer:
    """Оптимизатор для существующих чанков"""

    def __init__(self):
        self.chunker = RussianLegalChunker()

    def optimize_existing_chunks(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Оптимизация уже существующих чанков"""
        optimized_chunks = []

        for chunk in chunks:
            # Проверяем, нужна ли реоптимизация
            if self._needs_reoptimization(chunk):
                reoptimized = self._reoptimize_chunk(chunk)
                optimized_chunks.extend(reoptimized)
            else:
                optimized_chunks.append(chunk)

        return optimized_chunks

    def _needs_reoptimization(self, chunk: TextChunk) -> bool:
        """Определяет, нужна ли реоптимизация чанка"""
        # Чанки с фиксированным размером без учета структуры
        if (len(chunk.text) > 500 and
            'legal_element' not in chunk.metadata and
            'статья' in chunk.text.lower()):
            return True

        return False

    def _reoptimize_chunk(self, chunk: TextChunk) -> List[TextChunk]:
        """Реоптимизация одного чанка"""
        # Применяем правовой chunking к тексту
        reoptimized = self.chunker.chunk_legal_document(chunk.text, chunk.metadata)

        # Сохраняем исходный ID как родительский
        for new_chunk in reoptimized:
            new_chunk.metadata['parent_chunk_id'] = chunk.id
            new_chunk.metadata['reoptimized'] = True

        return reoptimized