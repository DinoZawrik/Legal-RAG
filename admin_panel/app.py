#!/usr/bin/env python3
"""
ГЧПРО Admin Panel
Веб-интерфейс для управления системой ГЧПРО
"""

import streamlit as st
import os
import sys
import requests
from pathlib import Path

# Добавляем пути для импорта модулей из родительской директории
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# Импорты компонентов админ-панели
from admin_panel.components.auth import AuthenticationManager
from admin_panel.components.metrics import SystemMetrics
from admin_panel.components.file_uploader import FileUploaderComponent
from admin_panel.components.universal_archive_processor import UniversalArchiveProcessor
from admin_panel.components.accessibility_improvements import apply_accessibility_improvements

# Конфигурация Streamlit
st.set_page_config(
    page_title="LegalRAG Admin",
    page_icon=":gear:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# Кастомные CSS стили
with open(current_dir / "static" / "style.css") as css_file:
    st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)


# Mapping of raw filenames to human-readable Russian names
_DOCUMENT_NAME_MAP = {
    "grazhdanskij_kodeks_rf.pdf": "Гражданский кодекс РФ",
    "grazhdanskij_kodeks_rf.txt": "Гражданский кодекс РФ",
    "grazhdanskij_kodeks_rf": "Гражданский кодекс РФ",
    "semejnyj_kodeks_rf.pdf": "Семейный кодекс РФ",
    "semejnyj_kodeks_rf.txt": "Семейный кодекс РФ",
    "semejnyj_kodeks_rf": "Семейный кодекс РФ",
    "skodeksrf.pdf": "Семейный кодекс РФ",
    "labor_code_excerpt.txt": "Трудовой кодекс РФ (выдержка)",
    "labor_code_excerpt": "Трудовой кодекс РФ (выдержка)",
    "trudovoj_kodeks_rf.pdf": "Трудовой кодекс РФ",
    "zakon_o_zashite_prav_potrebitelej.txt": "Закон о защите прав потребителей",
    "zakon_o_zashite_prav_potrebitelej": "Закон о защите прав потребителей",
    "zhilishchnyj_kodeks_rf.pdf": "Жилищный кодекс РФ",
    "zhilishchnyj_kodeks_rf.txt": "Жилищный кодекс РФ",
    "zhilishchnyj_kodeks_rf": "Жилищный кодекс РФ",
    "test_admin_upload.txt": "Тестовый документ (admin)",
    "test_smoke.txt": "Тестовый документ (smoke)",
}


def _human_doc_name(filename: str) -> str:
    """Convert raw filename to human-readable Russian name."""
    if not filename:
        return "Без названия"
    # Exact match
    if filename in _DOCUMENT_NAME_MAP:
        return _DOCUMENT_NAME_MAP[filename]
    # Case-insensitive
    for key, val in _DOCUMENT_NAME_MAP.items():
        if key.lower() == filename.lower():
            return val
    # Fallback: strip extension, replace underscores, title case
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    return name.replace('_', ' ').title()


class AdminPanelApp:
    """Главный класс админ-панели"""
    
    def __init__(self):
        self.auth = AuthenticationManager()
        self.metrics = SystemMetrics()
        self.file_uploader = FileUploaderComponent()
        self.universal_archive_processor = UniversalArchiveProcessor()
        
        # Применяем улучшения accessibility
        self.accessibility = apply_accessibility_improvements()
        
        # Инициализация session state
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'username' not in st.session_state:
            st.session_state.username = None
    
    def run(self):
        """Главная функция запуска админ-панели"""
        
        # Автоматический вход без пароля
        if not st.session_state.authenticated:
            st.session_state.authenticated = True
            st.session_state.username = "admin"
        
        if 'auth_token' not in st.session_state:
            st.session_state.auth_token = self.auth._create_jwt_token(st.session_state.username)
        
        self.show_main_page()
    
    def show_login_page(self):
        """Страница входа в систему"""
        
        # Заголовок
        st.markdown("""
        <div class="main-header">
            <h1>LegalRAG Admin</h1>
            <p>Панель управления системой анализа документов</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Форма входа
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.subheader("Вход в систему")
            
            with st.form("login_form"):
                username = st.text_input("Имя пользователя", placeholder="admin")
                password = st.text_input("Пароль", type="password", placeholder="Введите пароль")
                submit_button = st.form_submit_button("Войти", use_container_width=True)
                
                if submit_button:
                    if self.auth.authenticate(username, password):
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.success(" Успешный вход в систему!")
                        st.rerun()
                    else:
                        st.error(" Неверные учетные данные!")
    
    def show_main_page(self):
        """Главная страница админ-панели"""
        self.show_sidebar()
        self.show_files_page()
    
    def show_sidebar(self):
        """Боковая панель навигации"""
        
        with st.sidebar:
            st.markdown("""
            <div style="text-align:center; padding: 1rem 0 1.5rem;">
                <div style="font-size: 1.3rem; font-weight: 700; color: #fff; letter-spacing: 0.05em;">LegalRAG</div>
                <div style="font-size: 0.75rem; color: rgba(255,255,255,0.5); letter-spacing: 0.08em; text-transform: uppercase;">Admin Panel</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")

            # Logout
            if st.button("Выйти", use_container_width=True, key="logout-btn"):
                self.logout()
    
    
    def logout(self):
        """Выход из системы"""
        st.session_state.authenticated = False
        st.session_state.username = None
        if 'current_page' in st.session_state:
            del st.session_state.current_page
        st.rerun()
    
    def show_files_page(self):
        """Страница управления файлами с универсальной поддержкой архивов"""
        st.header("Управление файлами")
        
        # Табы для разных типов загрузки 
        tab1, tab2 = st.tabs(["Отдельные файлы", "Архивы (ZIP/RAR/7z)"])
        
        with tab1:
            # Используем компонент FileUploader для отдельных файлов
            self.file_uploader.render_upload_interface()
        
        with tab2:
            # Используем новый универсальный архивный процессор
            self.universal_archive_processor.render_universal_archive_upload()
        
        # Дополнительно - список существующих файлов
        st.markdown("---")
        
        st.subheader(" Загруженные документы")
        
        # Добавляем поиск
        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input(" Поиск по названию документа", 
                                       placeholder="Введите название документа...",
                                       help="Поиск по названию файла (регистр не важен)")
        with col2:
            # Кнопка поиска
            st.write("") # Добавляем пустую строку для выравнивания
            search_button = st.button(" Найти", use_container_width=True)
        
        try:
            # Получаем список файлов через API с авторизацией
            if not hasattr(st.session_state, 'auth_token'):
                st.error(" Ошибка авторизации")
                return
                
            headers = {
                'Authorization': f'Bearer {st.session_state.auth_token}',
                'Content-Type': 'application/json'
            }
            
            # Подготавливаем параметры поиска
            list_params = {"limit": 100, "offset": 0}
            
            # Добавляем поиск если введен запрос
            if search_query:
                list_params["search"] = search_query
            response = requests.get(f"{os.getenv('API_GATEWAY_URL', 'http://localhost:8080')}/admin/files/list", 
                                   headers=headers, params=list_params, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                # Storage Service возвращает структуру: {"success": true, "data": {"documents": [...], "total": N}}
                if response_data.get('success'):
                    files_data = response_data.get('data', {}).get('documents', [])
                else:
                    files_data = []
                
                if files_data:
                    # Отображаем информацию о количестве документов
                    total_docs = response_data.get('data', {}).get('total', len(files_data))
                    st.info(f"Найдено документов: {len(files_data)} из {total_docs}")

                    # Table header
                    h1, h2, h3, h4 = st.columns([3, 1, 1, 1])
                    h1.markdown("**Документ**")
                    h2.markdown("**Размер**")
                    h3.markdown("**Статус**")
                    h4.markdown("**Действие**")

                    # Отображаем все загруженные файлы
                    for file_info in files_data:
                        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                        
                        with col1:
                            raw_name = file_info.get('filename', 'N/A')
                            display_name = _human_doc_name(raw_name)
                            st.write(f"📄 {display_name}")
                        with col2:
                            file_size_bytes = file_info.get('file_size', 0)
                            if file_size_bytes > 1024 * 1024:
                                st.write(f"{file_size_bytes / (1024*1024):.1f} МБ")
                            elif file_size_bytes > 1024:
                                st.write(f"{file_size_bytes / 1024:.0f} КБ")
                            else:
                                st.write(f"{file_size_bytes} Б")
                        with col3:
                            status = file_info.get('status', 'N/A')
                            color = {"processed": "#10b981", "completed": "#10b981", "processing": "#3b82f6"}.get(status, "#94a3b8")
                            st.markdown(f'<span style="color:{color};font-weight:600;">{status}</span>', unsafe_allow_html=True)
                        with col4:
                            doc_id = file_info.get('document_id', file_info.get('id', 'unknown'))
                            # Confirmation flow
                            confirm_key = f"confirm_delete_{doc_id}"
                            if st.session_state.get(confirm_key):
                                sc1, sc2 = st.columns(2)
                                with sc1:
                                    if st.button("✅ Да", key=f"yes_{doc_id}", use_container_width=True):
                                        st.session_state[confirm_key] = False
                                        self.delete_file(doc_id, raw_name)
                                with sc2:
                                    if st.button("❌ Нет", key=f"no_{doc_id}", use_container_width=True):
                                        st.session_state[confirm_key] = False
                                        st.rerun()
                            else:
                                if st.button("🗑️ Удалить", key=f"delete_{doc_id}"):
                                    st.session_state[confirm_key] = True
                                    st.rerun()
                else:
                    st.info(" Загруженных документов пока нет")
                    
            elif response.status_code == 401:
                st.error(" Ошибка авторизации - обновите страницу")
            else:
                st.error(f" Ошибка получения списка файлов: {response.status_code}")
                
        except Exception as e:
            st.error(f" Ошибка при загрузке списка файлов: {str(e)}")
    
    def delete_file(self, doc_id: str, filename: str):
        """Удаление файла через API"""
        try:
            if not hasattr(st.session_state, 'auth_token'):
                st.error(" Ошибка авторизации")
                return
            
            headers = {
                'Authorization': f'Bearer {st.session_state.auth_token}',
                'Content-Type': 'application/json'
            }
            
            with st.spinner(f"Удаление файла {filename}..."):
                response = requests.delete(
                    f"{os.getenv('API_GATEWAY_URL', 'http://localhost:8080')}/admin/files/{doc_id}",
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    st.success(f" Файл '{filename}' успешно удален!")
                    st.rerun() # Обновляем страницу для отображения изменений
                elif response.status_code == 404:
                    st.error(f" Файл '{filename}' не найден")
                elif response.status_code == 401:
                    st.error(" Ошибка авторизации - обновите страницу")
                else:
                    try:
                        error_data = response.json()
                        error_message = error_data.get('detail', f'HTTP {response.status_code}')
                    except Exception:
                        error_message = f'HTTP {response.status_code}'
                    st.error(f" Ошибка удаления файла '{filename}': {error_message}")
                    
        except requests.exceptions.Timeout:
            st.error(f" Превышено время ожидания при удалении файла '{filename}'")
        except requests.exceptions.ConnectionError:
            st.error(" Нет соединения с API Gateway")
        except Exception as e:
            st.error(f" Ошибка при удалении файла '{filename}': {str(e)}")
    

    
    
    


# Точка входа
def main():
    """Главная функция"""
    app = AdminPanelApp()
    app.run()


if __name__ == "__main__":
    main()