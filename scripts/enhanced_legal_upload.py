#!/usr/bin/env python3
"""
Улучшенная загрузка правовых документов с правильным чанкированием
"""

import asyncio
import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.hybrid_document_processor import get_hybrid_processor
from core.legal_chunker import get_legal_chunker, DocumentType

async def upload_legal_documents():
    """Загрузка документов с улучшенной правовой обработкой"""
    print('[ENHANCED UPLOAD] Starting legal document processing with hybrid system...')

    try:
        # Инициализация гибридного процессора
        print('[INIT] Initializing hybrid document processor...')
        processor = await get_hybrid_processor()
        print('[OK] Hybrid processor ready')

        # Документы для обработки
        documents = [
            {
                "path": "test_115_fz.pdf",
                "type": DocumentType.FEDERAL_LAW,
                "metadata": {
                    "law_number": "115-FZ",
                    "year": 2005,
                    "title": "О концессионных соглашениях",
                    "critical_articles": ["10.1", "3.5", "5.2"]
                }
            },
            {
                "path": "test_224_fz.pdf",
                "type": DocumentType.FEDERAL_LAW,
                "metadata": {
                    "law_number": "224-FZ",
                    "year": 2015,
                    "title": "О государственно-частном партнерстве",
                    "critical_articles": ["7.1", "12.1", "15.3"]
                }
            }
        ]

        success_count = 0
        total_processed = 0

        for doc in documents:
            doc_path = Path(doc["path"])

            print(f'\n[DOCUMENT] Processing {doc["metadata"]["law_number"]} - {doc["metadata"]["title"]}')
            print(f'Path: {doc_path}')

            if not doc_path.exists():
                print(f'[WARNING] File not found: {doc_path}')
                print('Looking for alternative paths...')

                # Попробуем найти в разных местах
                alternative_paths = [
                    f"файлы_для_теста/{doc_path.name}",
                    f"documents/{doc_path.name}",
                    f"data/{doc_path.name}",
                    doc_path.name
                ]

                found_path = None
                for alt_path in alternative_paths:
                    if Path(alt_path).exists():
                        found_path = alt_path
                        print(f'[FOUND] Alternative path: {alt_path}')
                        break

                if not found_path:
                    print(f'[SKIP] Cannot find {doc["path"]} in any location')
                    continue

                doc["path"] = found_path

            total_processed += 1

            try:
                print('[PROCESSING] Running hybrid document processing...')

                # Процессинг через гибридную систему
                result = await processor.process_document_hybrid(
                    doc["path"],
                    doc["metadata"]
                )

                if result and result.get('success', False):
                    success_count += 1
                    print(f'[SUCCESS] Document processed successfully')
                    print(f'  - Chunks created: {result.get("chunks_processed", "unknown")}')
                    print(f'  - Graph processing: {result.get("graph_processing_success", False)}')
                    print(f'  - Vector indexing: {result.get("vector_indexing_success", False)}')
                else:
                    print(f'[ERROR] Processing failed: {result.get("error", "unknown error")}')

            except Exception as e:
                print(f'[ERROR] Exception during processing: {e}')
                import traceback
                traceback.print_exc()

        # Финальная статистика
        print('\n' + '='*60)
        print('[UPLOAD SUMMARY]')
        print(f'Documents processed: {total_processed}')
        print(f'Successfully uploaded: {success_count}')
        print(f'Success rate: {(success_count/total_processed)*100:.1f}%' if total_processed > 0 else 'No documents processed')

        if success_count > 0:
            print('\n[NEXT STEPS]')
            print('1. Run validation: python scripts/validate_legal_data.py')
            print('2. Test system: python enhanced_validation_test.py')

        return success_count > 0

    except Exception as e:
        print(f'[CRITICAL] Upload failed: {e}')
        import traceback
        traceback.print_exc()
        return False

async def fallback_simple_upload():
    """Fallback: простая загрузка если гибридная недоступна"""
    print('[FALLBACK] Using simple document upload...')

    try:
        from core.storage_coordinator import create_storage_coordinator

        storage = await create_storage_coordinator()
        if not storage:
            print('[ERROR] Cannot initialize storage')
            return False

        # Простая загрузка существующих PDF файлов
        pdf_files = list(Path('.').glob('*.pdf'))

        print(f'Found {len(pdf_files)} PDF files')

        for pdf_file in pdf_files:
            print(f'Processing {pdf_file}...')

            try:
                # Читаем содержимое файла
                with open(pdf_file, 'rb') as f:
                    file_content = f.read()

                # Создаем метаданные
                metadata = {
                    'filename': pdf_file.name,
                    'file_type': 'pdf',
                    'law_number': '115-FZ' if '115' in pdf_file.name else '224-FZ',
                    'source': 'enhanced_upload'
                }

                # Загружаем через storage manager
                result = await storage.add_document(
                    content=pdf_file.read_text(encoding='utf-8', errors='ignore'),
                    metadata=metadata
                )

                print(f'Upload result: {result}')

            except Exception as e:
                print(f'Error processing {pdf_file}: {e}')

        return len(pdf_files) > 0

    except Exception as e:
        print(f'Fallback upload failed: {e}')
        return False

if __name__ == '__main__':
    print('Starting enhanced legal document upload...')

    # Пробуем гибридную загрузку, при неудаче - простую
    success = asyncio.run(upload_legal_documents())

    if not success:
        print('\n[RETRY] Hybrid upload failed, trying simple upload...')
        success = asyncio.run(fallback_simple_upload())

    if success:
        print('\n[COMPLETED] Document upload successful!')
    else:
        print('\n[FAILED] All upload methods failed')