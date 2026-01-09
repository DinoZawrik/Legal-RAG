"""
Обновленные обработчики callback'ов для Telegram бота с PostgreSQL поддержкой.
"""

import logging
from aiogram.types import CallbackQuery
from aiogram import F, Dispatcher

from bot.keyboards import (
    get_main_menu_keyboard,
    create_document_list_keyboard,
    create_search_type_keyboard,
    create_upload_type_keyboard,
    create_database_stats_keyboard,
    create_document_info_keyboard,
)
from core.data_storage_suite import postgres_manager
from bot.text_formatters import (
    format_file_size,
    format_date,
)

logger = logging.getLogger(__name__)


async def handle_main_menu_callback(callback_query: CallbackQuery):
    """Обработчик callback'ов главного меню."""
    try:
        action = callback_query.data.split(":", 1)

        action_map = {
            "database": show_database_menu,
            "search": show_search_menu,
            "regulatory": show_regulatory_documents,
            "legal": show_legal_documents,
            "upload": show_upload_menu,
            "stats": show_statistics,
            "help": show_help,
            "clear": confirm_clear_chat,
        }

        if action in action_map:
            await action_map[action](callback_query)
        else:
            await callback_query.answer("Неизвестная команда")

    except Exception as e:
        logger.error("Ошибка в handle_main_menu_callback: %s", e, exc_info=True)
        await callback_query.answer("Произошла ошибка")


async def show_database_menu(callback_query: CallbackQuery):
    """Показывает меню базы данных."""
    try:
        query = "SELECT id, file_name, document_type, file_size, status, processed_at FROM documents ORDER BY processed_at DESC"
        documents_raw = await postgres_manager.execute_query(query)
        
        documents = [
            {
                "id": doc["id"],
                "filename": doc["file_name"],
                "document_type": doc["document_type"],
                "file_size": doc["file_size"],
                "processing_status": doc["status"],
                "created_at": doc["processed_at"],
            }
            for doc in documents_raw
        ]

        if not documents:
            await callback_query.message.edit_text(
                "📊 *База документов пуста*\n\n"
                "В базе данных пока нет документов.\n"
                "Используйте кнопку 'Загрузить документ' для добавления файлов.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        keyboard = create_document_list_keyboard(documents)
        text = f"📊 *База документов* ({len(documents)} документов)\n\nВыберите документ для просмотра информации:"
        await callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    except Exception as e:
        logger.error("Ошибка в show_database_menu: %s", e, exc_info=True)
        await callback_query.answer("Ошибка при загрузке базы данных")


async def show_search_menu(callback_query: CallbackQuery):
    """Показывает меню поиска."""
    try:
        text = "🔍 *Поиск по документам*\n\nВыберите тип поиска:"
        await callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=create_search_type_keyboard())
    except Exception as e:
        logger.error("Ошибка в show_search_menu: %s", e, exc_info=True)
        await callback_query.answer("Ошибка при загрузке меню поиска")


async def show_regulatory_documents(callback_query: CallbackQuery):
    """Показывает документы по отраслям."""
    try:
        # Этот импорт здесь для примера, в идеале он должен быть на уровне модуля,
        # но оставим для демонстрации возможности
        from core.processing_pipeline import get_industries_with_counts
        industries_with_counts = await get_industries_with_counts()

        if not industries_with_counts:
            await callback_query.message.edit_text(
                "📊 *Документы по отраслям*\n\nДокументов пока нет в базе.\nЗагрузите документы через команду /upload.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        from bot.keyboards import create_industry_selection_keyboard_with_counts
        keyboard = create_industry_selection_keyboard_with_counts(industries_with_counts, [])
        total_docs = sum(industries_with_counts.values())
        text = (
            f"📊 *Документы по отраслям* ({total_docs} документов)\n\n"
            f"Доступно отраслей: {len(industries_with_counts)}\n\n"
            "_Выберите отрасли для работы:_"
        )
        await callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    except Exception as e:
        logger.error("Ошибка в show_regulatory_documents: %s", e, exc_info=True)
        await callback_query.answer("Ошибка при загрузке документов по отраслям")


async def show_legal_documents(callback_query: CallbackQuery):
    """Показывает юридические документы."""
    try:
        query = "SELECT id, file_name, document_type, file_size, status, processed_at FROM documents WHERE document_type = $1 ORDER BY processed_at DESC"
        documents_raw = await postgres_manager.execute_query(query, {'doc_type': 'legal'})
        
        documents = [
            {
                "id": doc["id"],
                "filename": doc["file_name"],
                "document_type": doc["document_type"],
                "file_size": doc["file_size"],
                "processing_status": doc["status"],
                "created_at": doc["processed_at"],
            }
            for doc in documents_raw
        ]

        if not documents:
            await callback_query.message.edit_text(
                "⚖️ *Юридические документы*\n\nЮридических документов пока нет в базе.\nЗагрузите соответствующие файлы.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        keyboard = create_document_list_keyboard(documents)
        text = f"⚖️ *Юридические документы* ({len(documents)} документов)\n\nВыберите документ для просмотра:"
        await callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    except Exception as e:
        logger.error("Ошибка в show_legal_documents: %s", e, exc_info=True)
        await callback_query.answer("Ошибка при загрузке юридических документов")


async def show_upload_menu(callback_query: CallbackQuery):
    """Показывает меню загрузки."""
    try:
        text = (
            "📁 *Загрузка документов*\n\n"
            "Поддерживаемые форматы:\n"
            "• PDF, TXT, MD, RTF\n\n"
            "Просто отправьте файл в чат для автоматической обработки!"
        )
        await callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=create_upload_type_keyboard())
    except Exception as e:
        logger.error("Ошибка в show_upload_menu: %s", e, exc_info=True)
        await callback_query.answer("Ошибка при загрузке меню загрузки")


async def show_statistics(callback_query: CallbackQuery):
    """Показывает статистику базы данных."""
    try:
        stats_query = """
            SELECT
                COUNT(*) as total_documents,
                SUM(file_size) as total_size,
                AVG(file_size) as avg_size
            FROM documents
        """
        stats_result = await postgres_manager.execute_query(stats_query)
        stats = dict(stats_result) if stats_result else {}

        chunk_stats_query = "SELECT COUNT(*) as total_chunks, AVG(LENGTH(text)) as avg_chunk_length FROM chunks"
        chunk_stats_result = await postgres_manager.execute_query(chunk_stats_query)
        chunk_stats = dict(chunk_stats_result) if chunk_stats_result else {}

        type_stats_query = "SELECT document_type, COUNT(*) as count, SUM(file_size) as total_size FROM documents GROUP BY document_type"
        type_stats = await postgres_manager.execute_query(type_stats_query)

        total_size_str = format_file_size(stats.get("total_size", 0) or 0)
        avg_size_str = format_file_size(int(stats.get("avg_size", 0) or 0))
        avg_chunk_str = f"{int(chunk_stats.get('avg_chunk_length', 0) or 0)} символов"

        text = (
            f"📈 *Статистика базы данных*\n\n"
            f"📄 Всего документов: *{stats.get('total_documents', 0)}*\n"
            f"💾 Общий размер: *{total_size_str}*\n"
            f"📊 Средний размер: *{avg_size_str}*\n"
            f"📝 Всего чанков: *{chunk_stats.get('total_chunks', 0)}*\n"
            f"📏 Средняя длина чанка: *{avg_chunk_str}*\n\n"
        )

        if type_stats:
            text += "*По типам документов:*\n"
            for type_stat_raw in type_stats:
                type_stat = dict(type_stat_raw)
                doc_type = type_stat["document_type"]
                count = type_stat["count"]
                size = format_file_size(type_stat.get("total_size", 0) or 0)
                
                type_map = {"regulatory": "📋 Регуляторные", "legal": "⚖️ Юридические"}
                icon_name = type_map.get(doc_type, "📄 Обычные")
                text += f"{icon_name}: *{count}* ({size})\n"

        await callback_query.message.edit_text(
            text, parse_mode="Markdown", reply_markup=create_database_stats_keyboard()
        )

    except Exception as e:
        logger.error("Ошибка в show_statistics: %s", e, exc_info=True)
        await callback_query.answer("Ошибка при загрузке статистики")


async def show_help(callback_query: CallbackQuery):
    """Показывает справку."""
    try:
        text = (
            "❓ *Справка по боту*\n\n"
            "*Основные возможности:*\n"
            "• 📊 Просмотр и поиск документов\n"
            "• 📋⚖️ Работа с регуляторными и юридическими типами\n"
            "• 📁 Загрузка новых документов (PDF, TXT, MD, RTF)\n"
            "• 📈 Просмотр статистики\n\n"
            "*Как использовать:*\n"
            "1. Отправьте файл в чат для обработки\n"
            "2. Используйте меню для навигации\n"
            "3. Задавайте вопросы по загруженным документам"
        )
        await callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())
    except Exception as e:
        logger.error("Ошибка в show_help: %s", e, exc_info=True)
        await callback_query.answer("Ошибка при загрузке справки")


async def confirm_clear_chat(callback_query: CallbackQuery):
    """Запрашивает подтверждение очистки чата."""
    await callback_query.answer("Функция очистки чата будет добавлена позже")


async def handle_document_info(callback_query: CallbackQuery):
    """Показывает информацию о документе."""
    try:
        doc_id = callback_query.data.split(":", 1)
        document = await postgres_manager.get_document(doc_id)

        if not document:
            await callback_query.answer("Документ не найден")
            return

        chunks_query = "SELECT text FROM chunks WHERE document_id = $1"
        chunks = await postgres_manager.execute_query(chunks_query, {'doc_id': doc_id})

        filename = document["file_name"]
        doc_type = document["document_type"]
        file_size = format_file_size(document.get("file_size", 0))
        created_at = format_date(document.get("processed_at"))
        status = document.get("status", "N/A")

        type_map = {"regulatory": "📋 Регуляторный", "legal": "⚖️ Юридический"}
        type_icon_name = type_map.get(doc_type, "📄 Обычный")
        type_name = f"{type_icon_name} документ"

        status_icon = "✅" if status == "completed" else "⏳"

        text = (
            f"ℹ️ *Информация о документе*\n\n"
            f"📁 *Название:* {filename}\n"
            f"📋 *Тип:* {type_name}\n"
            f"💾 *Размер:* {file_size}\n"
            f"📅 *Загружен:* {created_at}\n"
            f"{status_icon} *Статус:* {status}\n"
            f"📝 *Чанков:* {len(chunks)}\n\n"
        )

        if chunks:
            total_content_length = sum(len(chunk["text"]) for chunk in chunks)
            avg_chunk_length = total_content_length // len(chunks) if chunks else 0
            text += f"📏 *Общий объем:* {total_content_length} символов\n"
            text += f"📊 *Средняя длина чанка:* {avg_chunk_length} символов"

        await callback_query.message.edit_text(
            text, parse_mode="Markdown", reply_markup=create_document_info_keyboard(doc_id)
        )

    except Exception as e:
        logger.error("Ошибка в handle_document_info: %s", e, exc_info=True)
        await callback_query.answer("Ошибка при загрузке информации о документе")


def register_postgresql_handlers(dp: Dispatcher):
    """Регистрирует обработчики для работы с PostgreSQL."""
    dp.callback_query.register(handle_main_menu_callback, F.data.startswith("main_menu:"))
    dp.callback_query.register(handle_document_info, F.data.startswith("doc_info:"))
    
    @dp.callback_query(F.data == "back_to_main")
    async def back_to_main_handler(callback_query: CallbackQuery):
        await callback_query.message.edit_text(
            "🏠 *Главное меню*\n\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )
