#!/usr/bin/env python3
"""
👥 User Manager Component для Admin Panel
Управление пользователями и администраторами системы
"""

import streamlit as st
import requests
import pandas as pd
from typing import Dict, List, Any, Optional
import os


class UserManagerComponent:
    """Компонент для управления Telegram пользователями"""
    
    def __init__(self):
        self.api_gateway_url = os.getenv('API_GATEWAY_URL', 'http://localhost:8080')
        # Управляем только правами загрузки через Telegram бот
        self.user_permissions = {
            'upload_documents': 'Может загружать документы через бота',
            'view_only': 'Только просмотр (без загрузки)'
        }
    
    def _get_auth_headers(self) -> Optional[Dict[str, str]]:
        """Получение заголовков авторизации"""
        if not hasattr(st.session_state, 'auth_token'):
            return None
        
        return {
            'Authorization': f'Bearer {st.session_state.auth_token}',
            'Content-Type': 'application/json'
        }
    
    def render_user_management_interface(self):
        """Отображение интерфейса управления Telegram пользователями"""
        
        # Глобальная инициализация session_state
        if 'selected_requests' not in st.session_state:
            st.session_state.selected_requests = set()
        
        st.subheader("👥 Управление Telegram пользователями")
        
        # Информация о текущей системе
        st.info("🤖 Здесь вы управляете правами пользователей Telegram бота на загрузку документов")
        
        # Табы для разных разделов
        tab1, tab2 = st.tabs([
            "📋 Telegram пользователи",
            "📝 Запросы на права"
        ])

        with tab1:
            self._render_telegram_users_list()

        with tab2:
            self._render_permission_requests_list()
    
    def _render_telegram_users_list(self):
        """Список Telegram пользователей с правами загрузки"""
        
        st.write("**Пользователи Telegram бота**")
        
        # Получаем текущий список админов из переменной окружения
        current_admin_ids = self._get_current_telegram_admin_ids()
        
        # Фильтры
        col1, col2, col3 = st.columns(3)
        
        with col1:
            permission_filter = st.selectbox(
                "Права доступа",
                ["Все", "Может загружать", "Только просмотр"],
                key="telegram_permission_filter"
            )
        
        with col2:
            # Убираем фильтр по статусу - он не используется
            st.empty()  # Пустая колонка для сохранения макета
        
        with col3:
            search_query = st.text_input(
                "🔍 Поиск по имени или @username",
                key="telegram_search",
                placeholder="Введите имя, фамилию или @username..."
            )
        
        # Получение данных Telegram пользователей
        telegram_users_data = self._get_telegram_users_data()
        
        if not telegram_users_data:
            st.info("📝 Загружаем данные Telegram пользователей...")
            return
        
        # Применение фильтров (без статуса)
        filtered_users = self._filter_telegram_users(telegram_users_data, permission_filter, None, search_query)
        
        # Таблица пользователей с чекбоксами для выбора
        if filtered_users:
            # Инициализация session state для выбранных пользователей
            if 'selected_users' not in st.session_state:
                st.session_state.selected_users = set()
            
            # Кнопка "Выбрать всех / Снять выбор"
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("🔄 Выбрать всех" if len(st.session_state.selected_users) == 0 else "❌ Снять выбор"):
                    if len(st.session_state.selected_users) == 0:
                        st.session_state.selected_users = {user['telegram_id'] for user in filtered_users}
                    else:
                        st.session_state.selected_users = set()
                    st.rerun()
            
            # Отображение пользователей с чекбоксами
            st.markdown("### 👥 Список пользователей Telegram")
            
            # Заголовки колонок (убираем колонку статуса)
            col1, col2, col3, col4 = st.columns([0.5, 1.5, 3, 3])
            with col1:
                st.markdown("**Выбор**")
            with col2:
                st.markdown("**Telegram ID**")
            with col3:
                st.markdown("**Пользователь**")
            with col4:
                st.markdown("**Права**")
            
            st.markdown("---")
            
            for i, user in enumerate(filtered_users):
                telegram_id = user['telegram_id']
                permissions_display = ', '.join(user['permissions']) if isinstance(user.get('permissions'), list) else str(user.get('permissions', ''))
                
                col1, col2, col3, col4 = st.columns([0.5, 1.5, 3, 3])

                with col1:
                    is_selected = telegram_id in st.session_state.selected_users
                    if st.checkbox("Выбрать", value=is_selected, key=f"user_select_{telegram_id}", label_visibility="hidden"):
                        st.session_state.selected_users.add(telegram_id)
                    else:
                        st.session_state.selected_users.discard(telegram_id)

                with col2:
                    st.text(f"{telegram_id}")

                with col3:
                    # Красивое отображение пользователя: имя + @username
                    first_name = user.get('first_name', '')
                    last_name = user.get('last_name', '')
                    username = user.get('username', '')

                    display_name = ""
                    if first_name and last_name:
                        display_name = f"{first_name} {last_name}"
                    elif first_name:
                        display_name = first_name
                    elif username:
                        display_name = f"@{username}"
                    else:
                        display_name = f"ID: {telegram_id}"

                    # Показываем имя и username отдельными строками для лучшей читаемости
                    if first_name or last_name:
                        st.text(display_name)
                        if username:
                            st.caption(f"@{username}")
                    else:
                        st.text(display_name)

                with col4:
                    st.text(permissions_display)
            
            # Показываем количество выбранных пользователей
            selected_count = len(st.session_state.selected_users)
            if selected_count > 0:
                st.info(f"✅ Выбрано пользователей: {selected_count}")
            
            # Создаем selected_rows в формате, который ожидают методы управления правами
            selected_rows = [user for user in filtered_users if user['telegram_id'] in st.session_state.selected_users]
            
            # Кнопки действий
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("🔄 Обновить данные"):
                    st.rerun()
            
            with col2:
                if st.button("🚫 Убрать права загрузки"):
                    self._remove_upload_permissions(selected_rows)
            
            with col3:
                if st.button("✅ Дать права загрузки"):
                    self._grant_upload_permissions(selected_rows)
            
            with col4:
                if st.button("📊 Экспорт списка"):
                    self._export_telegram_users_csv(filtered_users)
        
        else:
            st.info("👤 Telegram пользователи не найдены")
        
    
    
    # Метод _render_user_activity_statistics удалён - таб статистики больше не нужен
    
    def _render_access_settings(self):
        """Настройки доступа и разрешений"""
        
        st.write("**Настройка прав доступа**")
        
        # Конфигурация ролей
        st.subheader("👑 Конфигурация ролей")
        
        for role_key, role_name in self.roles.items():
            with st.expander(f"{role_name} ({role_key})"):
                st.write(f"**Настройки для роли: {role_name}**")
                
                # Получаем текущие права для роли
                current_permissions = self._get_role_permissions(role_key)
                
                # Чекбоксы для каждого разрешения
                updated_permissions = []
                for perm_key, perm_name in self.permissions.items():
                    is_enabled = perm_key in current_permissions
                    
                    if st.checkbox(
                        perm_name, 
                        value=is_enabled,
                        key=f"role_{role_key}_{perm_key}"
                    ):
                        updated_permissions.append(perm_key)
                
                # Кнопка сохранения изменений для роли
                if st.button(f"💾 Сохранить изменения для {role_name}", key=f"save_{role_key}"):
                    if self._update_role_permissions(role_key, updated_permissions):
                        st.success(f"✅ Права для роли {role_name} обновлены!")
                    else:
                        st.error("❌ Ошибка при обновлении прав")
        
        # Настройки безопасности
        st.subheader("🔐 Настройки безопасности")
        
        col1, col2 = st.columns(2)
        
        with col1:
            session_timeout = st.slider("⏰ Таймаут сессии (часы)", 1, 24, 8)
            max_failed_logins = st.slider("🚫 Макс. неудачных попыток входа", 3, 10, 5)
            require_2fa = st.checkbox("📱 Требовать 2FA для админов", value=False)
        
        with col2:
            password_min_length = st.slider("🔑 Мин. длина пароля", 6, 20, 8)
            password_require_special = st.checkbox("✨ Требовать спец. символы", value=True)
            auto_block_suspicious = st.checkbox("🛡️ Авто-блокировка подозрительной активности", value=True)
        
        if st.button("💾 Сохранить настройки безопасности", type="primary"):
            security_settings = {
                'session_timeout': session_timeout,
                'max_failed_logins': max_failed_logins,
                'require_2fa': require_2fa,
                'password_min_length': password_min_length,
                'password_require_special': password_require_special,
                'auto_block_suspicious': auto_block_suspicious
            }
            
            if self._save_security_settings(security_settings):
                st.success("✅ Настройки безопасности сохранены!")
            else:
                st.error("❌ Ошибка при сохранении настроек")
    
    def _get_users_data(self) -> List[Dict]:
        """Получение данных всех пользователей"""
        
        try:
            headers = self._get_auth_headers()
            if not headers:
                return []
            
            response = requests.get(f"{self.api_gateway_url}/admin/users/list", headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json().get('users', [])
            
            # Данные недоступны - сервис не отвечает или нет данных
            return []
            
        except Exception as e:
            st.error(f"Ошибка при получении данных пользователей: {str(e)}")
            return []
    
    def _filter_users(self, users: List[Dict], role_filter: str, status_filter: str, search_query: str) -> List[Dict]:
        """Применение фильтров к списку пользователей"""
        
        filtered = users.copy()
        
        # Фильтр по роли
        if role_filter != "Все":
            role_key = next((k for k, v in self.roles.items() if v == role_filter), None)
            if role_key:
                filtered = [u for u in filtered if u['role'] == role_key]
        
        # Фильтр по статусу
        if status_filter != "Все":
            status_map = {"Активные": "active", "Заблокированные": "blocked"}
            status_key = status_map.get(status_filter)
            if status_key:
                filtered = [u for u in filtered if u['status'] == status_key]
        
        # Поиск по имени/ID
        if search_query:
            query = search_query.lower()
            filtered = [
                u for u in filtered 
                if query in u['username'].lower() or query in str(u['user_id'])
            ]
        
        return filtered
    
    # Все статистические функции удалены - таб статистики больше не нужен
    # _get_user_statistics, _get_default_stats_with_error, _generate_sample_* methods removed
    
    def _validate_user_form(self, username: str, password: str, confirm_password: str, telegram_id: int) -> bool:
        """Валидация формы создания пользователя"""
        
        if not username or len(username) < 3:
            st.error("❌ Имя пользователя должно содержать не менее 3 символов")
            return False
        
        if not password or len(password) < 6:
            st.error("❌ Пароль должен содержать не менее 6 символов")
            return False
        
        if password != confirm_password:
            st.error("❌ Пароли не совпадают")
            return False
        
        if telegram_id <= 0:
            st.error("❌ Укажите корректный Telegram ID")
            return False
        
        return True
    
    def _create_user(self, user_data: Dict) -> bool:
        """Создание нового пользователя"""
        
        try:
            headers = self._get_auth_headers()
            if not headers:
                return False
            
            response = requests.post(
                f"{self.api_gateway_url}/admin/users/add",
                json=user_data,
                headers=headers,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            st.error(f"Ошибка при создании пользователя: {str(e)}")
            return False
    
    def _get_role_permissions(self, role: str) -> List[str]:
        """Получение текущих прав для роли"""
        
        # Заглушка - в реальной реализации берется из API
        role_permissions_map = {
            'super_admin': list(self.permissions.keys()),
            'admin': ['dashboard', 'files', 'users', 'logs', 'settings'],
            'moderator': ['dashboard', 'files', 'logs'],
            'user': ['dashboard']
        }
        
        return role_permissions_map.get(role, [])
    
    def _update_role_permissions(self, role: str, permissions: List[str]) -> bool:
        """Обновление прав для роли"""
        
        try:
            # В реальной реализации отправляем запрос к API
            return True
            
        except Exception:
            return False
    
    def _save_security_settings(self, settings: Dict) -> bool:
        """Сохранение настроек безопасности"""
        
        try:
            # В реальной реализации отправляем запрос к API
            return True
            
        except Exception:
            return False
    
    def _block_selected_users(self, selected_rows):
        """Блокировка выбранных пользователей"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return False
                
            blocked_count = 0
            for row in selected_rows:
                user_id = row.get('id')
                response = requests.put(
                    f"{self.api_gateway_url}/admin/telegram-users/{user_id}/block",
                    headers=headers,
                    timeout=10
                )
                if response.status_code == 200:
                    blocked_count += 1
                    
            st.success(f"✅ Заблокировано пользователей: {blocked_count}")
            return True
        except Exception as e:
            st.error(f"❌ Ошибка блокировки: {str(e)}")
            return False
        
    def _unblock_selected_users(self, selected_rows):
        """Разблокировка выбранных пользователей"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return False
                
            unblocked_count = 0
            for row in selected_rows:
                user_id = row.get('id')
                response = requests.put(
                    f"{self.api_gateway_url}/admin/telegram-users/{user_id}/unblock",
                    headers=headers,
                    timeout=10
                )
                if response.status_code == 200:
                    unblocked_count += 1
                    
            st.success(f"✅ Разблокировано пользователей: {unblocked_count}")
            return True
        except Exception as e:
            st.error(f"❌ Ошибка разблокировки: {str(e)}")
            return False
    
    def _update_user_permissions(self, user_id: int, grant_upload: bool) -> bool:
        """Выдача/отзыв права upload_documents для пользователя"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return False

            payload = {
                "permission_type": "upload_documents",
                "is_granted": bool(grant_upload)
            }
            response = requests.put(
                f"{self.api_gateway_url}/admin/telegram-users/{user_id}/permissions",
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                return True
            elif response.status_code == 404:
                st.error("❌ Пользователь не найден")
                return False
            elif response.status_code == 401:
                st.error("❌ Ошибка авторизации - обновите страницу")
                return False
            else:
                try:
                    error_data = response.json()
                    detail = error_data.get('detail', 'Неизвестная ошибка')
                except Exception:
                    detail = 'Неизвестная ошибка'
                st.error(f"❌ Ошибка обновления прав: {detail}")
                return False
        except Exception as e:
            st.error(f"❌ Ошибка при обновлении прав: {str(e)}")
            return False
    
    def _delete_telegram_user(self, user_id: int) -> bool:
        """Удаление Telegram пользователя"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return False
                
            response = requests.delete(
                f"{self.api_gateway_url}/admin/telegram-users/{user_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                st.success(f"✅ Пользователь удален: {data.get('message', 'Успешно')}")
                return True
            elif response.status_code == 404:
                st.error("❌ Пользователь не найден")
                return False
            elif response.status_code == 401:
                st.error("❌ Ошибка авторизации - обновите страницу")
                return False
            else:
                error_data = response.json()
                st.error(f"❌ Ошибка удаления: {error_data.get('detail', 'Неизвестная ошибка')}")
                return False
                
        except Exception as e:
            st.error(f"❌ Ошибка при удалении пользователя: {str(e)}")
            return False
    
    def _remove_upload_permissions(self, selected_rows):
        """Отбираем права загрузки у выбранных пользователей"""
        if not selected_rows:
            st.warning("⚠️ Не выбрано ни одного пользователя")
            return
            
        try:
            updated_count = 0
            for user in selected_rows:
                user_id = user.get('id') or user.get('telegram_id')  # Поддерживаем разные форматы ID
                # Отзываем право загрузки документов
                if self._update_user_permissions(user_id, False):
                    updated_count += 1
                    
            if updated_count > 0:
                st.success(f"✅ Права загрузки отобраны у {updated_count} пользователей")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Ошибка при изменении прав: {str(e)}")
    
    def _grant_upload_permissions(self, selected_rows):
        """Выдаем права загрузки выбранным пользователям"""
        if not selected_rows:
            st.warning("⚠️ Не выбрано ни одного пользователя")
            return
            
        try:
            updated_count = 0
            for user in selected_rows:
                user_id = user.get('id') or user.get('telegram_id')  # Поддерживаем разные форматы ID
                # Выдаем право на загрузку документов
                if self._update_user_permissions(user_id, True):
                    updated_count += 1
                    
            if updated_count > 0:
                st.success(f"✅ Права загрузки выданы {updated_count} пользователям")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Ошибка при изменении прав: {str(e)}")
    
    def _export_telegram_users_csv(self, df):
        """Экспорт Telegram пользователей в CSV"""
        st.info("📊 Экспорт данных Telegram пользователей в CSV...")
    
    # ====== НОВЫЕ МЕТОДЫ ДЛЯ TELEGRAM ПОЛЬЗОВАТЕЛЕЙ ======
    
    def _get_current_telegram_admin_ids(self) -> List[int]:
        """Получение пользователей с правами загрузки из базы данных"""
        try:
            # Получаем пользователей с правами загрузки из базы данных
            users_data = self._get_telegram_users_data()
            admin_ids = []

            for user in users_data:
                # Проверяем есть ли права загрузки
                permissions = user.get('permissions', [])
                if any(perm.get('permission_type') == 'upload_documents' and
                      perm.get('is_granted', False) for perm in permissions):
                    admin_ids.append(user.get('telegram_id'))

            return admin_ids
        except Exception as e:
            print(f"Ошибка получения администраторов: {e}")
            return []
    
    def _get_telegram_users_data(self) -> List[Dict]:
        """Получение данных Telegram пользователей из API"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return []
                
            response = requests.get(f"{self.api_gateway_url}/admin/telegram-users/list", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('telegram_users', [])
            elif response.status_code == 401:
                st.error("❌ Ошибка авторизации - обновите страницу")
                return []
            else:
                st.error(f"❌ Ошибка API: {response.status_code}")
                return []
            
        except requests.exceptions.ConnectionError:
            st.error("❌ Нет соединения с API Gateway")
            return []
        except Exception as e:
            st.error(f"❌ Ошибка при получении Telegram пользователей: {str(e)}")
            return []
    
    def _filter_telegram_users(self, users: List[Dict], permission_filter: str, status_filter: str, search_query: str) -> List[Dict]:
        """Применение фильтров к списку Telegram пользователей"""

        filtered = users.copy()

        # Фильтр по правам
        if permission_filter != "Все":
            if permission_filter == "Может загружать":
                # Пользователи с правами upload_documents
                filtered = [u for u in filtered if 'upload_documents' in (u.get('permissions', []) or [])]
            elif permission_filter == "Только просмотр":
                # Пользователи без прав загрузки (либо без прав вообще, либо с отозванными правами)
                filtered = [u for u in filtered if 'upload_documents' not in (u.get('permissions', []) or [])]

        # Убираем фильтр по статусу

        # Улучшенный поиск по имени, фамилии и @username
        if search_query:
            query = search_query.lower().strip()
            # Убираем @ если пользователь ввел его
            if query.startswith('@'):
                query = query[1:]

            filtered = [
                u for u in filtered
                if query in str(u.get('telegram_id', '')) or
                   query in u.get('username', '').lower() or
                   query in u.get('first_name', '').lower() or
                   query in u.get('last_name', '').lower() or
                   query in f"{u.get('first_name', '')} {u.get('last_name', '')}".lower().strip()
            ]

        return filtered
    
    
    def _remove_upload_permissions(self, selected_rows):
        """Убрать права загрузки у выбранных пользователей"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return
            
            # Получаем выбранные строки (теперь это список пользователей)
            if selected_rows and len(selected_rows) > 0:
                success_count = 0
                for user in selected_rows:
                    telegram_id = user.get('telegram_id')
                    if telegram_id:
                        # ИСПРАВЛЕНО: Используем PUT для отзыва прав вместо DELETE для удаления пользователя
                        permission_data = {
                            "permissions": []  # Пустой список = отзыв всех прав
                        }
                        response = requests.put(
                            f"{self.api_gateway_url}/admin/telegram-users/{telegram_id}/permissions",
                            json=permission_data,
                            headers=headers,
                            timeout=10
                        )
                        if response.status_code == 200:
                            success_count += 1
                
                if success_count > 0:
                    st.success(f"✅ Права загрузки убраны у {success_count} пользователей")
                    # Обновляем данные и очищаем выбор
                    if 'selected_users' in st.session_state:
                        st.session_state.selected_users = set()
                    st.rerun()
                else:
                    st.warning("⚠️ Не удалось убрать права ни у одного пользователя")
            else:
                st.warning("⚠️ Выберите пользователей для изменения прав")
                
        except Exception as e:
            st.error(f"❌ Ошибка при удалении прав: {str(e)}")
        
    def _grant_upload_permissions(self, selected_rows):
        """Дать права загрузки выбранным пользователям"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return
            
            # Получаем выбранные строки (теперь это список пользователей)
            if selected_rows and len(selected_rows) > 0:
                success_count = 0
                for user in selected_rows:
                    telegram_id = user.get('telegram_id')
                    if telegram_id:
                        permission_data = {
                            'permission_type': 'upload_documents',
                            'is_granted': True
                        }
                        response = requests.put(
                            f"{self.api_gateway_url}/admin/telegram-users/{telegram_id}/permissions",
                            json=permission_data,
                            headers=headers,
                            timeout=10
                        )
                        if response.status_code == 200:
                            success_count += 1
                
                if success_count > 0:
                    st.success(f"✅ Права загрузки выданы {success_count} пользователям")
                    # Обновляем данные и очищаем выбор
                    if 'selected_users' in st.session_state:
                        st.session_state.selected_users = set()
                    st.rerun()
                else:
                    st.warning("⚠️ Не удалось выдать права ни одному пользователю")
            else:
                st.warning("⚠️ Выберите пользователей для изменения прав")
                
        except Exception as e:
            st.error(f"❌ Ошибка при выдаче прав: {str(e)}")
    
    def get_telegram_users(self) -> List[Dict]:
        """Получение списка Telegram пользователей - метод для совместимости"""
        return self._get_telegram_users_data()
    
    def _render_permission_requests_list(self):
        """Отображение списка запросов на получение прав доступа"""
        
        # Инициализация session_state
        if 'selected_requests' not in st.session_state:
            st.session_state.selected_requests = set()
        
        st.write("**Запросы пользователей на получение прав доступа**")
        
        # Информация о системе
        st.info("🔑 Здесь администраторы могут рассматривать запросы пользователей на получение прав доступа к загрузке документов")
        
        # Фильтры
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox(
                "Статус запроса",
                ["Все", "Ожидают рассмотрения", "Одобрены", "Отклонены"],
                index=1,  # По умолчанию показываем только ожидающие рассмотрения
                key="permission_request_status_filter"
            )
        
        with col2:
            # Убираем фильтр по типу разрешения
            st.empty()  # Пустая колонка для сохранения макета
            permission_type_filter = "Все"  # Значение по умолчанию
        
        with col3:
            search_query = st.text_input("🔍 Поиск по пользователю", key="permission_request_search")
        
        # Получение данных запросов
        permission_requests_data = self._get_permission_requests_data()
        
        if not permission_requests_data:
            st.info("📝 Загружаем данные запросов на права...")
            return
        
        # Применение фильтров (без фильтра типа разрешения)
        filtered_requests = self._filter_permission_requests(
            permission_requests_data,
            status_filter,
            None,  # Не используем фильтр типа разрешения
            search_query
        )
        
        # Статистика по запросам
        if filtered_requests:
            col1, col2, col3 = st.columns(3)
            with col1:
                pending_count = len([r for r in filtered_requests if r['status'] == 'pending'])
                st.metric("⏳ Ожидают", pending_count)
            with col2:
                approved_count = len([r for r in filtered_requests if r['status'] == 'approved'])
                st.metric("✅ Одобрено", approved_count)
            with col3:
                rejected_count = len([r for r in filtered_requests if r['status'] == 'rejected'])
                st.metric("❌ Отклонено", rejected_count)
        
        # Таблица запросов
        if filtered_requests:
            st.markdown("### 📋 Список запросов")
            
            # Инициализация session state для выбранных запросов
            if 'selected_requests' not in st.session_state:
                st.session_state.selected_requests = set()
            
            # Кнопка "Выбрать все / Снять выбор"
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("🔄 Выбрать все" if len(st.session_state.selected_requests) == 0 else "❌ Снять выбор"):
                    if len(st.session_state.selected_requests) == 0:
                        st.session_state.selected_requests = {r['id'] for r in filtered_requests}
                    else:
                        st.session_state.selected_requests = set()
                    st.rerun()
            
            # Отображение запросов
            for request in filtered_requests:
                request_id = request['id']
                is_selected = request_id in st.session_state.selected_requests
                
                with st.expander(f"📋 Запрос #{request_id} - {request['display_name']}", expanded=False):
                    col1, col2, col3 = st.columns([0.5, 1, 4])
                    
                    with col1:
                        # Чекбокс для выбора
                        if st.checkbox("Выбрать", value=is_selected, key=f"request_select_{request_id}", label_visibility="hidden"):
                            st.session_state.selected_requests.add(request_id)
                        else:
                            st.session_state.selected_requests.discard(request_id)
                    
                    with col2:
                        # Статус с цветовой индикацией
                        status_color = {
                            'pending': '🟡',
                            'approved': '✅',
                            'rejected': '❌',
                            'expired': '⏰'
                        }.get(request['status'], '❓')
                        st.markdown(f"{status_color} **{request['status'].upper()}**")
                    
                    with col3:
                        # Детали запроса
                        st.markdown(f"**👤 Пользователь:** {request['display_name']}")
                        st.markdown(f"**🆔 Telegram ID:** {request['telegram_id']}")
                        st.markdown(f"**📅 Запрос:** {request['requested_at']}")
                        st.markdown(f"**🔐 Тип разрешения:** {request['request_type']}")
                        
                        if request.get('username'):
                            st.markdown(f"**🏷️ Username:** @{request['username']}")
                        
                        if request.get('request_message'):
                            st.markdown(f"**📝 Сообщение:** {request['request_message']}")
                        
                        if request.get('admin_comment'):
                            st.markdown(f"**💬 Комментарий админа:** {request['admin_comment']}")
                        
                        if request.get('processed_at'):
                            st.markdown(f"**🕒 Обработан:** {request['processed_at']}")
                            st.markdown(f"**👤 Обработал:** {request['processed_by']}")
                        
                        # Кнопки действий для ожидающих запросов
                        if request['status'] == 'pending':
                            col_a, col_b, col_c = st.columns(3)
                            
                            with col_a:
                                if st.button("✅ Одобрить", key=f"approve_{request_id}", type="primary"):
                                    self._process_request_action(request_id, 'approve')
                            
                            with col_b:
                                # Улучшенная логика отклонения с опциональным комментарием
                                reject_key = f"reject_{request_id}"
                                if reject_key not in st.session_state:
                                    st.session_state[reject_key] = False
                                
                                if not st.session_state.get(reject_key, False):
                                    if st.button("❌ Отклонить", key=f"reject_btn_{request_id}", type="secondary"):
                                        st.session_state[reject_key] = True
                                        st.rerun()
                                else:
                                    # Показываем поле для комментария и кнопки подтверждения
                                    admin_comment = st.text_input(
                                        "💬 Причина отклонения (опционально):", 
                                        key=f"comment_{request_id}",
                                        placeholder="Укажите причину отклонения или оставьте пустым"
                                    )
                                    
                                    # Кнопки без вложенных колонок
                                    if st.button("✅ Подтвердить", key=f"confirm_reject_{request_id}", type="primary"):
                                        self._process_request_action(request_id, 'reject', admin_comment or "Отклонено администратором")
                                        st.session_state[reject_key] = False
                                        st.rerun()
                                    if st.button("↩️ Отмена", key=f"cancel_reject_{request_id}"):
                                        st.session_state[reject_key] = False
                                        st.rerun()
                            
                            with col_c:
                                # Улучшенная логика удаления
                                delete_key = f"delete_{request_id}"
                                if delete_key not in st.session_state:
                                    st.session_state[delete_key] = False
                                
                                if not st.session_state.get(delete_key, False):
                                    if st.button("🗑️ Удалить", key=f"delete_btn_{request_id}"):
                                        st.session_state[delete_key] = True
                                        st.rerun()
                                else:
                                    # Показываем подтверждение удаления
                                    st.warning("⚠️ Удаление запроса необратимо!")
                                    # Кнопки без вложенных колонок
                                    if st.button("✅ Удалить", key=f"confirm_delete_{request_id}", type="primary"):
                                        self._delete_request(request_id)
                                        st.session_state[delete_key] = False
                                        st.rerun()
                                    if st.button("↩️ Отмена", key=f"cancel_delete_{request_id}"):
                                        st.session_state[delete_key] = False
                                        st.rerun()
                        else:
                            st.info(f"Запрос уже обработан ({request['status']})")
        
        else:
            st.info("📝 Запросы на права не найдены")
        
        # Массовые действия
        if 'selected_requests' not in st.session_state:
            st.session_state.selected_requests = set()
        selected_requests_count = len(st.session_state.selected_requests)
        if selected_requests_count > 0:
            st.markdown("---")
            st.info(f"📌 Выбрано запросов: {selected_requests_count}")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("✅ Массовое одобрение", type="primary"):
                    self._batch_process_requests('approve')
            
            with col2:
                if st.button("❌ Массовое отклонение", type="secondary"):
                    self._batch_process_requests('reject')
            
            with col3:
                if st.button("🗑️ Массовое удаление"):
                    self._batch_delete_requests()
    
    def _get_permission_requests_data(self) -> List[Dict]:
        """Получение данных запросов на права доступа через API"""
        try:
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return []
            
            # Запрос к API Gateway для получения списка запросов
            response = requests.get(
                f"{self.api_gateway_url}/admin/permission-requests/list",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('permission_requests', [])
            else:
                st.error(f"❌ Ошибка при получении данных запросов: {response.status_code}")
                return []
            
        except Exception as e:
            st.error(f"❌ Ошибка при получении данных запросов: {str(e)}")
            return []
    
    def _filter_permission_requests(self, requests: List[Dict], status_filter: str, permission_type_filter: str, search_query: str) -> List[Dict]:
        """Применение фильтров к списку запросов"""
        
        filtered = requests.copy()
        
        # Фильтр по статусу
        if status_filter != "Все":
            status_map = {
                "Ожидают рассмотрения": "pending",
                "Одобрены": "approved",
                "Отклонены": "rejected"
            }
            status_key = status_map.get(status_filter)
            if status_key:
                filtered = [r for r in filtered if r['status'] == status_key]
        
        # Убираем фильтр по типу разрешения (больше не нужен)
        
        # Поиск по пользователю
        if search_query:
            query = search_query.lower()
            filtered = [
                r for r in filtered
                if query in str(r.get('telegram_id', '')) or
                   query in r.get('username', '').lower() or
                   query in r.get('display_name', '').lower()
            ]
        
        return filtered
    
    def _process_request_action(self, request_id: int, action: str, admin_comment: str = None):
        """Обработка запроса (одобрение/отклонение) через API"""
        
        try:
            # Для отклонения используем переданный комментарий или значение по умолчанию
            if action == 'reject' and not admin_comment:
                admin_comment = "Отклонено администратором"
            
            # Отправка запроса к API Gateway
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return
            
            process_data = {
                'action': action,
                'admin_comment': admin_comment
            }
            
            response = requests.post(
                f"{self.api_gateway_url}/admin/permission-requests/{request_id}/process",
                json=process_data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    if action == 'approve':
                        st.success(f"✅ Запрос #{request_id} одобрен!")
                        # Здесь можно отправить уведомление пользователю в Telegram
                    else:
                        st.success(f"✅ Запрос #{request_id} отклонен!")
                    
                    # Очищаем выбор и обновляем интерфейс
                    if 'selected_requests' in st.session_state:
                        st.session_state.selected_requests.discard(request_id)
                    st.rerun()
                else:
                    st.error(f"❌ {result.get('message', 'Ошибка при обработке запроса')}")
            else:
                st.error(f"❌ Ошибка API: {response.status_code}")
                
        except Exception as e:
            st.error(f"❌ Ошибка при обработке запроса: {str(e)}")
    
    def _delete_request(self, request_id: int):
        """Удаление запроса через API"""
        
        try:
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return
            
            response = requests.delete(
                f"{self.api_gateway_url}/admin/permission-requests/{request_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    st.success(f"✅ Запрос #{request_id} удален!")
                    # Очищаем выбор и обновляем интерфейс
                    if 'selected_requests' in st.session_state:
                        st.session_state.selected_requests.discard(request_id)
                    st.rerun()
                else:
                    st.error(f"❌ {result.get('message', 'Ошибка при удалении запроса')}")
            else:
                st.error(f"❌ Ошибка API: {response.status_code}")
                
        except Exception as e:
            st.error(f"❌ Ошибка при удалении запроса: {str(e)}")
    
    def _batch_process_requests(self, action: str):
        """Массовая обработка запросов через API"""
        
        try:
            selected_requests = list(st.session_state.selected_requests)
            
            if not selected_requests:
                st.warning("⚠️ Выберите запросы для обработки")
                return
            
            # Инициализируем комментарий
            admin_comment = None
            
            # Получаем комментарий для отклонения
            if action == 'reject':
                admin_comment = st.text_area("💬 Причина отклонения для всех выбранных запросов:")
                if not admin_comment:
                    st.error("❌ Укажите причину отклонения")
                    return
            
            # Отправка запроса к API Gateway
            headers = self._get_auth_headers()
            if not headers:
                st.error("❌ Ошибка авторизации")
                return
            
            batch_data = {
                'request_ids': selected_requests,
                'action': action,
                'admin_comment': admin_comment
            }
            
            response = requests.post(
                f"{self.api_gateway_url}/admin/permission-requests/batch-process",
                json=batch_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    success_count = result.get('processed_count', len(selected_requests))
                    st.success(f"✅ {success_count} запросов успешно обработано!")
                    # Очищаем выбор и обновляем интерфейс
                    st.session_state.selected_requests = set()
                    st.rerun()
                else:
                    st.error(f"❌ {result.get('message', 'Ошибка при массовой обработке запросов')}")
            else:
                st.error(f"❌ Ошибка API: {response.status_code}")
                
        except Exception as e:
            st.error(f"❌ Ошибка при массовой обработке запросов: {str(e)}")
    
    def _batch_delete_requests(self):
        """Массовое удаление запросов через API"""
        
        try:
            selected_requests = list(st.session_state.selected_requests)
            
            if not selected_requests:
                st.warning("⚠️ Выберите запросы для удаления")
                return
            
            # Подтверждение удаления
            if st.button("✅ Подтвердить массовое удаление", key="confirm_batch_delete"):
                headers = self._get_auth_headers()
                if not headers:
                    st.error("❌ Ошибка авторизации")
                    return
                
                batch_data = {
                    'request_ids': selected_requests
                }
                
                response = requests.delete(
                    f"{self.api_gateway_url}/admin/permission-requests/batch-delete",
                    json=batch_data,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        success_count = result.get('deleted_count', len(selected_requests))
                        st.success(f"✅ {success_count} запросов успешно удалено!")
                        # Очищаем выбор и обновляем интерфейс
                        st.session_state.selected_requests = set()
                        st.rerun()
                    else:
                        st.error(f"❌ {result.get('message', 'Ошибка при массовом удалении запросов')}")
                else:
                    st.error(f"❌ Ошибка API: {response.status_code}")
                    
        except Exception as e:
            st.error(f"❌ Ошибка при массовом удалении запросов: {str(e)}")