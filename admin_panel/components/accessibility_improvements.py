#!/usr/bin/env python3
"""
Улучшения accessibility для админ панели LegalRAG
"""

import streamlit as st

def add_accessibility_css():
    """Добавляет CSS для улучшения accessibility и детектирования элементов"""
    
    st.markdown("""
<style>
    /* Accessibility improvements */
    
    /* Навигационные элементы с data-testid для лучшего детектирования */
    .nav-item {
        position: relative;
        cursor: pointer;
        padding: 8px 16px;
        border-radius: 5px;
        transition: background-color 0.3s;
    }
    
    .nav-item:hover {
        background-color: rgba(46, 139, 192, 0.1);
    }
    
    .nav-item.active {
        background-color: rgba(46, 139, 192, 0.2);
        border-left: 4px solid #2e8bc0;
    }
    
    /* Улучшенные кнопки с лучшими селекторами */
    .enhanced-button {
        background: linear-gradient(90deg, #1f4e79, #2e8bc0) !important;
        color: white !important;
        border: none !important;
        border-radius: 5px !important;
        padding: 0.5rem 1rem !important;
        font-weight: bold !important;
        cursor: pointer !important;
        transition: all 0.3s ease !important;
        min-height: 38px !important;
    }
    
    .enhanced-button:hover {
        background: linear-gradient(90deg, #2e8bc0, #1f4e79) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
    }
    
    .enhanced-button:focus {
        outline: 2px solid #ffd700 !important;
        outline-offset: 2px !important;
    }
    
    /* Улучшенные индикаторы состояния */
    .status-indicator {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85em;
        margin-right: 8px;
    }
    
    .status-healthy {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    
    .status-warning {
        background-color: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
    }
    
    .status-error {
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f1b0b7;
    }
    
    /* Улучшенные поля ввода */
    .enhanced-input input {
        border: 2px solid #dee2e6 !important;
        border-radius: 5px !important;
        padding: 8px 12px !important;
        font-size: 14px !important;
        transition: border-color 0.3s ease !important;
    }
    
    .enhanced-input input:focus {
        border-color: #2e8bc0 !important;
        box-shadow: 0 0 0 3px rgba(46, 139, 192, 0.1) !important;
        outline: none !important;
    }
    
    /* Улучшенные таблицы */
    .enhanced-table {
        border-collapse: collapse;
        width: 100%;
        margin-top: 1rem;
    }
    
    .enhanced-table th {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 12px;
        text-align: left;
        font-weight: bold;
        color: #495057;
    }
    
    .enhanced-table td {
        border: 1px solid #dee2e6;
        padding: 12px;
        color: #495057;
    }
    
    .enhanced-table tr:nth-child(even) {
        background-color: #f8f9fa;
    }
    
    .enhanced-table tr:hover {
        background-color: #e9ecef;
    }
    
    /* Карточки с улучшенным дизайном */
    .info-card {
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: box-shadow 0.3s ease;
    }
    
    .info-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    .info-card h3 {
        margin-top: 0;
        color: #1f4e79;
        border-bottom: 2px solid #2e8bc0;
        padding-bottom: 0.5rem;
    }
    
    /* Прогресс бары */
    .progress-bar {
        width: 100%;
        height: 20px;
        background-color: #e9ecef;
        border-radius: 10px;
        overflow: hidden;
        margin: 8px 0;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #28a745, #20c997);
        transition: width 0.3s ease;
    }
    
    /* Алерты */
    .alert {
        padding: 12px 16px;
        border-radius: 6px;
        margin: 10px 0;
        border-left: 4px solid;
    }
    
    .alert-success {
        background-color: #d4edda;
        color: #155724;
        border-left-color: #28a745;
    }
    
    .alert-warning {
        background-color: #fff3cd;
        color: #856404;
        border-left-color: #ffc107;
    }
    
    .alert-error {
        background-color: #f8d7da;
        color: #721c24;
        border-left-color: #dc3545;
    }
    
    .alert-info {
        background-color: #d1ecf1;
        color: #0c5460;
        border-left-color: #17a2b8;
    }
    
    /* Улучшенная навигация в сайдбаре */
    .sidebar-nav {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    
    .sidebar-nav li {
        margin: 4px 0;
    }
    
    .sidebar-nav a {
        display: block;
        padding: 10px 15px;
        text-decoration: none;
        color: #495057;
        border-radius: 5px;
        transition: all 0.3s ease;
    }
    
    .sidebar-nav a:hover {
        background-color: rgba(46, 139, 192, 0.1);
        color: #1f4e79;
    }
    
    .sidebar-nav a.active {
        background-color: #2e8bc0;
        color: white;
    }
    
    /* Мобильная адаптивность */
    @media (max-width: 768px) {
        .info-card {
            margin: 0.25rem 0;
            padding: 0.75rem;
        }
        
        .enhanced-button {
            width: 100%;
            margin: 4px 0;
        }
        
        .enhanced-table {
            font-size: 12px;
        }
        
        .enhanced-table th,
        .enhanced-table td {
            padding: 8px;
        }
    }
    
    /* Кастомные data-testid атрибуты для тестирования */
    [data-testid="nav-file-management"] {
        background-color: rgba(46, 139, 192, 0.05);
    }
    
    [data-testid="nav-user-management"] {
        background-color: rgba(46, 139, 192, 0.05);
    }
    
    [data-testid="nav-dashboard"] {
        background-color: rgba(46, 139, 192, 0.05);
    }
    
    /* Focus indicators для accessibility */
    *:focus {
        outline: 2px solid #ffd700 !important;
        outline-offset: 2px !important;
    }
    
    /* Компактный список пользователей - уменьшенное расстояние между строками */
    .stDataFrame tbody tr {
        line-height: 1.2 !important;
    }
    
    .stDataFrame tbody td {
        padding: 4px 8px !important;
        border-bottom: 1px solid #e0e0e0 !important;
    }
    
    .stDataFrame thead th {
        padding: 6px 8px !important;
        background-color: #f5f5f5 !important;
    }
    
    /* Уменьшаем общие отступы в пользовательских карточках */
    .user-card {
        margin: 0.25rem 0 !important;
        padding: 0.5rem !important;
    }
    
    /* Компактные строки в списках */
    .element-container {
        margin: 0.25rem 0 !important;
    }
    
</style>
""", unsafe_allow_html=True)

def create_enhanced_navigation():
    """Создает улучшенную навигацию с лучшими селекторами"""
    
    st.markdown("""
    <div class="sidebar-nav">
        <ul>
            <li>
                <a href="#dashboard" class="nav-item" data-testid="nav-dashboard" id="nav-dashboard">
                    Панель управления
                </a>
            </li>
            <li>
                <a href="#files" class="nav-item" data-testid="nav-file-management" id="nav-file-management">
                    Управление файлами
                </a>
            </li>
            <li>
                <a href="#users" class="nav-item" data-testid="nav-user-management" id="nav-user-management">
                    Пользователи
                </a>
            </li>
            <li>
                <a href="#system" class="nav-item" data-testid="nav-system-info" id="nav-system-info">
                    Системная информация
                </a>
            </li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

def create_enhanced_button(label, key=None, type="primary", disabled=False, help_text=None):
    """Создает улучшенную кнопку с лучшими атрибутами для тестирования"""
    
    css_class = "enhanced-button"
    if type == "secondary":
        css_class += " secondary"
    elif type == "danger":
        css_class += " danger"
    
    test_id = f"btn-{key}" if key else f"btn-{label.lower().replace(' ', '-')}"
    
    button_html = f"""
    <button class="{css_class}" 
            data-testid="{test_id}"
            id="{test_id}"
            {'disabled' if disabled else ''}
            title="{help_text or label}">
        {label}
    </button>
    """
    
    st.markdown(button_html, unsafe_allow_html=True)
    
    # Возвращаем информацию о кнопке для обработки кликов
    return {
        'testid': test_id,
        'id': test_id,
        'label': label
    }

def create_status_indicator(status, text):
    """Создает индикатор статуса с улучшенным дизайном"""
    
    status_class = f"status-indicator status-{status}"
    
    st.markdown(f"""
    <span class="{status_class}" 
          data-testid="status-{status}" 
          id="status-{status.replace('_', '-')}">
        {text}
    </span>
    """, unsafe_allow_html=True)

def create_info_card(title, content, status="info"):
    """Создает информационную карточку"""
    
    alert_class = f"info-card alert alert-{status}"
    card_id = f"card-{title.lower().replace(' ', '-')}"
    
    st.markdown(f"""
    <div class="{alert_class}" 
         data-testid="{card_id}"
         id="{card_id}">
        <h3>{title}</h3>
        <div>{content}</div>
    </div>
    """, unsafe_allow_html=True)

def create_enhanced_input(label, key=None, placeholder="", help_text=""):
    """Создает улучшенное поле ввода"""
    
    input_id = f"input-{key}" if key else f"input-{label.lower().replace(' ', '-')}"
    
    st.markdown(f"""
    <div class="enhanced-input">
        <label for="{input_id}" data-testid="label-{input_id}">{label}</label>
    </div>
    """, unsafe_allow_html=True)
    
    # Используем стандартный Streamlit input, но с кастомным CSS
    return st.text_input(
        label="",
        key=key,
        placeholder=placeholder,
        help=help_text,
        label_visibility="collapsed"
    )


def create_progress_bar(progress, label=""):
    """Создает прогресс бар"""
    
    progress_id = f"progress-{label.lower().replace(' ', '-')}" if label else "progress-bar"
    
    st.markdown(f"""
    <div class="progress-bar" data-testid="{progress_id}" id="{progress_id}">
        <div class="progress-fill" style="width: {progress}%"></div>
    </div>
    {f'<small>{label}: {progress}%</small>' if label else ''}
    """, unsafe_allow_html=True)

def add_aria_labels():
    """Добавляет ARIA labels для лучшей accessibility"""
    
    st.markdown("""
    <script>
    // Добавляем ARIA labels динамически
    document.addEventListener('DOMContentLoaded', function() {
        // Навигационные элементы
        const navItems = document.querySelectorAll('[data-testid^="nav-"]');
        navItems.forEach(item => {
            item.setAttribute('role', 'button');
            item.setAttribute('aria-label', item.textContent.trim());
        });
        
        // Кнопки
        const buttons = document.querySelectorAll('[data-testid^="btn-"]');
        buttons.forEach(button => {
            button.setAttribute('role', 'button');
            if (!button.getAttribute('aria-label')) {
                button.setAttribute('aria-label', button.textContent.trim());
            }
        });
        
        // Статус индикаторы
        const statusItems = document.querySelectorAll('[data-testid^="status-"]');
        statusItems.forEach(status => {
            status.setAttribute('role', 'status');
            status.setAttribute('aria-live', 'polite');
        });
    });
    </script>
    """, unsafe_allow_html=True)

# Главная функция для применения всех улучшений
def apply_accessibility_improvements():
    """Применяет все улучшения accessibility"""
    add_accessibility_css()
    add_aria_labels()
    
    # Возвращаем объект с функциями для использования
    return {
        'create_navigation': create_enhanced_navigation,
        'create_button': create_enhanced_button,
        'create_status': create_status_indicator,
        'create_card': create_info_card,
        'create_input': create_enhanced_input,
        'create_progress': create_progress_bar
    }