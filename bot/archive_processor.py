"""
Модуль для обработки архивов с документами в Telegram боте.

Поддерживает ZIP архивы и массовую обработку документов.
"""

import asyncio
import hashlib
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict

try:
    import rarfile
    RARFILE_AVAILABLE = True
except ImportError:
    RARFILE_AVAILABLE = False

try:
    import py7zr
    PY7ZR_AVAILABLE = True
except ImportError:
    PY7ZR_AVAILABLE = False

try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False

from core.processing_pipeline import UnifiedDocumentProcessor, DocumentType

logger = logging.getLogger(__name__)

@dataclass
class ArchiveProcessingResult:
    """Результат обработки архива"""
    total_files: int
    processed_files: int
    successful_files: int
    failed_files: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, str]]

class ArchiveProcessor:
    """Класс для обработки архивов с документами"""
    
    # Поддерживаемые форматы архивов
    SUPPORTED_ARCHIVE_EXTENSIONS = {'.zip'}
    if RARFILE_AVAILABLE:
        SUPPORTED_ARCHIVE_EXTENSIONS.add('.rar')
    if PY7ZR_AVAILABLE:
        SUPPORTED_ARCHIVE_EXTENSIONS.add('.7z')
    
    # Поддерживаемые форматы документов внутри архива
    SUPPORTED_DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.doc', '.rtf', '.txt'}
    
    # Кодировки для fallback декодирования (приоритетный порядок)
    ENCODING_PRIORITY = [
        'utf-8', # Современный стандарт
        'cp1251', # Windows Кириллица
        'cp866', # DOS Кириллица
        'koi8-r', # KOI8-R Кириллица
        'iso-8859-5', # ISO Кириллица
        'latin1' # Fallback
    ]
    
    def __init__(self):
        self.processing_pipeline = UnifiedDocumentProcessor()
        # Статистика по проблемам с декодированием имен файлов
        self.decoding_stats = defaultdict(int)
        
        # Проверяем доступность зависимостей и логируем статус
        self._log_supported_formats()
    
    def fix_filename_encoding(self, filename: str) -> str:
        """Исправляет кодировку имени файла для русских символов (упрощенная версия)"""
        return self._simple_decode_filename(filename)
    
    def _simple_decode_filename(self, filename: str) -> str:
        """Упрощенное декодирование имен файлов из архивов"""
        try:
            # Проверяем, есть ли не-ASCII символы
            if any(ord(c) > 127 for c in filename):
                # Пробуем основные кодировки для русского языка
                encodings = [
                    ('cp866', 'latin1'), # DOS Russian
                    ('cp1251', 'latin1'), # Windows Russian 
                    ('utf-8', 'latin1'), # UTF-8
                ]
                
                for target_encoding, source_encoding in encodings:
                    try:
                        decoded = filename.encode(source_encoding).decode(target_encoding, errors='ignore')
                        # Проверяем, что декодирование дало разумный результат
                        if decoded != filename and len(decoded.strip()) > 0:
                            logger.debug(f" Декодировано с {target_encoding}: {repr(filename)} -> {repr(decoded)}")
                            return decoded
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        continue
                
                # Если ничего не сработало, убираем проблемные символы
                safe_filename = ''.join(c if ord(c) < 128 else '_' for c in filename)
                if safe_filename != filename:
                    logger.debug(f" Очищено имя файла: {repr(filename)} -> {repr(safe_filename)}")
                    return safe_filename
                    
        except Exception as e:
            logger.debug(f" Ошибка декодирования имени файла: {e}")
        
        return filename
    
    def _log_supported_formats(self):
        """Логирование поддерживаемых форматов архивов и документов"""
        logger.info(" Инициализация ArchiveProcessor...")
        
        # Проверяем поддержку архивных форматов
        archive_support = {
            'ZIP': True, # Всегда поддерживается
            'RAR': RARFILE_AVAILABLE,
            '7-Zip': PY7ZR_AVAILABLE
        }
        
        # Проверяем поддержку документов
        doc_support = {
            'PDF': True, # Всегда поддерживается
            'TXT': True, # Всегда поддерживается
            'DOCX': self._check_docx_support(),
            'DOC': self._check_doc_support(), 
            'RTF': self._check_rtf_support(),
        }
        
        # Логируем статус поддержки
        logger.info(" Поддерживаемые архивы:")
        for format_name, supported in archive_support.items():
            status = "" if supported else ""
            support_text = "поддерживается" if supported else "недоступно"
            logger.info(f" {status} {format_name}: {support_text}")
            
        logger.info(" Поддерживаемые документы:")
        for format_name, supported in doc_support.items():
            status = "" if supported else ""
            support_text = "поддерживается" if supported else "недоступно"
            logger.info(f" {status} {format_name}: {support_text}")
        
        # Финальный список поддерживаемых форматов
        supported_archives = [f for f, s in archive_support.items() if s]
        supported_documents = [f for f, s in doc_support.items() if s]
        
        logger.info(f" Доступные архивы: {', '.join(supported_archives)}")
        logger.info(f" Доступные документы: {', '.join(supported_documents)}")
    
    def _check_docx_support(self) -> bool:
        """Проверка поддержки DOCX"""
        try:
            import docx
            return True
        except ImportError:
            return False
    
    def _check_doc_support(self) -> bool:
        """Проверка поддержки legacy DOC"""
        try:
            import docx2txt
            return True
        except ImportError:
            try:
                import textract
                return True
            except ImportError:
                try:
                    import olefile
                    return True
                except ImportError:
                    return False
    
    def _check_rtf_support(self) -> bool:
        """Проверка поддержки RTF"""
        try:
            from striprtf.striprtf import rtf_to_text
            return True
        except ImportError:
            try:
                import textract
                return True
            except ImportError:
                return False
    
    def is_archive(self, filename: str) -> bool:
        """Проверяет, является ли файл поддерживаемым архивом"""
        file_extension = Path(filename).suffix.lower()
        return file_extension in self.SUPPORTED_ARCHIVE_EXTENSIONS
    
    def is_archive_by_content(self, file_path: str) -> bool:
        """Проверяет, является ли файл архивом по содержимому"""
        try:
            # Проверяем ZIP
            if zipfile.is_zipfile(file_path):
                return True
            
            # Проверяем RAR если библиотека доступна
            if RARFILE_AVAILABLE:
                try:
                    with rarfile.RarFile(file_path, 'r') as rar_ref:
                        # Если удается открыть как RAR, то это RAR архив
                        return True
                except (rarfile.BadRarFile, rarfile.NotRarFile):
                    pass
                    
            return False
        except Exception:
            return False
    
    def is_supported_document(self, filename: str) -> bool:
        """Проверяет, является ли файл поддерживаемым документом"""
        file_extension = Path(filename).suffix.lower()
        return file_extension in self.SUPPORTED_DOCUMENT_EXTENSIONS
    
    async def extract_archive(self, archive_path: str) -> Tuple[List[str], str]:
        """
        Извлекает архив и возвращает список путей к извлеченным документам.
        
        Args:
            archive_path: Путь к архиву
            
        Returns:
            Tuple[List[str], str]: (список путей к документам, путь к временной папке)
        """
        temp_dir = tempfile.mkdtemp(prefix="legalrag_archive_")
        extracted_documents = []
        
        try:
            logger.info(f"Извлечение архива: {archive_path}")
            file_extension = Path(archive_path).suffix.lower()
            
            # Определяем тип архива и извлекаем соответствующим образом
            if file_extension == '.zip':
                extracted_documents = await self._extract_zip(archive_path, temp_dir)
            elif file_extension == '.rar' and RARFILE_AVAILABLE:
                extracted_documents = await self._extract_rar(archive_path, temp_dir)
            elif file_extension == '.7z' and PY7ZR_AVAILABLE:
                extracted_documents = await self._extract_7z(archive_path, temp_dir)
            else:
                raise ValueError(f"Неподдерживаемый тип архива: {file_extension}")
            
            logger.info(f"Извлечено {len(extracted_documents)} документов из архива")
            return extracted_documents, temp_dir
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении архива: {e}")
            raise
    
    async def _extract_zip(self, archive_path: str, temp_dir: str) -> List[str]:
        """Улучшенное извлечение ZIP архива с лучшей обработкой кодировок и ошибок"""
        extracted_documents = []
        failed_extractions = []
        
        try:
            # Первоначальная валидация архива
            if not zipfile.is_zipfile(archive_path):
                raise ValueError("Невалидный ZIP архив")
                
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                # Проверяем целостность архива
                try:
                    corrupted_files = zip_ref.testzip()
                    if corrupted_files:
                        logger.warning(f"Обнаружены поврежденные файлы в архиве: {corrupted_files}")
                except Exception as e:
                    logger.warning(f"Не удалось проверить целостность архива: {e}")
                
                for file_info in zip_ref.infolist():
                    # Пропускаем папки
                    if file_info.is_dir():
                        continue
                    
                    # Получаем имя файла с улучшенным декодированием
                    raw_filename = file_info.filename
                    filename = self._simple_decode_filename(raw_filename)
                    
                    logger.debug(f" Обработка файла: {filename} (оригинал: {raw_filename})")
                    
                    # Проверяем, является ли файл поддерживаемым документом
                    if self.is_supported_document(filename):
                        try:
                            # Проверяем размер файла
                            if file_info.file_size > 100 * 1024 * 1024: # 100MB
                                logger.warning(f"Файл {filename} слишком большой ({file_info.file_size} байт), пропускаем")
                                failed_extractions.append({
                                    'filename': filename,
                                    'reason': 'file_too_large',
                                    'size': file_info.file_size
                                })
                                continue

                            # Security: Path traversal protection
                            safe_filename = os.path.basename(raw_filename)
                            if '..' in file_info.filename or file_info.filename.startswith(('/', '\\')):
                                logger.warning(f"Path traversal attempt blocked: {file_info.filename}")
                                failed_extractions.append({
                                    'filename': filename,
                                    'reason': 'path_traversal_blocked',
                                })
                                continue

                            # Safe extraction: read from archive and write to validated path
                            extracted_path = os.path.join(temp_dir, safe_filename)
                            real_temp = os.path.realpath(temp_dir)
                            real_target = os.path.realpath(extracted_path)
                            if not real_target.startswith(real_temp + os.sep) and real_target != real_temp:
                                logger.error(f"Path traversal detected after resolve: {file_info.filename}")
                                failed_extractions.append({
                                    'filename': filename,
                                    'reason': 'path_traversal_blocked',
                                })
                                continue

                            with zip_ref.open(file_info) as src, open(extracted_path, 'wb') as dst:
                                dst.write(src.read())
                            
                            # Переименовываем файл, если нужно исправить кодировку
                            if safe_filename != filename and os.path.exists(extracted_path):
                                new_path = os.path.join(temp_dir, filename)
                                try:
                                    # Проверяем, что файл с таким именем не существует
                                    if not os.path.exists(new_path):
                                        os.rename(extracted_path, new_path)
                                        extracted_path = new_path
                                        logger.debug(f" Переименован: {safe_filename} -> {filename}")
                                    else:
                                        logger.warning(f"Файл {filename} уже существует, используем оригинальное имя")
                                except OSError as e:
                                    logger.debug(f"Не удалось переименовать {safe_filename} -> {filename}: {e}")
                            
                            # Проверяем, что файл действительно извлечен и читаем
                            if os.path.exists(extracted_path) and os.path.getsize(extracted_path) > 0:
                                extracted_documents.append(extracted_path)
                                logger.debug(f" Извлечен документ: {filename}")
                            else:
                                logger.warning(f" Файл не найден или пуст после извлечения: {filename}")
                                failed_extractions.append({
                                    'filename': filename,
                                    'reason': 'empty_or_missing',
                                    'path': extracted_path
                                })
                                
                        except Exception as e:
                            logger.error(f" Ошибка при извлечении файла {filename}: {e}")
                            failed_extractions.append({
                                'filename': filename,
                                'reason': 'extraction_error',
                                'error': str(e)
                            })
                            continue
                    else:
                        logger.debug(f" Пропущен неподдерживаемый файл: {filename}")
                        
            # Логируем результаты
            if failed_extractions:
                logger.warning(f"Не удалось извлечь {len(failed_extractions)} файлов")
                for failure in failed_extractions:
                    logger.debug(f" - {failure['filename']}: {failure['reason']}")
                        
        except zipfile.BadZipFile:
            raise ValueError("Повреждённый ZIP архив")
        except PermissionError:
            raise ValueError("Недостаточно прав для извлечения архива")
        except Exception as e:
            logger.error(f" Ошибка обработки ZIP архива: {e}")
            raise ValueError(f"Ошибка обработки ZIP архива: {str(e)}")
            
        return extracted_documents
    
    def _setup_unrar_tool(self) -> bool:
        """Упрощенная настройка unrar утилиты для RAR архивов"""
        try:
            import subprocess
            
            # Простая проверка доступности unrar
            unrar_paths = ['unrar', '/usr/bin/unrar', '/usr/local/bin/unrar']
            
            for unrar_path in unrar_paths:
                try:
                    # Простая проверка - запускаем unrar без параметров
                    result = subprocess.run(
                        [unrar_path], 
                        capture_output=True, 
                        timeout=3,
                        text=True
                    )
                    # unrar возвращает не 0 код, но если он запустился, то это хорошо
                    if 'usage' in result.stderr.lower() or 'unrar' in result.stderr.lower():
                        rarfile.UNRAR_TOOL = unrar_path
                        logger.info(f" Настроен unrar: {unrar_path}")
                        return True
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    continue
                    
            logger.warning(" unrar не найден в системе")
            return False
            
        except Exception as e:
            logger.error(f" Ошибка настройки unrar: {e}")
            return False
    
    async def _extract_rar(self, archive_path: str, temp_dir: str) -> List[str]:
        """Извлечение RAR архива с упрощенной обработкой"""
        extracted_documents = []
        failed_extractions = []
        
        # Настраиваем unrar перед обработкой
        if not self._setup_unrar_tool():
            raise ValueError(
                " RAR архивы не поддерживаются: unrar не установлен.\n\n"
                " Пожалуйста, используйте ZIP или 7z архивы, либо отправьте документы по одному."
            )
        
        try:
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                for file_info in rar_ref.infolist():
                    # Пропускаем папки
                    if file_info.is_dir():
                        continue
                    
                    # Получаем имя файла с упрощенным декодированием
                    raw_filename = file_info.filename
                    filename = self._simple_decode_filename(raw_filename)
                    
                    logger.debug(f" RAR файл: {filename}")
                    
                    # Проверяем, является ли файл поддерживаемым документом
                    if self.is_supported_document(filename):
                        try:
                            # Проверяем размер файла
                            if file_info.file_size > 100 * 1024 * 1024: # 100MB
                                logger.warning(f"RAR файл {filename} слишком большой, пропускаем")
                                failed_extractions.append({
                                    'filename': filename,
                                    'reason': 'file_too_large',
                                    'size': file_info.file_size
                                })
                                continue
                            
                            # Извлекаем файл
                            rar_ref.extract(file_info, temp_dir)
                            
                            # Получаем путь к извлеченному файлу
                            extracted_path = os.path.join(temp_dir, raw_filename)
                            
                            # Переименовываем, если нужно
                            if raw_filename != filename and os.path.exists(extracted_path):
                                new_path = os.path.join(temp_dir, filename)
                                try:
                                    if not os.path.exists(new_path):
                                        os.rename(extracted_path, new_path)
                                        extracted_path = new_path
                                        logger.debug(f" Переименован RAR файл: {raw_filename} -> {filename}")
                                except OSError:
                                    logger.debug(f"Не удалось переименовать RAR файл: {raw_filename}")
                            
                            # Проверяем, что файл действительно извлечен
                            if os.path.exists(extracted_path) and os.path.getsize(extracted_path) > 0:
                                extracted_documents.append(extracted_path)
                                logger.debug(f" Извлечен RAR документ: {filename}")
                            else:
                                logger.warning(f" RAR файл не найден или пуст после извлечения: {filename}")
                                failed_extractions.append({
                                    'filename': filename,
                                    'reason': 'empty_or_missing'
                                })
                                
                        except Exception as e:
                            logger.error(f" Ошибка при извлечении RAR файла {filename}: {e}")
                            failed_extractions.append({
                                'filename': filename,
                                'reason': 'extraction_error',
                                'error': str(e)
                            })
                            continue
                    else:
                        logger.debug(f" Пропущен неподдерживаемый RAR файл: {filename}")
                        
            # Логируем результаты
            if failed_extractions:
                logger.warning(f"Не удалось извлечь {len(failed_extractions)} RAR файлов")
                for failure in failed_extractions:
                    logger.debug(f" - {failure['filename']}: {failure['reason']}")
                        
        except rarfile.RarCannotExec as e:
            logger.error(f"Невозможно запустить unrar: {e}")
            raise ValueError(
                " RAR архивы не поддерживаются в текущей конфигурации.\n\n"
                " Пожалуйста, используйте ZIP или 7z архивы, либо отправьте документы по одному."
            )
        except rarfile.BadRarFile:
            raise ValueError("Повреждённый RAR архив")
        except PermissionError:
            raise ValueError("Недостаточно прав для извлечения RAR архива")
        except Exception as e:
            logger.error(f" Общая ошибка при обработке RAR: {e}")
            raise ValueError(f"Ошибка обработки RAR архива: {str(e)}")
            
        return extracted_documents
    
    async def _extract_7z(self, archive_path: str, temp_dir: str) -> List[str]:
        """Извлечение 7-Zip архива"""
        extracted_documents = []
        failed_extractions = []
        
        try:
            with py7zr.SevenZipFile(archive_path, mode='r') as archive_ref:
                # Получаем список файлов в архиве
                file_list = archive_ref.getnames()
                
                for filename in file_list:
                    # Пропускаем папки (определяем по окончанию на /)
                    if filename.endswith('/'):
                        continue
                        
                    # Проверяем, является ли файл поддерживаемым документом
                    if self.is_supported_document(filename):
                        try:
                            logger.debug(f" Обработка 7z файла: {filename}")
                            
                            # Извлекаем конкретный файл
                            archive_ref.extract(targets=[filename], path=temp_dir)
                            
                            # Проверяем путь к извлеченному файлу
                            extracted_path = os.path.join(temp_dir, filename)
                            
                            if os.path.exists(extracted_path) and os.path.getsize(extracted_path) > 0:
                                extracted_documents.append(extracted_path)
                                logger.debug(f" Извлечен 7z документ: {filename}")
                            else:
                                logger.warning(f" 7z файл не найден или пуст после извлечения: {filename}")
                                failed_extractions.append({
                                    'filename': filename,
                                    'reason': 'empty_or_missing'
                                })
                                
                        except Exception as e:
                            logger.error(f" Ошибка при извлечении 7z файла {filename}: {e}")
                            failed_extractions.append({
                                'filename': filename,
                                'reason': 'extraction_error',
                                'error': str(e)
                            })
                            continue
                    else:
                        logger.debug(f" Пропущен неподдерживаемый 7z файл: {filename}")
                        
            # Логируем результаты
            if failed_extractions:
                logger.warning(f"Не удалось извлечь {len(failed_extractions)} 7z файлов")
                for failure in failed_extractions:
                    logger.debug(f" - {failure['filename']}: {failure['reason']}")
                        
        except py7zr.exceptions.Bad7zFile:
            raise ValueError("Повреждённый 7-Zip архив")
        except PermissionError:
            raise ValueError("Недостаточно прав для извлечения 7z архива")
        except Exception as e:
            logger.error(f" Ошибка обработки 7-Zip архива: {e}")
            raise ValueError(f"Ошибка обработки 7-Zip архива: {str(e)}")
            
        return extracted_documents
    
    async def pre_check_duplicates(self, extracted_documents: List[str], document_type: DocumentType = DocumentType.REGULATORY) -> Dict[str, Any]:
        """
        Предварительная проверка дубликатов в архиве перед обработкой.
        
        Args:
            extracted_documents: Список путей к извлеченным документам
            document_type: Тип документа для проверки
            
        Returns:
            Dict с информацией о дубликатах и новых файлах
        """
        try:
            # Подготавливаем информацию о документах для проверки
            documents_info = []
            
            for doc_path in extracted_documents:
                filename = os.path.basename(doc_path)
                # Исправляем кодировку
                display_filename = self.fix_filename_encoding(filename)
                
                # Вычисляем хеш файла
                file_hash = None
                try:
                    with open(doc_path, 'rb') as f:
                        content = f.read()
                        file_hash = hashlib.sha256(content).hexdigest()
                except Exception as e:
                    logger.warning(f" Не удалось вычислить хеш для {filename}: {e}")
                
                documents_info.append({
                    'filename': display_filename,
                    'file_path': doc_path,
                    'file_hash': file_hash,
                    'document_type': document_type.value if hasattr(document_type, 'value') else str(document_type),
                    # Добавляем metadata с original_filename для корректной дедупликации
                    'metadata': {
                        'original_filename': display_filename,
                        'from_archive': True,
                        'archive_path': os.path.basename(self.current_archive_path) if hasattr(self, 'current_archive_path') else 'unknown'
                    }
                })
            
            # Получаем доступ к системе хранения для проверки дубликатов
            from core.storage_coordinator import create_storage_coordinator
            storage_manager = await create_storage_coordinator()
            
            # Выполняем массовую проверку дубликатов
            duplicate_check = await storage_manager.postgres.check_duplicates_bulk(documents_info)
            
            logger.info(f" Предварительная проверка архива: найдено {duplicate_check['summary']['duplicates_found']} дубликатов из {duplicate_check['summary']['total_files']} файлов")
            
            return duplicate_check
            
        except Exception as e:
            logger.error(f" Ошибка предварительной проверки дубликатов: {e}")
            return {
                'duplicates': [],
                'new_files': documents_info if 'documents_info' in locals() else [],
                'summary': {
                    'total_files': len(extracted_documents),
                    'duplicates_found': 0,
                    'new_files': len(extracted_documents),
                    'duplicate_rate': 0,
                    'error': str(e)
                }
            }
    
    async def process_archive(
        self, 
        archive_path: str, 
        document_type: DocumentType = DocumentType.REGULATORY,
        progress_callback = None,
        skip_duplicates: bool = True
    ) -> ArchiveProcessingResult:
        """
        Обрабатывает архив с документами.
        
        Args:
            archive_path: Путь к архиву
            document_type: Тип документов для обработки
            progress_callback: Функция для отслеживания прогресса
            
        Returns:
            ArchiveProcessingResult: Результат обработки
        """
        temp_dir = None
        results = []
        errors = []
        
        try:
            # Извлекаем архив
            extracted_documents, temp_dir = await self.extract_archive(archive_path)
            
            if not extracted_documents:
                return ArchiveProcessingResult(
                    total_files=0,
                    processed_files=0,
                    successful_files=0,
                    failed_files=0,
                    results=[],
                    errors=[{"error": "В архиве не найдено поддерживаемых документов (.pdf, .docx, .doc, .rtf, .txt)"}]
                )
            
            # Предварительная проверка дубликатов (если включена)
            duplicate_check = None
            documents_to_process = extracted_documents
            skipped_duplicates = []
            
            if skip_duplicates:
                logger.info(f" Выполняем предварительную проверку дубликатов для {len(extracted_documents)} файлов...")
                duplicate_check = await self.pre_check_duplicates(extracted_documents, document_type)
                
                if duplicate_check['summary']['duplicates_found'] > 0:
                    # Получаем только новые файлы для обработки
                    new_file_paths = [info['file_path'] for info in duplicate_check['new_files']]
                    documents_to_process = new_file_paths
                    skipped_duplicates = duplicate_check['duplicates']
                    
                    logger.info(f" Пропущено {len(skipped_duplicates)} дубликатов, обрабатываем {len(documents_to_process)} новых файлов")
            
            logger.info(f"Начинаем обработку {len(documents_to_process)} документов")
            
            # Обрабатываем каждый документ
            for i, doc_path in enumerate(documents_to_process):
                try:
                    filename = os.path.basename(doc_path)
                    
                    # Исправляем кодировку filename для отображения
                    display_filename = self.fix_filename_encoding(filename)
                    
                    # Вызываем callback для отображения прогресса
                    if progress_callback:
                        await progress_callback(i + 1, len(extracted_documents), display_filename)
                    
                    logger.info(f"Обработка файла {i+1}/{len(extracted_documents)}: {filename}")
                    
                    # Обрабатываем документ с правильными metadata
                    result = await self.processing_pipeline.process_single_document(
                        file_path=doc_path,
                        force_type=document_type,
                        metadata={
                            "original_filename": display_filename, # Исправленное имя файла
                            "from_archive": True,
                            "raw_filename": filename, # Сохраняем оригинальное имя для отладки
                            "archive_extraction": True
                        }
                    )
                    
                    result["filename"] = filename
                    results.append(result)
                    
                    if result.get("success"):
                        logger.info(f" Успешно обработан: {filename}")
                    else:
                        logger.warning(f" Ошибка обработки: {filename} - {result.get('error', 'Неизвестная ошибка')}")
                        errors.append({
                            "filename": filename,
                            "error": result.get('error', 'Неизвестная ошибка')
                        })
                    
                    # Небольшая пауза между обработкой файлов
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    error_msg = f"Критическая ошибка при обработке {filename}: {e}"
                    logger.error(error_msg)
                    errors.append({
                        "filename": os.path.basename(doc_path),
                        "error": str(e)
                    })
                    continue
            
            # Подсчитываем статистику
            successful_files = len([r for r in results if r.get("success")])
            failed_files = len(results) - successful_files
            
            # Добавляем информацию о пропущенных дубликатах в результаты
            if skipped_duplicates:
                for dup in skipped_duplicates:
                    results.append({
                        "success": True,
                        "duplicate": True,
                        "filename": dup['filename'],
                        "existing_id": dup['existing_id'],
                        "message": f"Пропущен дубликат: {dup['reason']}"
                    })
                    
            # Обновляем статистику с учетом пропущенных дубликатов
            total_successful = successful_files + len(skipped_duplicates)
            
            return ArchiveProcessingResult(
                total_files=len(extracted_documents),
                processed_files=len(results),
                successful_files=total_successful,
                failed_files=failed_files,
                results=results,
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке архива: {e}")
            raise
        finally:
            # Очищаем временную папку
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Удалена временная папка: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить временную папку {temp_dir}: {e}")
    
    def format_processing_result(self, result: ArchiveProcessingResult) -> str:
        """Форматирует результат обработки для отправки пользователю"""
        
        if result.total_files == 0:
            return " В архиве не найдено поддерживаемых документов (.pdf, .docx, .doc, .rtf, .txt)"
        
        # Основная статистика
        message = f""" **Обработка архива завершена!**

**Статистика:**
• Всего файлов: {result.total_files}
• Обработано: {result.processed_files}
• Успешно: {result.successful_files} 
• Ошибки: {result.failed_files} 

"""
        
        # Разделяем результаты на новые файлы и дубликаты
        new_files = [r for r in result.results if r.get("success") and not r.get("duplicate")]
        duplicate_files = [r for r in result.results if r.get("success") and r.get("duplicate")]
        
        # Список новых обработанных файлов (максимум 10)
        if new_files:
            message += " **Новые обработанные файлы:**\n"
            for i, result_item in enumerate(new_files[:10]):
                filename = result_item.get("filename", "unknown")
                message += f"• {filename}\n"
            
            if len(new_files) > 10:
                message += f"• ... и ещё {len(new_files) - 10} файлов\n"
            
            message += "\n"
        
        # Список пропущенных дубликатов (максимум 5)
        if duplicate_files:
            message += " **Пропущенные дубликаты:**\n"
            for i, result_item in enumerate(duplicate_files[:5]):
                filename = result_item.get("filename", "unknown")
                reason = result_item.get("message", "дубликат")
                message += f"• {filename} ({reason})\n"
            
            if len(duplicate_files) > 5:
                message += f"• ... и ещё {len(duplicate_files) - 5} дубликатов\n"
            
            message += "\n"
        
        # Список ошибок (максимум 5)
        if result.errors:
            message += " **Ошибки обработки:**\n"
            for i, error in enumerate(result.errors[:5]):
                filename = error.get("filename", "unknown")
                error_msg = error.get("error", "Неизвестная ошибка")
                message += f"• {filename}: {error_msg}\n"
            
            if len(result.errors) > 5:
                message += f"• ... и ещё {len(result.errors) - 5} ошибок\n"
        
        return message