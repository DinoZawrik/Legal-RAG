"""Модуль быстрых ответов и шаблонов вопросов"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def create_quick_questions_keyboard():
    """Создает клавиатуру с быстрыми вопросами"""
    keyboard = [
        [InlineKeyboardButton(text="📊 Общая статистика", callback_data="quick:stats")],
        [InlineKeyboardButton(text="💰 Финансовые данные", callback_data="quick:finance")],
        [InlineKeyboardButton(text="🏗️ Проекты в разработке", callback_data="quick:projects")],
        [InlineKeyboardButton(text="📈 Тренды и анализ", callback_data="quick:trends")],
        [InlineKeyboardButton(text="🔍 Поиск по документам", callback_data="quick:search")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


QUICK_QUESTIONS = {
    "stats": "Какая общая статистика по всем проектам?",
    "finance": "Какие финансовые показатели представлены в документах?",
    "projects": "Какие проекты находятся на стадии создания?",
    "trends": "Какие тренды можно выделить из представленных данных?",
    "search": "Найди информацию о конкретном регионе или проекте",
}
