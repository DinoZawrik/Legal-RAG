#!/usr/bin/env python3
"""
File Uploader Component для Admin Panel
Компонент для массовой загрузки и управления файлами
"""

import streamlit as st
import requests
import os
import hashlib
import zipfile
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import io


class FileUploaderComponent:
    """Компонент для загрузки и управления файлами"""
    
    def __init__(self):
        self.api_gateway_url = os.getenv('API_GATEWAY_URL', 'http://localhost:8080')
        self.max_file_size = 100 * 1024 * 1024 # 100MB на файл
        self.max_batch_size = 1024 * 1024 * 1024 # 1GB на batch
        self.supported_formats = ['.pdf', '.docx', '.doc', '.txt', '.rtf', '.xlsx', '.xls', '.csv']
    
    def _get_auth_headers(self) -> Optional[Dict[str, str]]:
        """Получение заголовков авторизации"""
        if not hasattr(st.session_state, 'auth_token'):
            return None
        
        return {
            'Authorization': f'Bearer {st.session_state.auth_token}'
            # Content-Type убираем - будет установлен автоматически в зависимости от запроса
        }
    
    def render_upload_interface(self):
        """Отображение интерфейса загрузки документов"""
        
        st.subheader(" Загрузка отдельных документов")
        st.info(" **Совет**: Для архивов используйте вкладку 'Архивы (ZIP/RAR/7z)'")
        
        # Прямо отображаем интерфейс загрузки файлов
        self._render_single_files_upload()
    
    def _render_single_files_upload(self):
        """Загрузка отдельных файлов"""
        
        st.write("**Загрузить отдельные документы**")
        
        uploaded_files = st.file_uploader(
            "Выберите файлы для загрузки",
            type=['pdf', 'docx', 'doc', 'txt', 'rtf', 'xlsx', 'xls', 'csv'],
            accept_multiple_files=True,
            help=f"Поддерживаемые форматы: {', '.join(self.supported_formats)}"
        )
        
        if uploaded_files:
            # Анализ выбранных файлов
            total_size = sum(file.size for file in uploaded_files)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Файлов выбрано", len(uploaded_files))
            with col2:
                st.metric("Общий размер", f"{total_size / (1024*1024):.1f} МБ")
            with col3:
                st.metric("Статус", "Готово к загрузке" if total_size < self.max_batch_size else "Превышен лимит")
            
            # Автоматически установленные настройки обработки
            skip_duplicates = True # Всегда пропускаем дубликаты
            process_immediately = True # Всегда обрабатываем сразу

            # Настройки типа документа
            document_type = st.selectbox(
                    "Тип обработки документа",
                    [
                        " Регуляторный акт",
                        " Презентация с контекстным извлечением",
                        " Табличные данные (Excel/CSV)",
                        " Автоматическое определение"
                    ],
                    help="Выберите тип обработки для оптимизации анализа"
                )

            # Убираем ненужную категорию документов
            category = "Общие"
            
            # Кнопка загрузки
            if st.button(" Загрузить файлы", type="primary", disabled=total_size > self.max_batch_size):
                self._process_files_upload(uploaded_files, skip_duplicates, process_immediately, category, document_type)
    
    def _render_zip_upload(self):
        """Загрузка ZIP архива - УСТАРЕЛО, используйте UniversalArchiveProcessor"""
        
        st.warning(" **Этот интерфейс устарел**")
        st.info(" Используйте новый универсальный процессор архивов во вкладке 'Архивы (ZIP/RAR/7z)' для поддержки всех форматов архивов")
        
        st.write("**Загрузить ZIP архив с документами**")
        
        uploaded_zip = st.file_uploader(
            "Выберите ZIP архив",
            type=['zip'],
            help="ZIP архив может содержать PDF, DOCX, DOC, TXT, RTF файлы"
        )
        
        if uploaded_zip:
            # Анализ ZIP архива
            zip_info = self._analyze_zip_file(uploaded_zip)
            
            if zip_info['error']:
                st.error(f" Ошибка при анализе архива: {zip_info['error']}")
                return
            
            # Информация об архиве
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Файлов в архиве", zip_info['total_files'])
            with col2:
                st.metric("Поддерживаемых", zip_info['supported_files'])
            with col3:
                st.metric("Размер архива", f"{zip_info['archive_size'] / (1024*1024):.1f} МБ")
            
            # Детальная информация
            if zip_info['file_list']:
                with st.expander(" Содержимое архива"):
                    for file_info in zip_info['file_list'][:20]: # Показываем первые 20
                        status_icon = "" if file_info['supported'] else ""
                        st.write(f"{status_icon} {file_info['name']} ({file_info['size_mb']:.1f} МБ)")
                    
                    if len(zip_info['file_list']) > 20:
                        st.write(f"... и еще {len(zip_info['file_list']) - 20} файлов")
            
            # Настройки обработки
            col1, col2 = st.columns(2)
            with col1:
                skip_duplicates = st.checkbox("Пропускать дубликаты", value=True, key="zip_skip_dupes")
                extract_subfolders = st.checkbox("Сохранить структуру папок", value=True)
            
            with col2:
                category = st.selectbox(
                    "Категория документов",
                    ["Общие", "Строительство", "Энергетика", "Отопление", "Нормативы"],
                    key="zip_category"
                )
            
            # Кнопка загрузки
            if zip_info['supported_files'] > 0:
                if st.button(" Обработать архив", type="primary"):
                    self._process_zip_upload(uploaded_zip, skip_duplicates, extract_subfolders, category)
            else:
                st.warning(" В архиве нет поддерживаемых файлов")
    
    def _render_batch_upload(self):
        """Массовая загрузка с drag-and-drop"""
        
        st.write("**Массовая загрузка (drag-and-drop)**")
        
        # Drag and drop зона
        st.markdown("""
        <div style="
            border: 2px dashed #1f4e79;
            border-radius: 10px;
            padding: 2rem;
            text-align: center;
            margin: 1rem 0;
            background: #f8f9fa;
        ">
            <h3> Перетащите файлы сюда</h3>
            <p>Или используйте стандартный загрузчик ниже</p>
            <p><small>Поддерживаемые форматы: PDF, DOCX, DOC, TXT, RTF, XLSX, XLS, CSV</small></p>
        </div>
        """, unsafe_allow_html=True)
        
        # Стандартный загрузчик как fallback
        batch_files = st.file_uploader(
            "Или выберите множество файлов",
            type=['pdf', 'docx', 'doc', 'txt', 'rtf', 'xlsx', 'xls', 'csv', 'zip'],
            accept_multiple_files=True,
            key="batch_uploader"
        )
        
        if batch_files:
            self._render_batch_processing(batch_files)
    
    def _render_batch_processing(self, files: List):
        """Интерфейс обработки batch загрузки"""
        
        # Анализ batch
        batch_analysis = self._analyze_batch_files(files)
        
        # Статистика
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Всего файлов", batch_analysis['total_files'])
        with col2:
            st.metric("ZIP архивов", batch_analysis['zip_count'])
        with col3:
            st.metric("Документов", batch_analysis['document_count'])
        with col4:
            st.metric("Общий размер", f"{batch_analysis['total_size_mb']:.1f} МБ")
        
        # Прогресс обработки
        if 'batch_processing' in st.session_state and st.session_state.batch_processing:
            st.info(" Обработка файлов в процессе...")
            progress_bar = st.progress(st.session_state.get('batch_progress', 0))
        
        # Настройки
        with st.expander(" Настройки обработки"):
            col1, col2 = st.columns(2)
            with col1:
                skip_duplicates = st.checkbox("Пропускать дубликаты", value=True, key="batch_skip_dupes")
                parallel_processing = st.checkbox("Параллельная обработка", value=True)
                auto_categorize = st.checkbox("Автоматическая категоризация", value=False)
            
            with col2:
                default_category = st.selectbox(
                    "Категория по умолчанию",
                    ["Общие", "Строительство", "Энергетика", "Отопление", "Нормативы"],
                    key="batch_category"
                )
                chunk_size = st.slider("Размер chunk (для больших файлов)", 500, 2000, 1000)
        
        # Кнопка запуска
        if st.button(" Начать массовую обработку", type="primary"):
            self._start_batch_processing(files, {
                'skip_duplicates': skip_duplicates,
                'parallel_processing': parallel_processing,
                'auto_categorize': auto_categorize,
                'default_category': default_category,
                'chunk_size': chunk_size
            })
    
    def _analyze_zip_file(self, zip_file) -> Dict[str, Any]:
        """Анализ содержимого ZIP архива"""
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                tmp_file.write(zip_file.read())
                tmp_file_path = tmp_file.name
            
            file_list = []
            supported_count = 0
            
            with zipfile.ZipFile(tmp_file_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if not file_info.is_dir():
                        file_path = Path(file_info.filename)
                        is_supported = file_path.suffix.lower() in self.supported_formats
                        
                        if is_supported:
                            supported_count += 1
                        
                        file_list.append({
                            'name': file_info.filename,
                            'size_mb': file_info.file_size / (1024 * 1024),
                            'supported': is_supported,
                            'extension': file_path.suffix.lower()
                        })
            
            os.unlink(tmp_file_path) # Удаляем временный файл
            
            return {
                'total_files': len(file_list),
                'supported_files': supported_count,
                'archive_size': zip_file.size,
                'file_list': file_list,
                'error': None
            }
            
        except Exception as e:
            return {
                'total_files': 0,
                'supported_files': 0,
                'archive_size': 0,
                'file_list': [],
                'error': str(e)
            }
    
    def _analyze_batch_files(self, files: List) -> Dict[str, Any]:
        """Анализ batch файлов"""
        
        total_files = len(files)
        zip_count = sum(1 for f in files if f.name.lower().endswith('.zip'))
        document_count = total_files - zip_count
        total_size = sum(f.size for f in files)
        
        return {
            'total_files': total_files,
            'zip_count': zip_count,
            'document_count': document_count,
            'total_size_mb': total_size / (1024 * 1024)
        }
    
    def _process_files_upload(self, files: List, skip_duplicates: bool, process_immediately: bool, category: str, document_type: str = " Регуляторный акт"):
        """Обработка загрузки отдельных файлов"""
        
        # Специальное предупреждение для презентаций с контекстным извлечением
        if document_type == " Презентация с контекстным извлечением":
            st.warning(" **Внимание!** Презентации с контекстным извлечением обрабатываются 5-20 минут в зависимости от размера. Пожалуйста, дождитесь завершения.")
            st.info(" Universal Contextual Extraction v2.0 анализирует каждую страницу через AI для сохранения семантических связей между элементами.")
        
        st.info(" Начинаем загрузку файлов...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        uploaded_count = 0
        skipped_count = 0
        error_count = 0
        
        for i, file in enumerate(files):
            try:
                # Специальное сообщение для презентаций
                if document_type == " Презентация с контекстным извлечением":
                    status_text.text(f" Добавляем в очередь контекстного анализа: {file.name}")
                else:
                    status_text.text(f" Добавляем в очередь обработки: {file.name}")
                
                # Проверка дубликатов
                if skip_duplicates and self._check_file_duplicate(file):
                    skipped_count += 1
                    status_text.text(f"Пропущен дубликат: {file.name}")
                    continue
                
                # Загрузка файла
                success = self._upload_single_file(file, category, document_type)
                
                if success:
                    uploaded_count += 1
                else:
                    error_count += 1
                
                progress_bar.progress((i + 1) / len(files))
                
            except Exception as e:
                error_count += 1
                st.error(f"Ошибка при обработке {file.name}: {str(e)}")
        
        # Итоговая статистика
        status_text.empty()
        progress_bar.empty()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.success(f" В очереди: {uploaded_count}")
        with col2:
            st.info(f" Пропущено: {skipped_count}")
        with col3:
            if error_count > 0:
                st.error(f" Ошибок: {error_count}")
        
        st.info(f" **Файлы добавлены в очередь**: {uploaded_count} из {len(files)} файлов отправлены на обработку")
        st.success(" **Обработка документов запущена в фоне**. Обновите страницу через некоторое время, чтобы увидеть результат.")

    
    def _process_zip_upload(self, zip_file, skip_duplicates: bool, extract_subfolders: bool, category: str):
        """Обработка загрузки ZIP архива с интеграцией через API Gateway"""
        
        st.info(" Начинаем обработку ZIP архива...")
        
        try:
            import tempfile
            import os
            import zipfile
            import hashlib
            from io import BytesIO
            
            # Сохраняем архив во временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                tmp_file.write(zip_file.getvalue())
                tmp_path = tmp_file.name
            
            try:
                # Извлекаем файлы из архива
                extracted_files = []
                temp_extracted_dir = tempfile.mkdtemp()
                
                with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                    # Получаем список файлов в архиве
                    file_list = zip_ref.namelist()
                    st.info(f" Найдено файлов в архиве: {len(file_list)}")
                    
                    for file_path in file_list:
                        # Пропускаем директории
                        if file_path.endswith('/'):
                            continue
                            
                        try:
                            # Извлекаем файл
                            zip_ref.extract(file_path, temp_extracted_dir)
                            full_path = os.path.join(temp_extracted_dir, file_path)
                            
                            # Проверяем, что файл успешно извлечен
                            if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                                filename = os.path.basename(file_path)
                                
                                # Фильтруем поддерживаемые форматы
                                if self._is_supported_format(filename):
                                    extracted_files.append({
                                        'path': full_path,
                                        'filename': filename,
                                        'archive_path': file_path
                                    })
                                else:
                                    st.warning(f" Неподдерживаемый формат: {filename}")
                                    
                        except Exception as e:
                            st.warning(f" Ошибка извлечения файла {file_path}: {str(e)}")
                            continue
                
                if not extracted_files:
                    st.error(" В архиве не найдено поддерживаемых файлов")
                    return
                
                st.info(f" Будет обработано файлов: {len(extracted_files)}")
                
                # Создаем прогресс бар
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Загружаем каждый файл через API Gateway
                processed_count = 0
                skipped_count = 0
                error_count = 0
                processed_files = []
                skipped_files = []
                error_files = []
                
                for i, file_info in enumerate(extracted_files):
                    file_path = file_info['path']
                    filename = file_info['filename']
                    
                    status_text.text(f"Обработка: {filename} ({i+1}/{len(extracted_files)})")
                    progress_bar.progress((i + 1) / len(extracted_files))
                    
                    try:
                        # Читаем файл
                        with open(file_path, 'rb') as f:
                            file_content = f.read()
                        
                        # Создаем объект файла для загрузки
                        file_obj = BytesIO(file_content)
                        file_obj.name = filename
                        
                        # Проверяем дубликат если включено
                        if skip_duplicates:
                            file_hash = hashlib.sha256(file_content).hexdigest()
                            if self._check_file_hash_duplicate(file_hash):
                                skipped_count += 1
                                skipped_files.append({
                                    'filename': filename,
                                    'reason': 'Дубликат (SHA256)',
                                    'hash': file_hash
                                })
                                continue
                        
                        # Загружаем файл через API (для ZIP файлов используем регуляторный тип по умолчанию)
                        success = self._upload_single_file(file_obj, category, " Регуляторный акт")
                        
                        if success:
                            processed_count += 1
                            processed_files.append({
                                'filename': filename,
                                'archive_path': file_info['archive_path'],
                                'size': len(file_content)
                            })
                            self._log_upload_action(filename, "zip_extract_upload_success", {
                                'archive_name': zip_file.name,
                                'archive_path': file_info['archive_path'],
                                'category': category,
                                'user': st.session_state.get('username', 'unknown')
                            })
                        else:
                            error_count += 1
                            error_files.append({
                                'filename': filename,
                                'error': 'API upload failed'
                            })
                            
                    except Exception as e:
                        error_count += 1
                        error_files.append({
                            'filename': filename,
                            'error': str(e)
                        })
                        st.warning(f" Ошибка обработки {filename}: {str(e)}")
                        continue
                
                # Очищаем прогресс
                progress_bar.empty()
                status_text.empty()
                
                # Показываем результаты
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.success(f" Обработано: {processed_count}")
                with col2:
                    st.info(f" Пропущено: {skipped_count}")
                with col3:
                    st.error(f" Ошибки: {error_count}")
                
                # Детализация
                if processed_files:
                    with st.expander(f" Успешно обработанные файлы ({len(processed_files)})"):
                        for file_info in processed_files:
                            st.write(f" {file_info['filename']} ({file_info.get('size', 0)} байт)")
                
                if skipped_files:
                    with st.expander(f" Пропущенные файлы ({len(skipped_files)})"):
                        for file_info in skipped_files:
                            reason = file_info.get('reason', 'Unknown')
                            st.write(f" {file_info['filename']} - {reason}")
                
                if error_files:
                    with st.expander(f" Файлы с ошибками ({len(error_files)})"):
                        for file_info in error_files:
                            error = file_info.get('error', 'Unknown error')
                            st.write(f" {file_info['filename']} - {error}")
                
                # Итоговое сообщение - ИСПРАВЛЕНО: показываем реальный статус
                if processed_count > 0:
                    st.info(f" **ZIP файлы отправлены в очередь**: {processed_count} файлов добавлены в систему")
                    st.success(" **Обработка документов запущена в фоне**. Обновите страницу через некоторое время, чтобы увидеть результат.")
                    st.info(" **Совет**: Фактическая обработка займет 30-60 секунд на документ. Проверьте статус через несколько минут.")
                    
                    
                    # Логируем общий результат
                    self._log_upload_action(zip_file.name, "zip_archive_processed", {
                        'total_files': len(extracted_files),
                        'processed': processed_count,
                        'skipped': skipped_count,
                        'errors': error_count,
                        'category': category,
                        'user': st.session_state.get('username', 'unknown')
                    })
                else:
                    st.error(" Не удалось обработать ни одного файла из архива")
                    
                # Очищаем временные файлы
                import shutil
                shutil.rmtree(temp_extracted_dir, ignore_errors=True)
                    
            finally:
                # Удаляем временный архив
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            st.error(f" Ошибка обработки ZIP архива: {str(e)}")
            import traceback
            st.error(f"Подробности: {traceback.format_exc()}")
            
    def _is_supported_format(self, filename: str) -> bool:
        """Проверяет, поддерживается ли формат файла"""
        supported_extensions = {'.pdf', '.docx', '.doc', '.txt', '.rtf', '.xlsx', '.xls', '.csv'}
        file_extension = os.path.splitext(filename.lower())[1]
        return file_extension in supported_extensions
        
    def _check_file_hash_duplicate(self, file_hash: str) -> bool:
        """Проверяет дубликат файла по SHA256 хешу через API"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                return False
                
            response = requests.get(
                f"{self.api_gateway_url}/admin/files/check-duplicate/{file_hash}",
                headers=headers,
                timeout=120 # Увеличиваем timeout для проверки дубликатов больших файлов
            )
            
            if response.status_code == 200:
                return response.json().get('is_duplicate', False)
            else:
                return False
                
        except Exception as e:
            # В случае ошибки считаем, что дубликата нет
            return False
    
    def _start_batch_processing(self, files: List, options: Dict):
        """Запуск массовой обработки"""
        
        st.session_state.batch_processing = True
        st.session_state.batch_progress = 0
        
        st.info(" Запуск массовой обработки...")
        
        try:
            # Обрабатываем файлы по одному
            processed_count = 0
            error_count = 0
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, file in enumerate(files):
                status_text.text(f"Обработка: {file.name}")
                progress_bar.progress((i + 1) / len(files))
                
                try:
                    # Проверяем дубликат
                    skip_duplicates = options.get('skip_duplicates', True)
                    if skip_duplicates and self._check_file_duplicate(file):
                        continue
                    
                    # Загружаем файл
                    success = self._upload_single_file(
                        file, 
                        options.get('category', 'Общие'),
                        options.get('document_type', " Регуляторный акт")
                    )
                    
                    if success:
                        processed_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    st.error(f"Ошибка обработки {file.name}: {str(e)}")
                    continue
            
            # Финальные результаты
            col1, col2 = st.columns(2)
            with col1:
                st.success(f" Обработано: {processed_count}")
            with col2:
                if error_count > 0:
                    st.error(f" Ошибок: {error_count}")
            
            st.info(f" **Файлы отправлены в очередь**: {processed_count} из {len(files)} файлов добавлены в систему")
            st.success(" **Обработка документов запущена в фоне**. Обновите страницу через некоторое время, чтобы увидеть результат.")
            
            
        except Exception as e:
            st.error(f" Критическая ошибка массовой обработки: {str(e)}")
        finally:
            st.session_state.batch_processing = False
            st.session_state.batch_progress = 0
    
    def _check_file_duplicate(self, file) -> bool:
        """Проверка файла на дубликат"""
        
        try:
            # Получаем заголовки авторизации и добавляем Content-Type для JSON
            headers = self._get_auth_headers()
            if not headers:
                st.error(" Ошибка авторизации")
                return False
            
            # Для JSON запросов добавляем Content-Type
            headers['Content-Type'] = 'application/json'
            
            # Вычисляем хеш файла
            file_hash = hashlib.sha256(file.read()).hexdigest()
            file.seek(0) # Возвращаем указатель в начало
            
            # Проверяем через API
            response = requests.post(
                f"{self.api_gateway_url}/admin/files/check-duplicate",
                json={"file_hash": file_hash, "filename": file.name},
                headers=headers,
                timeout=120 # Увеличиваем timeout для проверки дубликатов больших файлов
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('is_duplicate', False)
            elif response.status_code == 401:
                st.error(" Ошибка авторизации - обновите страницу")
                return False
            
            return False
            
        except Exception as e:
            st.error(f" Ошибка проверки дубликата: {str(e)}")
            return False # При ошибке считаем, что дубликата нет
    
    def _upload_single_file(self, file, category: str, document_type: str = " Регуляторный акт") -> bool:
        """Загрузка одного файла через API с логированием"""
        
        try:
            # Получаем токен авторизации (для файлов НЕ устанавливаем Content-Type - requests сделает это автоматически)
            if not hasattr(st.session_state, 'auth_token'):
                st.error(" Ошибка авторизации")
                return False
            
            headers = {
                'Authorization': f'Bearer {st.session_state.auth_token}'
                # НЕ добавляем Content-Type для multipart/form-data - requests установит автоматически
            }
            
            # Логируем начало загрузки
            self._log_upload_action(file.name, "upload_started", {
                'file_size': file.size,
                'category': category,
                'user': st.session_state.get('username', 'unknown')
            })
            
            # Читаем содержимое файла один раз
            file_content = file.read()

            # Определяем параметры на основе типа документа
            # Если выбрано автоматическое определение, определяем тип для каждого файла
            if document_type == " Автоматическое определение":
                # Сначала анализируем по названию
                auto_detected_type = self._auto_detect_document_type(file.name)

                # Для PDF файлов без явных признаков дополнительно проверяем ориентацию
                if auto_detected_type == " Регуляторный акт" and file.name.lower().endswith('.pdf'):
                    orientation = self._check_pdf_orientation(file_content)
                    if orientation == "landscape":
                        auto_detected_type = " Презентация с контекстным извлечением"
                        print(f" PDF {file.name} определен как презентация по горизонтальной ориентации")

                doc_type_params = self._get_document_type_params(auto_detected_type)
                # Добавляем информацию о том, что тип был определен автоматически
                doc_type_params['auto_detected'] = 'true'
                doc_type_params['original_selection'] = 'auto_detect'
                doc_type_params['detected_type'] = auto_detected_type
            else:
                doc_type_params = self._get_document_type_params(document_type)

            # Правильная подготовка файлов для multipart/form-data
            # API Gateway ожидает List[UploadFile], поэтому отправляем как 'files' (множественное число)
            files_data = {
                'files': (file.name, file_content, file.type)
            }
            
            # Form data
            form_data = {
                'category': category,
                'auto_process': 'true',
                'async_processing': 'false',
                'skip_duplicates': 'true'
            }
            
            # Добавляем параметры типа документа
            form_data.update(doc_type_params)
            
            # Отправка на API Gateway с синхронной обработкой
            response = requests.post(
                f"{self.api_gateway_url}/api/upload",
                files={'file': (file.name, file_content, file.type)},
                data={
                    'original_filename': file.name,
                    'document_type': doc_type_params.get('document_type', 'regulatory'),
                    'is_presentation': str(doc_type_params.get('is_presentation', False)).lower(),
                    'presentation_supplement': str(doc_type_params.get('presentation_supplement', False)).lower(),
                    'contextual_extraction': str(doc_type_params.get('contextual_extraction', False)).lower(),
                    'force_reprocess': 'false',
                    'async_processing': 'false'
                },
                headers=headers,
                timeout=1200 # 20 минут для больших документов
            )
            
            if response.status_code == 200:
                response_data = response.json()
                
                if response_data.get('success'):
                    chunks = response_data.get('chunks_created', 0)
                    doc_id = response_data.get('document_id', '')
                    self._log_upload_action(file.name, "upload_success", {
                        'document_id': doc_id,
                        'chunks_created': chunks,
                        'user': st.session_state.get('username', 'unknown')
                    })
                else:
                    self._log_upload_action(file.name, "upload_completed", {
                        'response': str(response_data)[:200],
                        'user': st.session_state.get('username', 'unknown')
                    })
                
                return True
            elif response.status_code == 401:
                st.error(" Ошибка авторизации - обновите страницу")
                self._log_upload_action(file.name, "upload_failed", {
                    'error': 'authorization_error',
                    'user': st.session_state.get('username', 'unknown')
                })
                return False
            elif response.status_code == 413:
                st.error(f" Файл {file.name} слишком большой")
                self._log_upload_action(file.name, "upload_failed", {
                    'error': 'file_too_large',
                    'file_size': file.size,
                    'user': st.session_state.get('username', 'unknown')
                })
                return False
            else:
                error_message = f"API error: {response.status_code}"
                try:
                    error_data = response.json()
                    error_message = error_data.get('detail', error_message)
                except:
                    pass
                
                st.error(f" Ошибка загрузки файла {file.name}: {error_message}")
                self._log_upload_action(file.name, "upload_failed", {
                    'error': error_message,
                    'status_code': response.status_code,
                    'user': st.session_state.get('username', 'unknown')
                })
                return False
            
        except requests.exceptions.Timeout:
            st.error(f" Превышено время ожидания при загрузке {file.name}")
            self._log_upload_action(file.name, "upload_failed", {
                'error': 'timeout',
                'user': st.session_state.get('username', 'unknown')
            })
            return False
        except requests.exceptions.ConnectionError:
            st.error(" Нет соединения с API Gateway")
            self._log_upload_action(file.name, "upload_failed", {
                'error': 'connection_error',
                'user': st.session_state.get('username', 'unknown')
            })
            return False
        except Exception as e:
            st.error(f" Ошибка загрузки файла {file.name}: {str(e)}")
            self._log_upload_action(file.name, "upload_failed", {
                'error': str(e),
                'user': st.session_state.get('username', 'unknown')
            })
            return False

    def _save_task_to_redis(self, file_name: str, task_info: dict):
        """Сохранение задачи в Redis для persistent storage"""
        try:
            import redis
            import json
            import os

            # Подключаемся к Redis
            redis_host = os.getenv('REDIS_HOST', 'legalrag_redis')
            redis_port = int(os.getenv('REDIS_PORT', 6379))

            r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

            # Ключ для сохранения задач пользователя
            user_id = st.session_state.get('username', 'anonymous')
            redis_key = f"legalrag:user_tasks:{user_id}"

            # Получаем текущие задачи
            current_tasks = {}
            existing_data = r.get(redis_key)
            if existing_data:
                current_tasks = json.loads(existing_data)

            # Добавляем новую задачу
            current_tasks[file_name] = task_info

            # Сохраняем с TTL 7 дней
            r.setex(redis_key, 604800, json.dumps(current_tasks)) # 7 дней = 604800 секунд

        except Exception:
            # Не логируем ошибки сохранения - это не критично
            pass
    
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
            return {
                'document_type': 'auto_detect',
                'auto_detect_type': 'true'
            }
        else: # " Регуляторный акт" или любой другой
            return {
                'document_type': 'regulatory'
            }
    
    def _log_upload_action(self, filename: str, action: str, details: Dict[str, Any]):
        """Логирование действий загрузки для аудита"""
        try:
            import logging
            logger = logging.getLogger('admin_panel_uploads')
            
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'filename': filename,
                'action': action,
                'details': details,
                'session_id': st.session_state.get('session_id', 'unknown')
            }
            
            logger.info(f"File upload action: {log_entry}")
            
            # Также можно отправить в API для более детального логирования
            self._send_audit_log(log_entry)
            
        except Exception as e:
            # Не прерываем загрузку из-за ошибок логирования
            print(f"Logging error: {e}")
    
    def _send_audit_log(self, log_entry: Dict[str, Any]):
        """Отправка лога аудита в API (асинхронно)"""
        try:
            headers = self._get_auth_headers()
            if headers:
                # Для JSON запросов добавляем Content-Type
                headers['Content-Type'] = 'application/json'
                
                # Отправляем лог в фоновом режиме, не блокируя основной процесс
                requests.post(
                    f"{self.api_gateway_url}/admin/audit/log",
                    json=log_entry,
                    headers=headers,
                    timeout=5
                )
        except:
            # Игнорируем ошибки аудита, чтобы не влиять на основной функционал
            pass

    def _save_task_to_localStorage(self, file_name: str, task_info: dict):
        """Сохранение задачи в localStorage браузера"""
        try:
            import json
            task_json = json.dumps(task_info).replace("'", "\\'")
            st.markdown(f"""
            <script>
            // Получаем существующие задачи
            let tasks = {{}};
            try {{
                const stored = window.localStorage.getItem('legalrag_tasks');
                if (stored) {{
                    tasks = JSON.parse(stored);
                }}
            }} catch (e) {{
                console.log('Error parsing stored tasks:', e);
            }}

            // Добавляем новую задачу
            tasks['{file_name}'] = {task_json};

            // Сохраняем обратно в localStorage
            window.localStorage.setItem('legalrag_tasks', JSON.stringify(tasks));
            console.log('Task saved to localStorage:', '{file_name}');
            </script>
            """, unsafe_allow_html=True)
        except Exception as e:
            print(f"Ошибка сохранения задачи в localStorage: {e}")

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
            # Дополнительные признаки PDF-презентаций по названию
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

    def _check_pdf_orientation(self, file_content: bytes) -> str:
        """Определение ориентации PDF страниц для выявления презентаций"""
        try:
            # Используем PyPDF2 если доступен, иначе возвращаем неопределенный результат
            try:
                import PyPDF2
            except ImportError:
                # Если PyPDF2 недоступен, проверяем через простой анализ содержимого
                return self._simple_pdf_orientation_check(file_content)

            pdf_stream = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)

            landscape_count = 0
            portrait_count = 0

            # Проверяем первые 5 страниц (достаточно для определения)
            pages_to_check = min(5, len(pdf_reader.pages))

            for i in range(pages_to_check):
                page = pdf_reader.pages[i]
                mediabox = page.mediabox

                width = float(mediabox.width)
                height = float(mediabox.height)

                # Учитываем поворот страницы
                rotation = page.get('/Rotate', 0)
                if rotation in [90, 270]:
                    width, height = height, width

                if width > height:
                    landscape_count += 1
                else:
                    portrait_count += 1

            # Если больше половины страниц в горизонтальной ориентации
            if landscape_count > portrait_count:
                return "landscape"
            else:
                return "portrait"

        except Exception as e:
            print(f"Ошибка определения ориентации PDF: {e}")
            return "unknown"

    def _simple_pdf_orientation_check(self, file_content: bytes) -> str:
        """Простая проверка ориентации PDF без библиотек"""
        try:
            # Ищем MediaBox в PDF содержимом
            content_str = file_content.decode('latin-1', errors='ignore')

            # Ищем паттерны MediaBox
            import re
            mediabox_pattern = r'/MediaBox\s*\[\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*\]'
            matches = re.findall(mediabox_pattern, content_str)

            landscape_count = 0
            portrait_count = 0

            for match in matches[:5]: # Первые 5 найденных MediaBox
                try:
                    x1, y1, x2, y2 = map(float, match)
                    width = abs(x2 - x1)
                    height = abs(y2 - y1)

                    if width > height:
                        landscape_count += 1
                    else:
                        portrait_count += 1
                except:
                    continue

            if landscape_count > portrait_count and landscape_count > 0:
                return "landscape"
            else:
                return "portrait"

        except Exception:
            return "unknown"