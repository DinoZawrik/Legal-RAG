#!/usr/bin/env python3
"""
🔐 Authentication Manager для Admin Panel
JWT аутентификация и управление сессиями
"""

import os
import jwt
import hashlib
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class AuthenticationManager:
    """Простой менеджер аутентификации для единственного админа"""
    
    def __init__(self):
        self.secret_key = os.getenv('ADMIN_JWT_SECRET', 'change-jwt-secret-in-production')
        self.algorithm = 'HS256'
        self.token_expiry = timedelta(hours=8)  # Токен действует 8 часов

        # Единственный администратор
        self.admin_password = os.getenv('ADMIN_PANEL_PASSWORD', 'change_me_in_env')
    
    
    def _hash_password(self, password: str) -> str:
        """Хеширование пароля с солью"""
        salt = os.getenv("ADMIN_PASSWORD_SALT", "change-salt-in-production")
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def authenticate(self, username: str, password: str) -> bool:
        """
        Простая аутентификация единственного администратора
        
        Args:
            username: Имя пользователя (игнорируется, но оставлено для совместимости)
            password: Пароль администратора
            
        Returns:
            bool: True если пароль правильный
        """
        
        if not password:
            return False
        
        # Простая проверка пароля (без хеширования для упрощения)
        if password == self.admin_password:
            # Создаем простой JWT токен
            token = self._create_jwt_token('admin')
            
            # Сохраняем в session state
            st.session_state.auth_token = token
            st.session_state.username = 'admin'
            
            return True
        
        return False
    
    def _create_jwt_token(self, username: str) -> str:
        """
        Создание простого JWT токена
        
        Args:
            username: Имя пользователя
            
        Returns:
            str: JWT токен
        """
        
        payload = {
            'username': username,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + self.token_expiry
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Проверка JWT токена
        
        Args:
            token: JWT токен
            
        Returns:
            Dict | None: Данные пользователя или None если токен недействителен
        """
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def check_permission(self, required_permission: str) -> bool:
        """
        У единственного админа есть все права
        
        Args:
            required_permission: Требуемое право доступа (игнорируется)
            
        Returns:
            bool: True если пользователь аутентифицирован
        """
        
        return self.is_authenticated()
    
    def get_current_user_info(self) -> Dict[str, Any]:
        """Получение информации о текущем администраторе"""
        
        if not hasattr(st.session_state, 'auth_token'):
            return {}
        
        token_data = self.verify_token(st.session_state.auth_token)
        if not token_data:
            return {}
        
        return {
            'username': token_data['username'],
            'role': 'admin',
            'token_expires': datetime.fromtimestamp(token_data['exp']).strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def logout(self):
        """Выход из системы"""
        
        # Очищаем все данные сессии
        keys_to_remove = [
            'authenticated', 'username', 'auth_token', 'current_page'
        ]
        
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
    
    def is_authenticated(self) -> bool:
        """Проверка аутентификации пользователя"""
        
        if not hasattr(st.session_state, 'auth_token'):
            return False
        
        token_data = self.verify_token(st.session_state.auth_token)
        return token_data is not None
    


# Utility функции для использования в Streamlit
def require_auth():
    """Проверка аутентификации для страниц"""
    
    auth = AuthenticationManager()
    
    if not auth.is_authenticated():
        st.error("🔐 Требуется аутентификация")
        st.stop()


