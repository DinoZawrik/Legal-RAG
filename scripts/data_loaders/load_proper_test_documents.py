#!/usr/bin/env python3
"""
Загрузчик правильных тестовых документов с умным чанкингом
РЕШЕНИЕ: Использует SmartLegalChunker для сохранения структуры законов
"""

import os
import asyncio
import PyPDF2
from typing import List, Optional
import uuid

# Добавляем корневую директорию в путь
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Импорты из нашей системы
import re

from core.advanced_legal_chunker import AdvancedLegalChunker, EnhancedLegalChunk
from core.storage_coordinator import create_storage_coordinator, StorageCoordinator
from core.infrastructure_suite import TextChunk


class ProperDocumentLoader:
    """Загрузчик правильных документов с умным чанкингом"""

    def __init__(self):
        self.chunker = AdvancedLegalChunker()
        self.storage: StorageCoordinator | None = None
        self.documents_path = self._resolve_documents_path()

    async def initialize_storage(self):
        """Инициализация системы хранения"""
        self.storage = await create_storage_coordinator()
        results = {
            "postgres": self.storage.postgres.pool is not None,
            "redis": self.storage.redis.client is not None,
            "vector_store": self.storage.vector_store.collection is not None,
        }
        print(f"Инициализация хранилища: {results}")
        return all(results.values())

    async def load_all_test_documents(self) -> List[EnhancedLegalChunk]:
        """Загрузка всех тестовых документов"""
        all_chunks: List[EnhancedLegalChunk] = []

        print(f"Каталог с документами: {self.documents_path}")

        pdf_files = sorted(Path(self.documents_path).rglob("*.pdf"))
        print(f"Найдено PDF файлов: {len(pdf_files)}")

        for file_path in pdf_files:
            print(f"\nОбрабатываю: {file_path.name}")

            try:
                # Извлекаем текст из PDF
                text = self._extract_pdf_text(str(file_path))
                if not text.strip():
                    print(f"Пустой текст в {file_path.name}")
                    continue

                law_number = self._derive_law_number_from_path(file_path)
                legal_chunks = self.chunker.chunk_document(
                    text,
                    document_id=file_path.stem,
                    law_number=law_number,
                )

                # Загружаем в ChromaDB
                await self._upload_chunks_to_chromadb(legal_chunks)

                all_chunks.extend(legal_chunks)
                print(f"УСПЕХ {file_path.name}: {len(legal_chunks)} умных чанков загружено")

            except Exception as e:
                print(f"ОШИБКА обработки {file_path.name}: {e}")
                continue

        return all_chunks

    def _derive_law_number_from_path(self, file_path: Path) -> Optional[str]:
        """Пытается извлечь номер закона из имени файла."""
        name = file_path.stem
        match = re.search(r"(\d{3})-ФЗ", name)
        if match:
            return f"{match.group(1)}-ФЗ"
        return None

    def _extract_pdf_text(self, file_path: str) -> str:
        """Извлечение текста из PDF"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

            print(f"Извлечено {len(text)} символов")
            return text

        except Exception as e:
            print(f"ОШИБКА извлечения текста: {e}")
            return ""

    async def _upload_chunks_to_chromadb(self, legal_chunks: List[EnhancedLegalChunk]):
        """Загрузка чанков в ChromaDB"""
        if not legal_chunks:
            return

        # Конвертируем LegalChunk в TextChunk для совместимости
        text_chunks = []
        for legal_chunk in legal_chunks:
            metadata = legal_chunk.to_chromadb_metadata()
            metadata.update({
                'chunk_type': 'legal_smart_chunk',
                'created_with': 'AdvancedLegalChunker'
            })

            text_id = legal_chunk.chunk_id
            if not text_id:
                hierarchy_id = "::".join(
                    filter(
                        None,
                        [
                            legal_chunk.document_id,
                            f"раздел-{legal_chunk.section_number}" if legal_chunk.section_number else None,
                            f"глава-{legal_chunk.chapter_number}" if legal_chunk.chapter_number else None,
                            f"статья-{legal_chunk.article_number}" if legal_chunk.article_number else None,
                            f"часть-{legal_chunk.part_number}" if legal_chunk.part_number else None,
                            f"пункт-{legal_chunk.point_number}" if legal_chunk.point_number else None,
                            f"подпункт-{legal_chunk.subpoint_number}" if legal_chunk.subpoint_number else None,
                        ],
                    )
                )
                text_id = hierarchy_id or f"chunk_{uuid.uuid4().hex[:8]}"

            # Ensure uniqueness by appending suffix when needed
            base_id = text_id
            suffix = 1
            while any(chunk.id == text_id for chunk in text_chunks):
                text_id = f"{base_id}__{suffix}"
                suffix += 1

            text_chunk = TextChunk(
                id=text_id,
                text=legal_chunk.content,
                metadata=metadata,
            )
            text_chunks.append(text_chunk)

        # Загружаем в ChromaDB
        try:
            await self.storage.vector_store.add_documents(text_chunks)
            print(f"Загружено {len(text_chunks)} чанков в ChromaDB")
        except Exception as e:
            print(f"ОШИБКА загрузки в ChromaDB: {e}")

    async def verify_loaded_documents(self):
        """Проверка загруженных документов"""
        try:
            # Проверяем количество документов в ChromaDB
            collection_count = await self.storage.vector_store.collection.count()
            print(f"\nИТОГОВАЯ СТАТИСТИКА:")
            print(f"   Всего документов в ChromaDB: {collection_count}")

            # Тестовый поиск
            test_queries = [
                "концессионные соглашения",
                "государственно-частное партнерство",
                "плата концедента"
            ]

            print(f"\nТЕСТОВЫЕ ПОИСКИ:")
            for query in test_queries:
                results = await self.storage.search_documents(query, max_results=3)
                print(f"   '{query}': {len(results)} результатов")
                if results:
                    for i, result in enumerate(results[:2]):
                        law_type = result.metadata.get('law_type', 'unknown')
                        article = result.metadata.get('article_number', 'N/A')
                        print(f"     {i+1}. {law_type}, статья {article}")

        except Exception as e:
            print(f"ОШИБКА проверки: {e}")

    def _resolve_documents_path(self) -> str:
        """Определяет путь к директории с тестовыми документами."""
        # 1. Путь из переменной окружения
        env_path = os.getenv("TEST_DOCUMENTS_PATH")
        if env_path and os.path.isdir(env_path):
            return env_path

        # 2. Путь относительно текущей рабочей директории
        cwd_path = os.path.join(os.getcwd(), 'файлы_для_теста')
        if os.path.isdir(cwd_path):
            return cwd_path

        # 3. Путь относительно расположения скрипта
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_path = os.path.join(script_dir, 'файлы_для_теста')
        if os.path.isdir(local_path):
            return local_path

        raise FileNotFoundError(
            "Could not find test documents directory. Set TEST_DOCUMENTS_PATH environment variable."
        )


async def main():
    """Основная функция загрузки"""
    print("ЗАПУСК ЗАГРУЗЧИКА ПРАВИЛЬНЫХ ТЕСТОВЫХ ДОКУМЕНТОВ")
    print("=" * 60)

    loader = ProperDocumentLoader()

    # Инициализируем хранилище
    if not await loader.initialize_storage():
        print("ОШИБКА инициализации хранилища")
        return

    # Загружаем документы
    chunks = await loader.load_all_test_documents()

    # Проверяем результат
    await loader.verify_loaded_documents()

    print(f"\nЗАГРУЗКА ЗАВЕРШЕНА!")
    print(f"   Всего обработано чанков: {len(chunks)}")

    # Анализ по типам чанков
    chunk_types = {}
    for chunk in chunks:
        chunk_type = chunk.metadata.get('chunk_subtype', 'unknown')
        chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

    print(f"\nАНАЛИЗ ПО ТИПАМ ЧАНКОВ:")
    for chunk_type, count in chunk_types.items():
        print(f"   {chunk_type}: {count}")


if __name__ == "__main__":
    asyncio.run(main())