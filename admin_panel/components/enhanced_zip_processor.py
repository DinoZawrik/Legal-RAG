#!/usr/bin/env python3
"""
Enhanced ZIP Processor - Улучшенная обработка ZIP архивов
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
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

class EnhancedZipProcessor:
    """Улучшенный процессор ZIP архивов с параллельной обработкой"""
    
    def __init__(self):
        self.api_gateway_url = os.getenv('API_GATEWAY_URL', 'http://localhost:8080')
        self.supported_formats = ['.pdf', '.docx', '.doc', '.txt', '.rtf']
        self.max_file_size = 100 * 1024 * 1024 # 100MB
        self.max_archive_size = 500 * 1024 * 1024 # 500MB
        self.max_concurrent_uploads = 3 # Количество параллельных загрузок
        
    def process_zip_archive_enhanced(self, uploaded_file, progress_callback=None) -> Dict[str, Any]:
        """
        Улучшенная обработка ZIP архива с параллельной загрузкой и прогресс-баром
        """
        result = {
            "success": False,
            "total_files": 0,
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "files": [],
            "error_details": []
        }
        
        try:
            # Сохраняем архив во временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                zip_path = tmp_file.name
            
            # Анализируем содержимое архива
            files_to_process = self._analyze_archive(zip_path)
            result["total_files"] = len(files_to_process)
            
            if not files_to_process:
                result["error_details"].append("Архив не содержит поддерживаемых файлов")
                return result
            
            # Обновляем прогресс
            if progress_callback:
                progress_callback(0, f"Найдено {len(files_to_process)} файлов для обработки")
            
            # Параллельная обработка файлов
            processed_files = self._process_files_parallel(
                zip_path, 
                files_to_process, 
                progress_callback
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
            os.unlink(zip_path)
            
            result["success"] = result["processed"] > 0
            
            if progress_callback:
                progress_callback(100, f"Завершено: {result['processed']} загружено, {result['skipped']} пропущено, {result['errors']} ошибок")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка обработки ZIP архива: {e}")
            result["error_details"].append(f"Критическая ошибка: {str(e)}")
            return result
    
    def _analyze_archive(self, zip_path: str) -> List[Dict[str, Any]]:
        """Анализ содержимого архива"""
        files_to_process = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    # Пропускаем папки
                    if file_info.is_dir():
                        continue
                    
                    # Получаем расширение файла
                    file_path = Path(file_info.filename)
                    file_ext = file_path.suffix.lower()
                    
                    # Проверяем поддерживаемые форматы
                    if file_ext in self.supported_formats:
                        # Проверяем размер файла
                        if file_info.file_size <= self.max_file_size:
                            files_to_process.append({
                                "filename": file_info.filename,
                                "size": file_info.file_size,
                                "extension": file_ext,
                                "path": file_path
                            })
                        else:
                            logger.warning(f"Файл {file_info.filename} слишком большой: {file_info.file_size} bytes")
                    else:
                        logger.debug(f"Неподдерживаемый формат файла: {file_info.filename}")
        
        except Exception as e:
            logger.error(f"Ошибка анализа архива: {e}")
        
        return files_to_process
    
    def _process_files_parallel(self, zip_path: str, files_list: List[Dict], progress_callback=None) -> List[Dict[str, Any]]:
        """Параллельная обработка файлов из архива"""
        
        results = []
        total_files = len(files_list)
        processed_count = 0
        
        # Создаем ThreadPoolExecutor для параллельной обработки
        with ThreadPoolExecutor(max_workers=self.max_concurrent_uploads) as executor:
            # Запускаем задачи
            future_to_file = {
                executor.submit(self._process_single_file_from_zip, zip_path, file_info): file_info
                for file_info in files_list
            }
            
            # Обрабатываем результаты по мере готовности
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                processed_count += 1
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Обновляем прогресс
                    if progress_callback:
                        progress_percent = int((processed_count / total_files) * 100)
                        status = result.get('status', 'unknown')
                        progress_callback(
                            progress_percent, 
                            f"Обработано {processed_count}/{total_files} файлов. Последний: {result['filename']} ({status})"
                        )
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки файла {file_info['filename']}: {e}")
                    results.append({
                        "filename": file_info['filename'],
                        "status": "error",
                        "error": str(e)
                    })
        
        return results
    
    def _process_single_file_from_zip(self, zip_path: str, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка одного файла из ZIP архива"""
        
        filename = file_info['filename']
        
        try:
            # Извлекаем файл из архива
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_data = zip_ref.read(filename)
            
            # Вычисляем хэш файла для проверки дубликатов
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # Проверяем дубликат через API
            if self._check_file_duplicate(file_hash):
                return {
                    "filename": filename,
                    "status": "skipped",
                    "message": "Файл уже существует в системе",
                    "hash": file_hash
                }
            
            # Загружаем файл через API
            upload_result = self._upload_file_to_api(filename, file_data)
            
            if upload_result["success"]:
                return {
                    "filename": filename,
                    "status": "success",
                    "message": "Файл успешно загружен",
                    "document_id": upload_result.get("document_id"),
                    "size": len(file_data),
                    "hash": file_hash
                }
            else:
                return {
                    "filename": filename,
                    "status": "error",
                    "error": upload_result.get("error", "Unknown error"),
                    "hash": file_hash
                }
                
        except Exception as e:
            logger.error(f"Ошибка обработки файла {filename}: {e}")
            return {
                "filename": filename,
                "status": "error",
                "error": str(e)
            }
    
    def _check_file_duplicate(self, file_hash: str) -> bool:
        """Проверка дубликата файла по хэшу"""
        try:
            auth_headers = self._get_auth_headers()
            response = requests.get(
                f"{self.api_gateway_url}/admin/files/check-duplicate/{file_hash}",
                headers=auth_headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("is_duplicate", False)
            else:
                # Если API недоступно, считаем что дубликата нет
                logger.warning(f"Не удалось проверить дубликат: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка проверки дубликата: {e}")
            return False
    
    def _upload_file_to_api(self, filename: str, file_data: bytes) -> Dict[str, Any]:
        """Загрузка файла через API"""
        try:
            auth_headers = self._get_auth_headers()
            
            files = {
                'files': (filename, file_data, 'application/octet-stream')
            }
            data = {
                'category': 'general',
                'auto_process': 'true'
            }
            
            response = requests.post(
                f"{self.api_gateway_url}/admin/files/upload",
                files=files,
                data=data,
                headers=auth_headers,
                timeout=1200 # 20 минут для контекстного извлечения презентаций
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    # Извлекаем информацию о загруженном файле
                    file_results = result.get("results", [])
                    if file_results:
                        file_result = file_results[0]
                        return {
                            "success": True,
                            "document_id": file_result.get("document_id"),
                            "message": file_result.get("message")
                        }
                
                return {
                    "success": False,
                    "error": result.get("error", "Unknown API error")
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}..."
                }
                
        except Exception as e:
            logger.error(f"Ошибка загрузки файла {filename}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Получение заголовков авторизации"""
        if hasattr(st.session_state, 'auth_token') and st.session_state.auth_token:
            return {
                'Authorization': f'Bearer {st.session_state.auth_token}'
            }
        return {}
    
    def render_enhanced_zip_upload(self):
        """Рендеринг улучшенного интерфейса загрузки ZIP архивов"""
        
        st.subheader(" Улучшенная загрузка ZIP архивов")
        
        # Информация о возможностях
        with st.expander(" Возможности улучшенной обработки", expanded=False):
            st.write("""
            **Улучшения:**
            - Параллельная обработка файлов (до 3 одновременно)
            - Подробный прогресс-бар с информацией о процессе 
            - Интеллектуальная проверка дубликатов
            - Детальная статистика обработки
            - Оптимизированная производительность
            - Улучшенная обработка ошибок
            
            **Поддерживаемые форматы:** PDF, DOCX, DOC, TXT, RTF
            
            **Ограничения:**
            - Максимальный размер файла: 100 МБ
            - Максимальный размер архива: 500 МБ
            """)
        
        # Загрузка архива
        uploaded_zip = st.file_uploader(
            "Выберите ZIP архив",
            type=['zip'],
            help="Загрузите ZIP архив с документами для обработки"
        )
        
        if uploaded_zip is not None:
            # Информация об архиве
            file_size = len(uploaded_zip.getvalue())
            file_size_mb = file_size / (1024 * 1024)
            
            st.info(f" Архив: **{uploaded_zip.name}** ({file_size_mb:.1f} МБ)")
            
            # Проверка размера архива
            if file_size > self.max_archive_size:
                st.error(f" Архив слишком большой! Максимальный размер: {self.max_archive_size/(1024*1024):.0f} МБ")
                return
            
            # Кнопка обработки
            if st.button(" Обработать архив (улучшенно)", key="enhanced_zip_process"):
                
                # Контейнеры для прогресса и результатов
                progress_container = st.container()
                results_container = st.container()
                
                with progress_container:
                    st.info(" Начинаем обработку архива...")
                    
                    # Прогресс-бар и статус
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Функция обратного вызова для обновления прогресса
                    def update_progress(percent: int, message: str):
                        progress_bar.progress(percent)
                        status_text.text(message)
                
                # Запускаем обработку
                result = self.process_zip_archive_enhanced(uploaded_zip, update_progress)
                
                # Отображаем результаты
                with results_container:
                    self._display_processing_results(result)
    
    def _display_processing_results(self, result: Dict[str, Any]):
        """Отображение результатов обработки"""
        
        if result["success"]:
            st.success(f" Архив успешно обработан!")
        else:
            st.warning(" Обработка архива завершена с ошибками")
        
        # Статистика
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(" Всего файлов", result["total_files"])
        
        with col2:
            st.metric(" Загружено", result["processed"])
        
        with col3:
            st.metric(" Пропущено", result["skipped"])
        
        with col4:
            st.metric(" Ошибок", result["errors"])
        
        # Детальная информация о файлах
        if result["files"]:
            st.subheader(" Детальная информация")
            
            # Фильтры
            filter_status = st.selectbox(
                "Фильтр по статусу:",
                ["Все", "Успешно", "Пропущено", "Ошибки"],
                key="enhanced_filter"
            )
            
            # Фильтруем файлы
            filtered_files = result["files"]
            if filter_status != "Все":
                status_map = {
                    "Успешно": "success",
                    "Пропущено": "skipped", 
                    "Ошибки": "error"
                }
                filtered_files = [f for f in result["files"] if f["status"] == status_map[filter_status]]
            
            # Отображаем файлы
            for file_info in filtered_files:
                status_icon = {
                    "success": "",
                    "skipped": "",
                    "error": ""
                }.get(file_info["status"], "")
                
                with st.expander(f"{status_icon} {file_info['filename']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Статус:** {file_info['status']}")
                        st.write(f"**Сообщение:** {file_info.get('message', 'N/A')}")
                    
                    with col2:
                        if "size" in file_info:
                            st.write(f"**Размер:** {file_info['size']} байт")
                        if "document_id" in file_info and file_info['document_id']:
                            st.write(f"**ID документа:** {file_info['document_id'][:8]}...")
                        if "hash" in file_info:
                            st.write(f"**Хэш:** {file_info['hash'][:16]}...")
                    
                    if "error" in file_info:
                        st.error(f"Ошибка: {file_info['error']}")
        
        # Ошибки обработки
        if result["error_details"]:
            st.subheader(" Ошибки обработки")
            for error in result["error_details"]:
                st.error(error)

# Экспорт основного класса
__all__ = ['EnhancedZipProcessor']