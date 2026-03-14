#!/usr/bin/env python3
"""
Universal Archive Processor - Универсальная обработка архивов
Поддержка ZIP, RAR, 7z архивов с единым интерфейсом
"""

import streamlit as st
import requests
import os
import hashlib
import zipfile
import tempfile
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import io

logger = logging.getLogger(__name__)

# Импорт дополнительных библиотек архивов с проверкой доступности
try:
    import rarfile
    RARFILE_AVAILABLE = True
    logger.info("rarfile library available")
except ImportError:
    RARFILE_AVAILABLE = False
    logger.warning("rarfile library not available - RAR support disabled")

try:
    import py7zr
    PY7ZR_AVAILABLE = True
    logger.info("py7zr library available")
except ImportError:
    PY7ZR_AVAILABLE = False
    logger.warning("py7zr library not available - 7z support disabled")


class UniversalArchiveProcessor:
    """Универсальный процессор архивов с поддержкой ZIP, RAR, 7z"""
    
    def __init__(self):
        self.api_gateway_url = os.getenv('API_GATEWAY_URL', 'http://localhost:8080')
        self.supported_formats = ['.pdf', '.docx', '.doc', '.txt', '.rtf']
        self.max_file_size = 100 * 1024 * 1024 # 100MB
        self.max_archive_size = 500 * 1024 * 1024 # 500MB
        self.max_concurrent_uploads = 3 # Количество параллельных загрузок
        
        # Определяем поддерживаемые типы архивов
        self.supported_archive_types = {
            '.zip': 'ZIP архив',
            '.rar': 'RAR архив' if RARFILE_AVAILABLE else None,
            '.7z': '7z архив' if PY7ZR_AVAILABLE else None
        }
        # Убираем неподдерживаемые форматы
        self.supported_archive_types = {k: v for k, v in self.supported_archive_types.items() if v is not None}
        
    def get_supported_archive_info(self) -> Dict[str, str]:
        """Возвращает информацию о поддерживаемых архивах"""
        return {
            'supported_types': list(self.supported_archive_types.keys()),
            'descriptions': self.supported_archive_types,
            'libraries': {
                'rarfile': RARFILE_AVAILABLE,
                'py7zr': PY7ZR_AVAILABLE
            }
        }
        
    def detect_archive_type(self, file_path: str) -> Optional[str]:
        """Определяет тип архива по расширению и содержимому"""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        if extension in self.supported_archive_types:
            return extension
        
        # Попытка определить по содержимому (магические числа)
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
                
            # ZIP архив (PK)
            if header.startswith(b'PK'):
                return '.zip'
            
            # RAR архив (Rar!) 
            if header.startswith(b'Rar!'):
                return '.rar'
            
            # 7z архив
            if header.startswith(b'7z\xBC\xAF\x27\x1C'):
                return '.7z'
                
        except Exception as e:
            logger.warning(f"Не удалось определить тип архива {file_path}: {e}")
            
        return None
    
    def render_universal_archive_upload(self):
        """Отображение универсального интерфейса загрузки архивов"""

        st.subheader("Универсальная обработка архивов")

        # Плашка с предупреждением о разработке
        st.warning("""
        **ЭКСПЕРИМЕНТАЛЬНАЯ ФУНКЦИЯ**

        Обработка архивов находится в стадии разработки и тестирования.
        Могут возникать проблемы с извлечением файлов или кодировкой имен файлов.

        Рекомендуется использовать загрузку отдельных файлов для критически важных документов.
        """)
        
        # Получаем поддерживаемые форматы
        supported_info = self.get_supported_archive_info()
        # Загрузчик архивов
        supported_extensions = [ext[1:] for ext in supported_info['supported_types']] # убираем точку
        
        uploaded_archive = st.file_uploader(
            "Выберите архив для загрузки",
            type=supported_extensions,
            help=f"Поддерживаемые форматы: {', '.join(supported_extensions).upper()}"
        )
        
        if uploaded_archive:
            self._process_uploaded_archive(uploaded_archive)
    
    def _process_uploaded_archive(self, uploaded_file):
        """Обработка загруженного архива"""
        
        # Проверяем размер
        if uploaded_file.size > self.max_archive_size:
            st.error(f"[FAIL] Размер архива ({uploaded_file.size / (1024*1024):.1f} МБ) превышает лимит ({self.max_archive_size / (1024*1024):.0f} МБ)")
            return
        
        # Определяем тип архива
        archive_type = self.detect_archive_type(uploaded_file.name)
        
        if not archive_type:
            st.error(f"[FAIL] Неподдерживаемый формат архива: {Path(uploaded_file.name).suffix}")
            return
            
        st.info(f"[INFO] Обнаружен архив: **{archive_type.upper()[1:]}** ({uploaded_file.size / (1024*1024):.1f} МБ)")
        
        # Автоматическое определение типа документов
        document_type = " Автоматическое определение"
        
        # Кнопка для запуска обработки
        if st.button(f"Обработать {archive_type.upper()[1:]} архив", key="process_universal_archive"):
            
            # Создаем прогресс-бары
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def progress_callback(percent, message):
                progress_bar.progress(percent / 100)
                status_text.text(f"[PROGRESS] {message}")
            
            # Обрабатываем архив
            with st.spinner("Обработка архива..."):
                result = self.process_archive_universal(uploaded_file, archive_type, progress_callback, document_type)
            
            # Показываем результат
            self._display_processing_results(result, archive_type)
    
    def process_archive_universal(self, uploaded_file, archive_type: str, progress_callback=None, document_type: str = " Автоматическое определение") -> Dict[str, Any]:
        """
        Универсальная обработка архива любого поддерживаемого типа
        """
        result = {
            "success": False,
            "archive_type": archive_type,
            "total_files": 0,
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "files": [],
            "error_details": []
        }
        
        try:
            # Сохраняем архив во временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix=archive_type) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                archive_path = tmp_file.name
            
            # Анализируем содержимое архива в зависимости от типа
            files_to_process = self._analyze_archive_universal(archive_path, archive_type)
            result["total_files"] = len(files_to_process)
            
            if not files_to_process:
                result["error_details"].append("Архив не содержит поддерживаемых файлов")
                return result
            
            # Обновляем прогресс
            if progress_callback:
                progress_callback(10, f"Найдено {len(files_to_process)} файлов для обработки")
            
            # Параллельная обработка файлов
            processed_files = self._process_files_sequential_universal(
                archive_path, 
                archive_type,
                files_to_process, 
                progress_callback,
                document_type
            )
            
            # Подсчитываем результаты
            for file_result in processed_files:
                result["files"].append(file_result)
                if file_result["status"] == "success":
                    result["processed"] += 1
                elif file_result["status"] == "skipped":
                    result["skipped"] += 1
                else:
                    result["errors"] += 1
                    if "error" in file_result:
                        result["error_details"].append(f"{file_result['filename']}: {file_result['error']}")
            
            # Очистка
            os.unlink(archive_path)
            
            result["success"] = result["processed"] > 0
            
            if progress_callback:
                progress_callback(100, f"Завершено: {result['processed']} загружено, {result['skipped']} пропущено, {result['errors']} ошибок")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка обработки {archive_type} архива: {e}")
            result["error_details"].append(f"Критическая ошибка: {str(e)}")
            return result
    
    def _analyze_archive_universal(self, archive_path: str, archive_type: str) -> List[Dict[str, Any]]:
        """Универсальный анализ содержимого архива"""
        files_to_process = []
        
        try:
            if archive_type == '.zip':
                files_to_process = self._analyze_zip_archive(archive_path)
            elif archive_type == '.rar' and RARFILE_AVAILABLE:
                files_to_process = self._analyze_rar_archive(archive_path)
            elif archive_type == '.7z' and PY7ZR_AVAILABLE:
                files_to_process = self._analyze_7z_archive(archive_path)
            else:
                raise ValueError(f"Неподдерживаемый тип архива: {archive_type}")
                
        except Exception as e:
            logger.error(f"Ошибка анализа архива {archive_type}: {e}")
            
        return files_to_process
    
    def _auto_detect_document_type(self, filename: str) -> str:
        """Автоматическое определение типа документа по имени файла и расширению"""
        filename_lower = filename.lower()
        
        # Презентации - PowerPoint, PDF презентации
        presentation_indicators = [
            '.pptx', '.ppt', '.odp',
            'презентация', 'presentation', 'слайд', 'slide',
            'доклад', 'report'
        ]
        
        # Табличные данные - Excel, CSV
        spreadsheet_indicators = [
            '.xlsx', '.xls', '.csv', '.ods',
            'таблица', 'данные', 'отчет', 'статистика', 
            'реестр', 'список', 'перечень'
        ]
        
        # Регуляторные документы - законы, постановления, приказы
        regulatory_indicators = [
            'закон', 'постановление', 'приказ', 'указ', 'распоряжение',
            'положение', 'инструкция', 'регламент', 'стандарт', 'норма',
            'фз', 'федеральный', 'кодекс', 'конституция',
            'law', 'decree', 'order', 'regulation', 'standard'
        ]
        
        # Проверяем презентации (ПРИОРИТЕТ - презентации могут быть в PDF!)
        if any(indicator in filename_lower for indicator in presentation_indicators):
            return " Презентация с контекстным извлечением"

        # Проверяем табличные данные
        if any(indicator in filename_lower for indicator in spreadsheet_indicators):
            return " Табличные данные (Excel/CSV)"

        # Проверяем регуляторные документы (НО НЕ если это может быть презентация в PDF)
        if any(indicator in filename_lower for indicator in regulatory_indicators):
            return " Регуляторный акт"

        # Для PDF файлов без явных индикаторов - проверяем дополнительные признаки презентаций
        if filename_lower.endswith('.pdf'):
            # Дополнительные признаки PDF-презентаций
            pdf_presentation_hints = [
                'слайд', 'slide', 'deck', 'pitch', 'demo',
                'обзор', 'overview', 'summary', 'brief',
                'материал', 'material', 'лекция', 'lecture'
            ]
            if any(hint in filename_lower for hint in pdf_presentation_hints):
                return " Презентация с контекстным извлечением"

        # Документы по расширению (doc, docx, rtf, txt - точно документы)
        if filename_lower.endswith(('.doc', '.docx', '.rtf', '.txt')):
            return " Регуляторный акт"
        
        # По умолчанию - регуляторный акт (основная специализация системы)
        return " Регуляторный акт"
    
    def _analyze_zip_archive(self, zip_path: str) -> List[Dict[str, Any]]:
        """Анализ ZIP архива с поддержкой русских имен файлов"""
        files_to_process = []
        
        try:
            # Пробуем разные кодировки для поддержки русских имен файлов
            encodings_to_try = ['utf-8', 'cp866', 'windows-1251', 'cp1251']
            
            for encoding in encodings_to_try:
                try:
                    files_found = []
                    
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        for file_info in zip_ref.filelist:
                            if file_info.is_dir() or file_info.filename.startswith('__MACOSX'):
                                continue
                            
                            # Попытка декодирования имени файла
                            try:
                                # Получаем байты имени файла из ZIP
                                if hasattr(file_info, 'flag_bits') and (file_info.flag_bits & 0x800):
                                    # Флаг UTF-8 установлен - имя уже в UTF-8
                                    decoded_filename = file_info.filename
                                else:
                                    # Пробуем декодировать как указанную кодировку
                                    if isinstance(file_info.filename, str):
                                        # Если уже строка, пробуем пересоздать правильно
                                        filename_bytes = file_info.filename.encode('cp437', errors='ignore')
                                        decoded_filename = filename_bytes.decode(encoding, errors='ignore')
                                    else:
                                        # Если байты, декодируем напрямую
                                        decoded_filename = file_info.filename.decode(encoding, errors='ignore')
                                
                                # Проверяем, получили ли читаемое имя (не содержит странные символы)
                                if decoded_filename and not any(ord(c) > 1000 for c in decoded_filename if c.isalpha()):
                                    file_ext = Path(decoded_filename).suffix.lower()
                                    
                                    if file_ext in self.supported_formats:
                                        files_found.append({
                                            'filename': decoded_filename,
                                            'original_filename': file_info.filename,
                                            'size': file_info.file_size,
                                            'extension': file_ext,
                                            'encoding_used': encoding,
                                            'archive_info': file_info
                                        })
                                        
                            except (UnicodeDecodeError, UnicodeEncodeError):
                                continue
                        
                        if files_found:
                            logger.info(f"Успешно декодированы имена файлов с кодировкой {encoding}")
                            return files_found
                            
                except Exception as e:
                    logger.warning(f"Ошибка при попытке кодировки {encoding}: {e}")
                    continue
            
            # Если ни одна кодировка не сработала, используем оригинальные имена
            logger.warning("Не удалось декодировать имена файлов, используем оригинальные")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if not file_info.is_dir() and not file_info.filename.startswith('__MACOSX'):
                        file_ext = Path(file_info.filename).suffix.lower()
                        
                        if file_ext in self.supported_formats:
                            files_to_process.append({
                                'filename': file_info.filename,
                                'original_filename': file_info.filename,
                                'size': file_info.file_size,
                                'extension': file_ext,
                                'encoding_used': 'original',
                                'archive_info': file_info
                            })
                            
        except Exception as e:
            logger.error(f"Ошибка анализа ZIP архива: {e}")
            
        return files_to_process
    
    def _analyze_rar_archive(self, rar_path: str) -> List[Dict[str, Any]]:
        """Анализ RAR архива"""
        files_to_process = []
        
        if not RARFILE_AVAILABLE:
            logger.error("rarfile library not available")
            return files_to_process
            
        try:
            # Проверяем доступность RAR инструментов
            import subprocess
            try:
                # Пробуем команду unrar --version (для unrar-free)
                result = subprocess.run(['unrar', '--version'], capture_output=True, timeout=5)
                if result.returncode == 0:
                    rar_tool_available = True
                else:
                    # Пробуем альтернативную команду для unrar-free
                    subprocess.run(['unrar', '--help'], capture_output=True, check=True, timeout=5)
                    rar_tool_available = True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                logger.warning("RAR binary tool not found, skipping RAR archive")
                return files_to_process
            
            with rarfile.RarFile(rar_path, 'r') as rar_ref:
                for file_info in rar_ref.infolist():
                    if not file_info.is_dir():
                        file_ext = Path(file_info.filename).suffix.lower()
                        
                        if file_ext in self.supported_formats:
                            files_to_process.append({
                                'filename': file_info.filename,
                                'size': file_info.file_size,
                                'extension': file_ext,
                                'archive_info': file_info
                            })
        except Exception as e:
            logger.warning(f"RAR archive not processed due to missing tools: {e}")
            
        return files_to_process
    
    def _analyze_7z_archive(self, archive_path: str) -> List[Dict[str, Any]]:
        """Анализ 7z архива"""
        files_to_process = []
        
        if not PY7ZR_AVAILABLE:
            logger.error("py7zr library not available")
            return files_to_process
            
        try:
            with py7zr.SevenZipFile(archive_path, 'r') as archive_ref:
                for file_info in archive_ref.list():
                    if not file_info.is_directory:
                        file_ext = Path(file_info.filename).suffix.lower()
                        
                        if file_ext in self.supported_formats:
                            files_to_process.append({
                                'filename': file_info.filename,
                                'size': file_info.uncompressed,
                                'extension': file_ext,
                                'archive_info': file_info
                            })
        except Exception as e:
            logger.error(f"Ошибка анализа 7z архива: {e}")
            
        return files_to_process
    
    def _process_files_sequential_universal(self, archive_path: str, archive_type: str, 
                                          files_to_process: List[Dict[str, Any]], 
                                          progress_callback=None, document_type: str = " Автоматическое определение") -> List[Dict[str, Any]]:
        """Последовательная обработка файлов из архива (без потоков для совместимости с Streamlit)"""
        processed_files = []
        total_files = len(files_to_process)
        
        for i, file_info in enumerate(files_to_process):
            try:
                file_result = self._extract_and_upload_file_universal(
                    archive_path,
                    archive_type,
                    file_info,
                    document_type
                )
                processed_files.append(file_result)
                
                # Обновляем прогресс
                if progress_callback:
                    progress_percent = 20 + ((i + 1) / total_files) * 70
                    status_msg = f"Обработано {i + 1}/{total_files} файлов"
                    progress_callback(progress_percent, status_msg)
                    
            except Exception as e:
                error_result = {
                    "filename": file_info['filename'],
                    "status": "error",
                    "error": str(e)
                }
                processed_files.append(error_result)
                logger.error(f"Ошибка обработки файла {file_info['filename']}: {e}")
        
        return processed_files
    
    def _extract_and_upload_file_universal(self, archive_path: str, archive_type: str, 
                                         file_info: Dict[str, Any], document_type: str = " Автоматическое определение") -> Dict[str, Any]:
        """Извлечение файла из архива и загрузка в систему"""
        
        try:
            # Извлекаем файл в зависимости от типа архива
            if archive_type == '.zip':
                file_content = self._extract_from_zip(archive_path, file_info)
            elif archive_type == '.rar' and RARFILE_AVAILABLE:
                file_content = self._extract_from_rar(archive_path, file_info)
            elif archive_type == '.7z' and PY7ZR_AVAILABLE:
                file_content = self._extract_from_7z(archive_path, file_info)
            else:
                raise ValueError(f"Неподдерживаемый тип архива: {archive_type}")
            
            if not file_content:
                return {
                    "filename": file_info['filename'],
                    "status": "error",
                    "error": "Не удалось извлечь файл из архива"
                }
            
            # Проверяем дубликаты
            file_hash = hashlib.sha256(file_content).hexdigest()
            is_duplicate = self._check_file_duplicate(file_hash, file_info['filename'])
            
            if is_duplicate:
                return {
                    "filename": file_info['filename'],
                    "status": "skipped",
                    "reason": "Файл уже существует в системе",
                    "hash": file_hash
                }
            
            # Загружаем файл через API
            upload_result = self._upload_file_to_api(file_content, file_info['filename'], document_type)
            
            return {
                "filename": file_info['filename'],
                "status": "success" if upload_result["success"] else "error",
                "size": len(file_content),
                "hash": file_hash,
                "document_id": upload_result.get("document_id"),
                "upload_result": upload_result
            }
            
        except Exception as e:
            logger.error(f"Ошибка извлечения и загрузки файла {file_info['filename']}: {e}")
            return {
                "filename": file_info['filename'],
                "status": "error",
                "error": str(e)
            }
    
    def _extract_from_zip(self, zip_path: str, file_info: Dict[str, Any]) -> Optional[bytes]:
        """Извлечение файла из ZIP архива с поддержкой кодировок"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Используем оригинальное имя файла из архива для извлечения
                original_filename = file_info.get('original_filename', file_info['filename'])
                return zip_ref.read(original_filename)
        except Exception as e:
            logger.error(f"Ошибка извлечения из ZIP: {e}")
            return None
    
    def _extract_from_rar(self, rar_path: str, file_info: Dict[str, Any]) -> Optional[bytes]:
        """Извлечение файла из RAR архива"""
        if not RARFILE_AVAILABLE:
            return None
            
        try:
            with rarfile.RarFile(rar_path, 'r') as rar_ref:
                return rar_ref.read(file_info['filename'])
        except Exception as e:
            logger.error(f"Ошибка извлечения из RAR: {e}")
            return None
    
    def _extract_from_7z(self, archive_path: str, file_info: Dict[str, Any]) -> Optional[bytes]:
        """Извлечение файла из 7z архива"""
        if not PY7ZR_AVAILABLE:
            return None
            
        try:
            with py7zr.SevenZipFile(archive_path, 'r') as archive_ref:
                extracted_data = archive_ref.read([file_info['filename']])
                return extracted_data[file_info['filename']].read()
        except Exception as e:
            logger.error(f"Ошибка извлечения из 7z: {e}")
            return None
    
    def _check_file_duplicate(self, file_hash: str, filename: str) -> bool:
        """Проверка дубликата файла"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                return False
            
            response = requests.post(
                f"{self.api_gateway_url}/admin/files/check-duplicate",
                json={
                    "files": [{"hash": file_hash, "filename": filename}],
                    "skip_duplicates": True
                },
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('data'):
                    return len(result['data'].get('duplicates', [])) > 0
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки дубликата {filename}: {e}")
            return False
    
    def _upload_file_to_api(self, file_content: bytes, filename: str, document_type: str = " Автоматическое определение") -> Dict[str, Any]:
        """Загрузка файла через API"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                return {"success": False, "error": "Ошибка авторизации"}
            
            # Определяем тип документа
            if document_type == " Автоматическое определение":
                # Автоматическое определение по имени файла 
                auto_detected_type = self._auto_detect_document_type(filename)
                document_category = self._convert_document_type_to_category(auto_detected_type)
                # Обновляем параметры на основе автоопределенного типа
                doc_type_params = self._get_document_type_params(auto_detected_type)
            else:
                # Используем выбранный пользователем тип
                document_category = self._convert_document_type_to_category(document_type)
                # Определяем параметры на основе выбранного типа документа
                doc_type_params = self._get_document_type_params(document_type)
            
            # Подготавливаем multipart данные
            files = {
                'files': (filename, file_content, self._get_content_type(filename))
            }
            
            # Form data
            data = {
                'category': document_category,
                'auto_process': 'true',
                'async_processing': 'false',
                'skip_duplicates': 'true'
            }
            
            # Добавляем параметры типа документа
            data.update(doc_type_params)
            
            response = requests.post(
                f"{self.api_gateway_url}/admin/files/upload",
                files=files,
                data=data,
                headers=headers,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "document_id": result.get('data', {}).get('documents', [{}])[0].get('document_id'),
                    "response": result
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Ошибка загрузки файла {filename}: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_auth_headers(self) -> Optional[Dict[str, str]]:
        """Получение заголовков авторизации"""
        if not hasattr(st.session_state, 'auth_token'):
            return None
        
        return {
            'Authorization': f'Bearer {st.session_state.auth_token}'
        }
    
    def _get_content_type(self, filename: str) -> str:
        """Определение content-type по расширению файла"""
        ext = Path(filename).suffix.lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.txt': 'text/plain',
            '.rtf': 'application/rtf'
        }
        return content_types.get(ext, 'application/octet-stream')
    
    def _determine_document_category(self, filename: str, file_content: bytes) -> str:
        """Определение категории документа по имени файла и содержимому"""
        
        filename_lower = filename.lower()
        
        # Ключевые слова для определения регуляторных документов
        regulatory_keywords = [
            'федеральный', 'закон', 'постановление', 'приказ', 'распоряжение',
            'указ', 'правительство', 'министерство', 'минтранс', 'гост',
            'норматив', 'правила', 'положение', 'инструкция', 'регламент',
            'стандарт', 'методика', 'рекомендации', 'письмо'
        ]
        
        # Ключевые слова для презентаций
        presentation_keywords = [
            'презентация', 'слайд', 'доклад', 'выступление', 'pitch',
            'presentation', 'slides', 'keynote'
        ]
        
        # Проверяем по имени файла
        for keyword in regulatory_keywords:
            if keyword in filename_lower:
                logger.info(f"Определен как регуляторный документ по ключевому слову: {keyword}")
                return 'regulatory'
        
        for keyword in presentation_keywords:
            if keyword in filename_lower:
                logger.info(f"Определен как презентация по ключевому слову: {keyword}")
                return 'presentation'
        
        # Для PDF файлов можем анализировать первые байты содержимого
        if filename_lower.endswith('.pdf') and file_content:
            try:
                # Простая эвристика: презентации часто содержат определенные метаданные
                content_sample = file_content[:2048].decode('utf-8', errors='ignore').lower()
                
                # Ищем признаки презентационного содержимого
                if any(word in content_sample for word in ['powerpoint', 'keynote', 'impress', '/slide']):
                    logger.info("Определен как презентация по содержимому PDF")
                    return 'presentation'
                
                # Ищем признаки нормативного содержимого
                if any(word in content_sample for word in ['статья', 'пункт', 'подпункт', 'глава']):
                    logger.info("Определен как регуляторный документ по содержимому PDF")
                    return 'regulatory'
                    
            except Exception as e:
                logger.warning(f"Не удалось проанализировать содержимое PDF: {e}")
        
        # По умолчанию - регуляторный документ (поскольку в архиве нормативка)
        logger.info("Не удалось определить тип, используем regulatory по умолчанию")
        return 'regulatory'
    
    def _convert_document_type_to_category(self, document_type: str) -> str:
        """Преобразование выбранного типа документа в API категорию"""
        
        type_mapping = {
            " Регуляторный акт": "regulatory", 
            " Презентация с контекстным извлечением": "presentation",
            " Табличные данные (Excel/CSV)": "spreadsheet"
        }
        
        return type_mapping.get(document_type, "auto")
    
    def _get_document_type_params(self, document_type: str) -> Dict[str, str]:
        """Определение параметров на основе типа документа для API"""
        
        if document_type == " Презентация с контекстным извлечением":
            return {
                'document_type': 'presentation',
                'is_presentation': 'true', 
                'contextual_extraction': 'true',
                'presentation_supplement': 'true'
            }
        elif document_type == " Регуляторный акт":
            return {
                'document_type': 'regulatory'
            }
        elif document_type == " Табличные данные (Excel/CSV)":
            return {
                'document_type': 'spreadsheet',
                'enhanced_table_extraction': 'true',
                'preserve_table_structure': 'true'
            }
        elif document_type == " Автоматическое определение":
            # Для автоопределения оставляем пустые параметры - backend сам определит
            return {
                'document_type': 'auto',
                'auto_detect_type': 'true'
            }
        else: # Fallback - регуляторный документ по умолчанию
            return {
                'document_type': 'regulatory'
            }
    
    def _display_processing_results(self, result: Dict[str, Any], archive_type: str):
        """Отображение результатов обработки"""
        
        st.markdown("---")
        st.subheader(f"Результаты обработки {archive_type.upper()[1:]} архива")
        
        # Общая статистика
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Всего файлов", result.get('total_files', 0))
        with col2:
            st.metric("Загружено", result.get('processed', 0))
        with col3:
            st.metric(" Пропущено", result.get('skipped', 0))
        with col4:
            st.metric("Ошибок", result.get('errors', 0))
        
        # Детальная информация о файлах
        if result.get('files'):
            st.subheader(" Детали обработки файлов")
            
            for file_info in result['files']:
                with st.expander(f"{file_info['filename']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        status_emoji = {
                            'success': '[OK]',
                            'skipped': '',
                            'error': '[FAIL]'
                        }.get(file_info['status'], '')
                        
                        st.write(f"**Статус:** {status_emoji} {file_info['status'].title()}")
                        
                        if 'size' in file_info:
                            st.write(f"**Размер:** {file_info['size'] / 1024:.1f} КБ")
                        
                        if 'hash' in file_info:
                            st.write(f"**SHA256:** `{file_info['hash'][:16]}...`")
                    
                    with col2:
                        if file_info['status'] == 'success' and 'document_id' in file_info and file_info['document_id']:
                            st.write(f"**ID документа:** {file_info['document_id'][:8]}...")
                            st.success("Файл успешно загружен в систему")
                            
                            # Показываем информацию о кодировке, если была исправлена
                            if 'encoding_used' in file_info and file_info['encoding_used'] != 'utf-8':
                                st.info(f"**Кодировка:** {file_info['encoding_used']} (автоопределена)")
                                
                        elif file_info['status'] == 'skipped':
                            st.info(f"**Причина:** {file_info.get('reason', 'Файл пропущен')}")
                        elif file_info['status'] == 'error':
                            st.error(f"**Ошибка:** {file_info.get('error', 'Неизвестная ошибка')}")
                            
                            # Дополнительная информация для отладки
                            if 'original_filename' in file_info:
                                st.code(f"Оригинальное имя: {file_info['original_filename']}")
                            if 'encoding_used' in file_info:
                                st.info(f"Попробованная кодировка: {file_info['encoding_used']}")
        
        # Ошибки обработки
        if result.get('error_details'):
            st.subheader(" Ошибки обработки")
            for error in result['error_details']:
                st.error(f"[FAIL] {error}")
        
        # Итоговое сообщение - ИСПРАВЛЕНО: показываем реальный статус
        if result.get('success'):
            if result.get('processed') == result.get('total_files'):
                st.info(f" **Файлы отправлены в очередь обработки**: {result['processed']} из {result['total_files']}")
                st.success(" **Обработка документов запущена в фоне**. Обновите страницу через некоторое время, чтобы увидеть результат.")
                st.info(" **Совет**: Фактическая обработка займет 30-60 секунд на документ. Проверьте статус через несколько минут.")
            else:
                st.info(f" **Частично отправлено**: {result['processed']} из {result['total_files']} файлов добавлены в очередь")
                st.warning(" **Некоторые файлы не удалось отправить**. Проверьте логи выше для деталей.")
        else:
            st.error(" **Ошибка**: Не удалось отправить файлы на обработку. Проверьте подключение к серверу.")