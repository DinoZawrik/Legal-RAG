"""Модуль для создания клавиатур Telegram бота"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

# --- Константы для callback_data (инлайн-клавиатуры) ---
DOC_MANAGE_PREFIX = "doc_manage"
PAGINATION_PREFIX = "page"
MAIN_MENU_PREFIX = "main_menu"
REGULATORY_PREFIX = "regulatory"
INDUSTRY_PREFIX = "industry"
REG_DOC_TYPE_PREFIX = "reg_doc_type"
FILE_UPLOAD_PREFIX = "file_upload"
DATABASE_PREFIX = "database"
SEARCH_PREFIX = "search"
DOC_TYPE_PREFIX = "doc_type"


# --- Тексты для кнопок (постоянные клавиатуры) ---
class ReplyButtons:
    SMART_SEARCH = " Умный поиск"
    ALL_DOCS = " Все документы"
    REGULATORY = " Регуляторные"
    STATS = " Статистика"
    UPLOAD = " Загрузить"
    SETTINGS = " Настройки"
    HELP = " Помощь"
    CLEAR_CHAT = " Очистить чат"
    CANCEL_UPLOAD = " Отменить загрузку"
    MY_DOCS = " Мои документы"
    MAIN_MENU = " Главное меню"
    VECTOR_SEARCH = " Векторный поиск"
    REGULATORY_SEARCH = " Регуляторный поиск"
    SQL_QUERY = " SQL запрос"
    SEARCH_SETTINGS = " Настройки поиска"
    BY_INDUSTRIES = " По отраслям"
    BY_DOC_TYPE = " По типу документа"
    SEARCH_BY_CONTENT = " Поиск по содержанию"
    STATS_BY_INDUSTRIES = " Статистика по отраслям"
    UPLOAD_DOCUMENT = " Загрузить документ"
    REQUEST_PERMISSION = " Запросить права"


# --- Фабрика клавиатур ---

def _create_reply_keyboard(buttons, placeholder="", one_time=False):
    """Хелпер для создания ReplyKeyboardMarkup."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in buttons],
        resize_keyboard=True,
        one_time_keyboard=one_time,
        input_field_placeholder=placeholder if placeholder else None,
    )


def get_main_menu_keyboard(user_has_upload_permission=True):
    """Возвращает главную клавиатуру меню с учетом прав пользователя."""
    buttons = [
        [ReplyButtons.SMART_SEARCH, ReplyButtons.ALL_DOCS],
        [ReplyButtons.REGULATORY, ReplyButtons.STATS],
    ]
    
    # Показываем UPLOAD только если есть права, иначе показываем REQUEST_PERMISSION
    if user_has_upload_permission:
        buttons.append([ReplyButtons.UPLOAD, ReplyButtons.SETTINGS])
    else:
        buttons.append([ReplyButtons.REQUEST_PERMISSION, ReplyButtons.SETTINGS])
    
    buttons.append([ReplyButtons.HELP, ReplyButtons.CLEAR_CHAT])
    
    return _create_reply_keyboard(buttons, "Введите ваш вопрос или выберите действие...")


def get_upload_keyboard():
    """Возвращает клавиатуру для режима загрузки."""
    buttons = [[ReplyButtons.CANCEL_UPLOAD], [ReplyButtons.MY_DOCS]]
    return _create_reply_keyboard(buttons)


def get_search_menu_keyboard():
    """Возвращает клавиатуру для режима поиска."""
    buttons = [
        [ReplyButtons.VECTOR_SEARCH, ReplyButtons.REGULATORY_SEARCH],
        [ReplyButtons.SQL_QUERY, ReplyButtons.SEARCH_SETTINGS],
        [ReplyButtons.MAIN_MENU],
    ]
    return _create_reply_keyboard(buttons, "Выберите тип поиска или введите запрос...")


def get_regulatory_menu_keyboard():
    """Возвращает клавиатуру для работы с регуляторными документами."""
    buttons = [
        [ReplyButtons.BY_INDUSTRIES, ReplyButtons.BY_DOC_TYPE],
        [ReplyButtons.SEARCH_BY_CONTENT, ReplyButtons.STATS_BY_INDUSTRIES],
        [ReplyButtons.UPLOAD_DOCUMENT, ReplyButtons.MAIN_MENU],
    ]
    return _create_reply_keyboard(buttons, "Работа с документами по отраслям...")


def get_back_to_main_keyboard():
    """Возвращает простую клавиатуру с кнопкой 'Главное меню'."""
    buttons = [[ReplyButtons.MAIN_MENU]]
    return _create_reply_keyboard(buttons, "Нажмите, чтобы вернуться в главное меню...")


def get_keyboard_by_context(context: str, user_has_upload_permission=True):
    """
    Возвращает соответствующую ReplyKeyboardMarkup по контексту.
    """
    keyboards = {
        "main": lambda: get_main_menu_keyboard(user_has_upload_permission),
        "search": get_search_menu_keyboard,
        "regulatory": get_regulatory_menu_keyboard,
        "upload": get_upload_keyboard,
        "back": get_back_to_main_keyboard,
    }
    return keyboards.get(context, lambda: get_main_menu_keyboard(user_has_upload_permission))()


# --- Инлайн-клавиатуры ---

def _add_main_menu_button(keyboard: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """Добавляет кнопку 'Главное меню' к существующей инлайн-клавиатуре."""
    new_keyboard = keyboard.inline_keyboard.copy()
    new_keyboard.append(
        [InlineKeyboardButton(text=ReplyButtons.MAIN_MENU, callback_data=f"{MAIN_MENU_PREFIX}:back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=new_keyboard)


def create_document_management_keyboard():
    """Клавиатура для управления документами."""
    inline_keyboard = [
        [
            InlineKeyboardButton(text=" Выбрать документы", callback_data=f"{DOC_MANAGE_PREFIX}:select"),
            InlineKeyboardButton(text=" Очистить чат", callback_data=f"{DOC_MANAGE_PREFIX}:clear"),
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return _add_main_menu_button(keyboard)


def create_clear_chat_confirmation_keyboard():
    """Клавиатура подтверждения очистки чата."""
    inline_keyboard = [
        [InlineKeyboardButton(text=" Да, очистить", callback_data=f"{DOC_MANAGE_PREFIX}:confirm_clear")],
        [InlineKeyboardButton(text=" Нет, отменить", callback_data=f"{DOC_MANAGE_PREFIX}:cancel_clear")],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return _add_main_menu_button(keyboard)


def create_pagination_keyboard(current_page, total_pages, prefix=PAGINATION_PREFIX):
    """Универсальная клавиатура пагинации."""
    if total_pages <= 1:
        return None

    buttons = []
    if current_page > 1:
        buttons.append(InlineKeyboardButton(text="", callback_data=f"{prefix}:{current_page-1}"))

    buttons.append(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="current_page"))

    if current_page < total_pages:
        buttons.append(InlineKeyboardButton(text="", callback_data=f"{prefix}:{current_page+1}"))

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def create_selection_keyboard(
    items, selected_items, prefix, done_callback, select_all_callback, clear_all_callback
):
    """Универсальная клавиатура для выбора элементов."""
    inline_keyboard = []
    for item_id, item_name in items.items():
        emoji = "" if item_id in selected_items else ""
        inline_keyboard.append(
            [InlineKeyboardButton(text=f"{emoji} {item_name}", callback_data=f"{prefix}:toggle:{item_id}")]
        )

    control_buttons = [
        InlineKeyboardButton(text=" Выбрать все", callback_data=select_all_callback),
        InlineKeyboardButton(text=" Очистить", callback_data=clear_all_callback),
    ]
    inline_keyboard.append(control_buttons)
    inline_keyboard.append([InlineKeyboardButton(text=" Готово", callback_data=done_callback)])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return _add_main_menu_button(keyboard)


def create_documents_selection_keyboard(documents, selected_doc_ids):
    """Генерирует клавиатуру для выбора PDF документов."""
    doc_items = {doc.get("id"): doc.get("filename", "Неизвестный документ") for doc in documents}
    return create_selection_keyboard(
        items=doc_items,
        selected_items=selected_doc_ids,
        prefix="doc_select",
        done_callback="doc_select:done",
        select_all_callback="doc_select:select_all",
        clear_all_callback="doc_select:clear_all",
    )


def create_industry_selection_keyboard(industries, selected_industries):
    """Создает клавиатуру для выбора отраслей."""
    industry_items = {industry: industry for industry in industries}
    return create_selection_keyboard(
        items=industry_items,
        selected_items=selected_industries,
        prefix=INDUSTRY_PREFIX,
        done_callback=f"{INDUSTRY_PREFIX}:done",
        select_all_callback=f"{INDUSTRY_PREFIX}:select_all",
        clear_all_callback=f"{INDUSTRY_PREFIX}:clear_all",
    )


def create_regulatory_document_type_keyboard():
    """Создает клавиатуру для выбора типа регуляторного документа."""
    doc_types = ["постановление", "приказ", "распоряжение", "закон", "указ", "решение"]
    inline_keyboard = []
    for doc_type in doc_types:
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=f" {doc_type.capitalize()}",
                    callback_data=f"{REG_DOC_TYPE_PREFIX}:{doc_type}",
                )
            ]
        )
    inline_keyboard.append(
        [
            InlineKeyboardButton(text=" Все типы", callback_data=f"{REG_DOC_TYPE_PREFIX}:all"),
            InlineKeyboardButton(text=" Отмена", callback_data=f"{REG_DOC_TYPE_PREFIX}:cancel"),
        ]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return _add_main_menu_button(keyboard)


def create_file_upload_keyboard():
    """Создает клавиатуру для загрузки файлов."""
    inline_keyboard = [
        [InlineKeyboardButton(text=" Загрузить текстовый файл", callback_data=f"{FILE_UPLOAD_PREFIX}:text_file")],
        [InlineKeyboardButton(text=" Отмена", callback_data=f"{FILE_UPLOAD_PREFIX}:cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def create_database_stats_keyboard():
    """Создает клавиатуру для статистики базы данных."""
    inline_keyboard = [
        [
            InlineKeyboardButton(text=" Обновить статистику", callback_data=f"{DATABASE_PREFIX}:refresh"),
            InlineKeyboardButton(text=" Детальная статистика", callback_data=f"{DATABASE_PREFIX}:detailed"),
        ],
        [
            InlineKeyboardButton(text=" По отраслям", callback_data=f"{DATABASE_PREFIX}:by_industry"),
            InlineKeyboardButton(text=" По типам документов", callback_data=f"{DATABASE_PREFIX}:by_type"),
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return _add_main_menu_button(keyboard)
