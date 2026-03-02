#!/usr/bin/env python3
"""
🌐 ГЧПРО Admin Panel
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
from admin_panel.components.user_manager import UserManagerComponent
from admin_panel.components.file_uploader import FileUploaderComponent
from admin_panel.components.universal_archive_processor import UniversalArchiveProcessor
from admin_panel.components.task_monitor import TaskMonitorComponent
from admin_panel.components.accessibility_improvements import apply_accessibility_improvements

# Конфигурация Streamlit
st.set_page_config(
    page_title="ГЧПРО Admin Panel",
    page_icon=":gear:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# Кастомные CSS стили
st.markdown("""
<style>
    /* Глобальные стили */
    .main-header {
        background: linear-gradient(90deg, #1f4e79, #2e8bc0);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    
    /* Кнопка выхода в левом нижнем углу */
    .logout-button {
        position: fixed;
        bottom: 20px;
        left: 20px;
        z-index: 1000;
        background: linear-gradient(90deg, #dc3545, #c82333);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: bold;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        cursor: pointer;
    }
    
    .logout-button:hover {
        background: linear-gradient(90deg, #c82333, #bd2130);
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.3);
    }
    
    .metric-card {
        background: #ffffff;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f4e79;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        color: #333333;
    }
    
    .metric-card h4 {
        color: #1f4e79 !important;
        margin-bottom: 0.5rem;
        font-weight: 600;
    }
    
    .metric-card p {
        color: #333333 !important;
        margin: 0.25rem 0;
        font-size: 0.9rem;
    }
    
    .metric-card strong {
        color: #1f4e79 !important;
        font-weight: 600;
    }
    
    .status-online {
        color: #28a745 !important;
        font-weight: bold;
        background: #d4edda;
        padding: 2px 8px;
        border-radius: 4px;
    }
    
    .status-offline {
        color: #dc3545 !important;
        font-weight: bold;
        background: #f8d7da;
        padding: 2px 8px;
        border-radius: 4px;
    }
    
    .status-warning {
        color: #856404 !important;
        font-weight: bold;
        background: #fff3cd;
        padding: 2px 8px;
        border-radius: 4px;
    }
    
    /* Кнопки */
    .stButton > button {
        background: linear-gradient(90deg, #1f4e79, #2e8bc0);
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    
    /* Сайдбар */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #1f4e79, #2e8bc0);
    }
</style>
""", unsafe_allow_html=True)


class AdminPanelApp:
    """Главный класс админ-панели"""
    
    def __init__(self):
        self.auth = AuthenticationManager()
        self.metrics = SystemMetrics()
        self.file_uploader = FileUploaderComponent()
        self.universal_archive_processor = UniversalArchiveProcessor()
        self.task_monitor = TaskMonitorComponent()
        
        # Применяем улучшения accessibility
        self.accessibility = apply_accessibility_improvements()
        
        # Инициализация session state
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'username' not in st.session_state:
            st.session_state.username = None
    
    def run(self):
        """Главная функция запуска админ-панели"""
        
        if not st.session_state.authenticated:
            self.show_login_page()
            return
        
        # Создаем JWT токен для аутентифицированного пользователя
        if 'auth_token' not in st.session_state:
            st.session_state.auth_token = self.auth._create_jwt_token(st.session_state.username)
        
        # Главная страница после входа
        self.show_main_page()
    
    def show_login_page(self):
        """Страница входа в систему"""
        
        # Заголовок
        st.markdown("""
        <div class="main-header">
            <h1>ГЧПРО Admin Panel</h1>
            <p>Веб-интерфейс для управления системой анализа документов</p>
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
                        st.success("✅ Успешный вход в систему!")
                        st.rerun()
                    else:
                        st.error("❌ Неверные учетные данные!")
    
    def show_main_page(self):
        """Главная страница админ-панели"""
        
        # Сайдбар с навигацией
        self.show_sidebar()
        
        # Основной контент - переключение страниц с поддержкой URL параметров
        query_params = st.query_params
        url_page = query_params.get('page', None)

        if not hasattr(st.session_state, 'current_page'):
            # Если есть параметр в URL, используем его, иначе по умолчанию 'files'
            st.session_state.current_page = url_page if url_page in ['files', 'users', 'tasks'] else 'files'

        # Обновляем URL если текущая страница отличается от параметра
        # ВРЕМЕННО ОТКЛЮЧЕНО: проблемы совместимости с некоторыми версиями Streamlit
        # if url_page != st.session_state.current_page:
        #     try:
        #         st.query_params = {"page": st.session_state.current_page}
        #     except:
        #         pass
        
        # Переключение между страницами
        if st.session_state.current_page == 'files':
            self.show_files_page()
        elif st.session_state.current_page == 'users':
            self.show_users_page()
        elif st.session_state.current_page == 'tasks':
            self.show_tasks_page()
    
    def show_sidebar(self):
        """Боковая панель навигации с улучшенной accessibility"""
        
        with st.sidebar:
            # Добавляем улучшенную навигацию
            st.markdown('<div id="main-content">', unsafe_allow_html=True)

            # Улучшенные стили для рабочих кнопок навигации
            st.markdown("""
            <style>
            .nav-buttons .stButton > button {
                width: 100%;
                margin: 4px 0;
                background: linear-gradient(90deg, #1f4e79, #2e8bc0) !important;
                color: white !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 12px !important;
                font-weight: bold !important;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
                transition: all 0.3s ease !important;
            }
            
            .nav-buttons .stButton > button:hover {
                background: linear-gradient(90deg, #2e8bc0, #1f4e79) !important;
                transform: translateY(-2px) !important;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
            }
            
            .nav-buttons .stButton > button[data-testid="nav-file-management"],
            .nav-buttons .stButton > button[data-testid="nav-user-management"] {
                background: rgba(46,139,192,0.1) !important;
                border: 2px solid #2e8bc0 !important;
            }
            </style>
            <div class="nav-buttons">
            """, unsafe_allow_html=True)
            
            # Рабочие кнопки навигации
            if st.button("Управление файлами",
                        use_container_width=True,
                        key="btn-files",
                        help="Загрузка документов, ZIP/RAR/7z архивов, управление файлами"):
                st.session_state.current_page = 'files'
                st.query_params['page'] = 'files'
                st.rerun()

            if st.button("Пользователи",
                        use_container_width=True,
                        key="btn-users",
                        help="Управление пользователями и правами доступа"):
                st.session_state.current_page = 'users'
                st.query_params['page'] = 'users'
                st.rerun()

            if st.button("📊 Мониторинг задач",
                        use_container_width=True,
                        key="btn-tasks",
                        help="Отслеживание прогресса обработки документов"):
                st.session_state.current_page = 'tasks'
                st.query_params['page'] = 'tasks'
                st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)  # Закрываем nav-buttons div

            # Пространство для кнопки выхода внизу
            st.markdown('<div class="spacer" style="flex: 1;"></div>', unsafe_allow_html=True)

            # Кнопка выхода в самом низу sidebar
            st.markdown("---")
            st.markdown("""
            <style>
            .logout-button-container {
                position: fixed;
                bottom: 20px;
                width: calc(100% - 40px);
                z-index: 1000;
            }
            .logout-button-container .stButton > button {
                background: linear-gradient(90deg, #dc3545, #c82333) !important;
                color: white !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 0.75rem 1rem !important;
                font-weight: bold !important;
                width: 100% !important;
            }
            .logout-button-container .stButton > button:hover {
                background: linear-gradient(90deg, #c82333, #bd2130) !important;
                transform: translateY(-1px) !important;
                box-shadow: 0 4px 8px rgba(220,53,69,0.3) !important;
            }
            </style>
            <div class="logout-button-container">
            """, unsafe_allow_html=True)

            if st.button("🚪 Выйти", use_container_width=True, key="logout-btn"):
                self.logout()

            st.markdown("</div>", unsafe_allow_html=True)
    
    
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
        
        st.subheader("📋 Загруженные документы")
        
        # Добавляем поиск
        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input("🔍 Поиск по названию документа", 
                                       placeholder="Введите название документа...",
                                       help="Поиск по названию файла (регистр не важен)")
        with col2:
            # Кнопка поиска
            st.write("")  # Добавляем пустую строку для выравнивания
            search_button = st.button("🔍 Найти", use_container_width=True)
        
        try:
            # Получаем список файлов через API с авторизацией
            if not hasattr(st.session_state, 'auth_token'):
                st.error("❌ Ошибка авторизации")
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
                    st.info(f"📊 Найдено документов: {len(files_data)} из {total_docs}")
                    
                    # Отображаем все загруженные файлы
                    for file_info in files_data:  # Показываем все файлы
                        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                        
                        with col1:
                            st.write(f"📄 {file_info.get('filename', 'N/A')}")
                        with col2:
                            # Storage Service возвращает file_size в байтах, конвертируем в МБ
                            file_size_bytes = file_info.get('file_size', 0)
                            file_size_mb = file_size_bytes / (1024 * 1024) if file_size_bytes else 0
                            st.write(f"{file_size_mb:.1f} МБ")
                        with col3:
                            st.write(file_info.get('status', 'N/A'))
                        with col4:
                            # Storage Service возвращает document_id, а не id
                            doc_id = file_info.get('document_id', file_info.get('id', 'unknown'))
                            if st.button("🗑️", key=f"delete_{doc_id}"):
                                self.delete_file(doc_id, file_info.get('filename', 'unknown'))
                else:
                    st.info("📄 Загруженных документов пока нет")
                    
            elif response.status_code == 401:
                st.error("❌ Ошибка авторизации - обновите страницу")
            else:
                st.error(f"❌ Ошибка получения списка файлов: {response.status_code}")
                
        except Exception as e:
            st.error(f"❌ Ошибка при загрузке списка файлов: {str(e)}")
    
    def delete_file(self, doc_id: str, filename: str):
        """Удаление файла через API"""
        try:
            if not hasattr(st.session_state, 'auth_token'):
                st.error("❌ Ошибка авторизации")
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
                    st.success(f"✅ Файл '{filename}' успешно удален!")
                    st.rerun()  # Обновляем страницу для отображения изменений
                elif response.status_code == 404:
                    st.error(f"❌ Файл '{filename}' не найден")
                elif response.status_code == 401:
                    st.error("❌ Ошибка авторизации - обновите страницу")
                else:
                    try:
                        error_data = response.json()
                        error_message = error_data.get('detail', f'HTTP {response.status_code}')
                    except Exception:
                        error_message = f'HTTP {response.status_code}'
                    st.error(f"❌ Ошибка удаления файла '{filename}': {error_message}")
                    
        except requests.exceptions.Timeout:
            st.error(f"❌ Превышено время ожидания при удалении файла '{filename}'")
        except requests.exceptions.ConnectionError:
            st.error("❌ Нет соединения с API Gateway")
        except Exception as e:
            st.error(f"❌ Ошибка при удалении файла '{filename}': {str(e)}")
    
    def show_users_page(self):
        """Страница управления пользователями"""
        # Убираем дублирующий заголовок - он уже есть в UserManagerComponent
        
        # Инициализация UserManager
        user_manager = UserManagerComponent()
        
        # Используем полноценный интерфейс управления пользователями
        user_manager.render_user_management_interface()
    
    def show_tasks_page(self):
        """Страница мониторинга задач обработки"""
        self.task_monitor.render_task_monitor()
    
    
    


# Точка входа
def main():
    """Главная функция"""
    app = AdminPanelApp()
    app.run()


if __name__ == "__main__":
    main()