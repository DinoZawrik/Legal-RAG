"""Модуль расширенных форматтеров для Telegram бота"""

import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime


class EnhancedFormatter:
    """Расширенный форматтер для различных типов данных"""

    @staticmethod
    def format_search_results(results: List[Dict], limit: int = 10) -> str:
        """
        Форматирует результаты поиска для отображения в Telegram

        Args:
            results: Список результатов поиска
            limit: Максимальное количество результатов для отображения

        Returns:
            str: Отформатированный текст результатов поиска
        """
        if not results:
            return " По вашему запросу ничего не найдено"

        formatted_results = [" *Результаты поиска:*\n"]
        display_results = results[:limit]

        for i, result in enumerate(display_results, 1):
            result_type = result.get("type", "unknown")
            if result_type == "vector":
                formatted_results.append(EnhancedFormatter._format_vector_result(result, i))
            elif result_type == "regulatory":
                formatted_results.append(EnhancedFormatter._format_regulatory_result(result, i))
            elif result_type == "sql":
                formatted_results.append(EnhancedFormatter._format_sql_result(result, i))
            else:
                formatted_results.append(EnhancedFormatter._format_generic_result(result, i))

        total_count = len(results)
        if total_count > limit:
            formatted_results.append(f"\n *Показано {limit} из {total_count} результатов*")
            formatted_results.append("_Используйте пагинацию для просмотра остальных результатов_")

        return "\n".join(formatted_results)

    @staticmethod
    def _format_vector_result(result: Dict, index: int) -> str:
        """Форматирует результат векторного поиска"""
        # Извлекаем filename с приоритетом: корневой уровень -> metadata
        filename = result.get("filename")
        if not filename:
            metadata = result.get("metadata", {})
            filename = metadata.get("original_filename") or metadata.get("filename") or metadata.get("file_name", "Неизвестный файл")

        filename = EnhancedFormatter._escape_markdown(filename)
        content = EnhancedFormatter._escape_markdown(result.get("content", "")[:200])
        score = result.get("score", 0)
        document_type = result.get("document_type", "Документ")
        type_emoji = {"pdf": "", "regulatory": "", "legal": ""}.get(document_type, "")

        return (
            f"{index}. {type_emoji} **{filename}**\n"
            f"    Релевантность: {score:.2f}\n"
            f"    {content}{'...' if len(result.get('content', '')) > 200 else ''}\n"
        )

    @staticmethod
    def _format_regulatory_result(result: Dict, index: int) -> str:
        """Форматирует результат регуляторного поиска"""
        title = EnhancedFormatter._escape_markdown(result.get("title", "Без названия"))
        industry = EnhancedFormatter._escape_markdown(result.get("industry", "Не указана"))
        doc_type = EnhancedFormatter._escape_markdown(result.get("document_type", "Документ"))
        content = EnhancedFormatter._escape_markdown(result.get("content", "")[:200])

        return (
            f"{index}.  **{title}**\n"
            f"    Отрасль: {industry}\n"
            f"    Тип: {doc_type}\n"
            f"    {content}{'...' if len(result.get('content', '')) > 200 else ''}\n"
        )

    @staticmethod
    def _format_sql_result(result: Dict, index: int) -> str:
        """Форматирует результат SQL запроса"""
        table_name = EnhancedFormatter._escape_markdown(result.get("table_name", "Неизвестная таблица"))
        row_data = result.get("data", {})
        formatted_data = [f"   • {EnhancedFormatter._escape_markdown(str(k))}: {EnhancedFormatter._escape_markdown(str(v))}" for k, v in row_data.items()]
        return f"{index}.  **{table_name}**\n" f"{'\n'.join(formatted_data)}\n"

    @staticmethod
    def _format_generic_result(result: Dict, index: int) -> str:
        """Форматирует общий результат поиска"""
        # Извлекаем filename или title с приоритетом
        title = result.get("title")
        if not title:
            filename = result.get("filename")
            if not filename:
                metadata = result.get("metadata", {})
                filename = metadata.get("original_filename") or metadata.get("filename") or metadata.get("file_name", "Без названия")
            title = filename

        title = EnhancedFormatter._escape_markdown(title)
        content = EnhancedFormatter._escape_markdown(result.get("content", result.get("description", ""))[:200])
        return (
            f"{index}.  **{title}**\n"
            f"    {content}{'...' if len(result.get('content', result.get('description', ''))) > 200 else ''}\n"
        )

    @staticmethod
    def format_document_info(document: Dict) -> str:
        """Форматирует информацию о документе"""
        # Извлекаем filename с приоритетом из metadata
        filename = document.get("filename")
        if not filename:
            metadata = document.get("metadata", {})
            filename = metadata.get("original_filename") or metadata.get("filename") or metadata.get("file_name", "Неизвестный файл")
        doc_type = document.get("document_type", "Неизвестный тип")
        file_size = document.get("file_size", 0)
        created_at = document.get("created_at")
        chunk_count = document.get("chunk_count", 0)
        industry = document.get("industry")
        doc_subtype = document.get("document_subtype")

        size_str = format_file_size(file_size)
        date_str = format_date(created_at) if created_at else "Не указана"
        type_emoji = {"pdf": "", "regulatory": "", "legal": ""}.get(doc_type, "")

        info_lines = [
            f"{type_emoji} **Информация о документе**\n",
            f" **Имя файла:** {EnhancedFormatter._escape_markdown(filename)}",
            f" **Тип документа:** {EnhancedFormatter._escape_markdown(doc_type)}",
            f" **Размер:** {size_str}",
            f" **Дата загрузки:** {date_str}",
            f" **Количество фрагментов:** {chunk_count}",
        ]
        if industry:
            info_lines.append(f" **Отрасль:** {EnhancedFormatter._escape_markdown(industry)}")
        if doc_subtype:
            info_lines.append(f" **Подтип:** {EnhancedFormatter._escape_markdown(doc_subtype)}")
        return "\n".join(info_lines)

    @staticmethod
    def format_statistics_data(stats_data: Dict) -> str:
        """Централизованно форматирует все виды статистических данных."""
        if not stats_data or "error" in stats_data:
            return f" Ошибка получения статистики: {stats_data.get('error', 'Неизвестная ошибка')}"

        stats_type = stats_data.get("type")
        data = stats_data.get("data", {})

        formatters = {
            "general": EnhancedFormatter._format_general_statistics,
            "by_type": EnhancedFormatter._format_type_statistics,
            "by_date": EnhancedFormatter._format_date_statistics,
            "users": EnhancedFormatter._format_users_statistics,
            "custom": EnhancedFormatter._format_custom_statistics,
        }

        formatter = formatters.get(stats_type)
        if formatter:
            # Для 'custom' передаем доп. аргумент
            if stats_type == "custom":
                return formatter(data, stats_data.get("query", ""))
            return formatter(data)
        
        return " Неизвестный тип статистики."

    @staticmethod
    def _format_general_statistics(data: Dict) -> str:
        """Форматирует общую статистику."""
        text = " **Общая статистика по документам**\n\n"
        text += f" **Всего документов:** {data.get('total_documents', 0)}\n"
        text += f" **Общий размер:** {format_file_size(data.get('total_size', 0))}\n"
        text += f" **Средний размер:** {format_file_size(int(data.get('avg_size', 0)))}\n"
        text += f" **Всего фрагментов (чанков):** {data.get('total_chunks', 0)}\n"
        if data.get("latest_upload"):
            text += f" **Последняя загрузка:** {format_date(data['latest_upload'])}\n"
        return text

    @staticmethod
    def _format_type_statistics(data: List[Dict]) -> str:
        """Форматирует статистику по типам документов."""
        text = " **Статистика по типам документов**\n\n"
        if not data:
            return text + "Нет данных по типам."
        
        for item in data:
            doc_type = item.get("document_type", "Неизвестный")
            count = item.get("count", 0)
            total_size = format_file_size(item.get("total_size", 0))
            type_emoji = {"regulatory": "", "legal": "", "general": ""}.get(doc_type, "")
            text += f"{type_emoji} **{doc_type.capitalize()}:** {count} док. ({total_size})\n"
        return text

    @staticmethod
    def _format_date_statistics(data: List[Dict]) -> str:
        """Форматирует статистику по датам загрузки."""
        text = " **Статистика загрузок по месяцам**\n\n"
        if not data:
            return text + "Нет данных по датам."

        for item in data:
            try:
                month_dt = item.get("month")
                month_str = format_date(month_dt, "%B %Y") if month_dt else "Неизвестно"
                count = item.get("count", 0)
                total_size = format_file_size(item.get("total_size", 0))
                text += f"   - **{month_str}:** {count} док. ({total_size})\n"
            except Exception:
                continue # Пропускаем некорректные записи
        return text

    @staticmethod
    def _format_users_statistics(data: Dict) -> str:
        """Форматирует статистику по пользователям."""
        text = " **Статистика по пользователям**\n\n"
        if data.get("error"):
             return text + f"_{data['error']}_"
        
        text += f" **Всего пользователей:** {data.get('total_users', 'N/A')}\n"
        text += f" **Активных сегодня:** {data.get('active_today', 'N/A')}\n"
        text += f" **Активных за неделю:** {data.get('active_week', 'N/A')}\n"
        return text

    @staticmethod
    def _format_custom_statistics(data: List, query: str) -> str:
        """Форматирует пользовательскую статистику."""
        text = " **Результаты пользовательского запроса**\n\n"
        if query:
            text += f"**Запрос:** `{query}`\n\n"
        if not data:
            return text + "Нет данных для отображения."

        if isinstance(data, dict):
            headers = list(data.keys())
            text += " | ".join([f"**{h}**" for h in headers]) + "\n"
            text += "|".join(["---" for _ in headers]) + "\n"
            for row in data[:15]:
                text += " | ".join([str(v) for v in row.values()]) + "\n"
            if len(data) > 15:
                text += f"\n_Показаны первые 15 из {len(data)} строк_"
        else:
            for i, item in enumerate(data[:15], 1):
                text += f"{i}. {item}\n"
            if len(data) > 15:
                text += f"\n_Показаны первые 15 из {len(data)} элементов_"
        return text

    @staticmethod
    def _escape_markdown(text: Any) -> str:
        """Экранирует специальные символы Markdown в строке."""
        if not isinstance(text, str):
            text = str(text)
        escape_chars = r"\_*[]()~`>#+-=|{}.!"
        return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

    @staticmethod
    def truncate_text(text: str, max_length: int = 1000) -> str:
        """Обрезает текст до заданной длины."""
        return text[:max_length] + "..." if len(text) > max_length else text

    @staticmethod
    def format_text(text: str) -> str:
        """
        Форматирует текст для отображения в Telegram с использованием HTML разметки.
        Убирает экранирование и улучшает читаемость.
        """
        if not text:
            return ""
        
        # Удаляем экранирование символов
        formatted_text = text.replace('\\*', '*').replace('\\_', '_').replace('\\(', '(').replace('\\)', ')')
        formatted_text = formatted_text.replace('\\.', '.').replace('\\-', '-').replace('\\|', '|')
        formatted_text = formatted_text.replace('\\[', '[').replace('\\]', ']').replace('\\{', '{').replace('\\}', '}')
        
        # Конвертируем Markdown в HTML
        # Жирный текст **text** -> <b>text</b>
        formatted_text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', formatted_text)
        # Курсив *text* -> <i>text</i>
        formatted_text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<i>\1</i>', formatted_text)
        # Подчеркивание _text_ -> <u>text</u>
        formatted_text = re.sub(r'_([^_\n]+)_', r'<i>\1</i>', formatted_text)
        
        # Улучшаем форматирование списков
        formatted_text = re.sub(r'^\s*[*•]\s+([^\n]+)', r'• \1', formatted_text, flags=re.MULTILINE)
        
        # Убираем двойные переносы строк
        formatted_text = re.sub(r'\n\n+', '\n\n', formatted_text)
        
        # Улучшаем форматирование источников
        formatted_text = re.sub(r' Источники?:\s*\n', '\n <b>Источники:</b>\n', formatted_text)
        
        # Экранируем HTML символы
        formatted_text = formatted_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        # Восстанавливаем наши HTML теги
        formatted_text = formatted_text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
        formatted_text = formatted_text.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
        formatted_text = formatted_text.replace('&lt;u&gt;', '<u>').replace('&lt;/u&gt;', '</u>')
        
        return formatted_text.strip()

    @staticmethod
    def split_long_message(text: str, max_length: int = 4000) -> List[str]:
        """
        Разбивает длинное сообщение на части для отправки в Telegram.
        
        Args:
            text: Текст для разбивки
            max_length: Максимальная длина одной части (по умолчанию 4000 символов)
            
        Returns:
            List[str]: Список частей сообщения
        """
        if not text:
            return [""]
        
        if len(text) <= max_length:
            return [text]
        
        # Разделяем по логическим блокам (источники отдельно)
        sources_match = re.search(r'\n\s*\*?Источники?\*?:\s*\n(.+)', text, re.DOTALL | re.IGNORECASE)
        
        if sources_match:
            main_text = text[:sources_match.start()].strip()
            sources_text = f" *Источники:*\n{sources_match.group(1).strip()}"
            
            # Разбиваем основной текст
            main_parts = EnhancedFormatter._split_text_by_length(main_text, max_length)
            
            # Разбиваем источники отдельно
            sources_parts = EnhancedFormatter._split_text_by_length(sources_text, max_length)
            
            return main_parts + sources_parts
        else:
            return EnhancedFormatter._split_text_by_length(text, max_length)
    
    @staticmethod
    def _split_text_by_length(text: str, max_length: int) -> List[str]:
        """Вспомогательный метод для разбивки текста по длине."""
        if len(text) <= max_length:
            return [text]
        
        parts = []
        current_part = ""
        
        # Разбиваем по абзацам
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            if len(current_part + '\n\n' + paragraph) > max_length:
                if current_part:
                    parts.append(current_part.strip())
                    current_part = paragraph
                else:
                    # Если абзац слишком длинный, разбиваем по предложениям
                    sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                    for sentence in sentences:
                        if len(current_part + ' ' + sentence) > max_length:
                            if current_part:
                                parts.append(current_part.strip())
                                current_part = sentence
                            else:
                                # Если предложение слишком длинное, принудительно разрезаем
                                parts.append(sentence[:max_length])
                                current_part = sentence[max_length:]
                        else:
                            current_part += (' ' + sentence) if current_part else sentence
            else:
                current_part += ('\n\n' + paragraph) if current_part else paragraph
        
        if current_part:
            parts.append(current_part.strip())
        
        return parts if parts else [""]


# Глобальный экземпляр и функции-обертки для удобства
enhanced_formatter = EnhancedFormatter()

def get_enhanced_formatter() -> EnhancedFormatter:
    """Возвращает синглтон-экземпляр форматтера."""
    return enhanced_formatter

def format_search_results(results: List[Dict], limit: int = 10) -> str:
    """Форматирует результаты поиска."""
    return get_enhanced_formatter().format_search_results(results, limit)

def format_document_info(document: Dict) -> str:
    """Форматирует информацию о документе."""
    return get_enhanced_formatter().format_document_info(document)

def format_statistics_data(stats_data: Dict) -> str:
    """Форматирует все виды статистических данных."""
    return get_enhanced_formatter().format_statistics_data(stats_data)

def truncate_text(text: str, max_length: int = 1000) -> str:
    """Обрезает текст."""
    return get_enhanced_formatter().truncate_text(text, max_length)

def format_text(text: str) -> str:
    """Форматирует текст для Telegram."""
    return get_enhanced_formatter().format_text(text)

def split_long_message(text: str, max_length: int = 4000) -> List[str]:
    """Разбивает длинное сообщение на части."""
    return get_enhanced_formatter().split_long_message(text, max_length)

def format_file_size(size_bytes: int) -> str:
    """Форматирует размер файла в читаемый формат (КБ, МБ, ГБ)."""
    if not isinstance(size_bytes, (int, float)) or size_bytes < 0:
        return "0 Б"
    if size_bytes == 0:
        return "0 Б"
    size_names = ("Б", "КБ", "МБ", "ГБ", "ТБ")
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.1f} {size_names[i]}"

def format_date(date_value: Any, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Форматирует дату в читаемый формат."""
    if not date_value:
        return "Неизвестно"
    try:
        if isinstance(date_value, str):
            dt = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        elif isinstance(date_value, datetime):
            dt = date_value
        else:
            return str(date_value)
        return dt.strftime(fmt)
    except (ValueError, TypeError):
        return str(date_value)
