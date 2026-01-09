#!/usr/bin/env python3
"""
🤖 Telegram Bot Message Handlers
Модуль для обработки и форматирования сообщений.

Включает функциональность:
- Форматирование текста для Telegram
- Разбивка длинных сообщений
- Обработка текстовых сообщений
- Конвертация Markdown в HTML
"""

import asyncio
import logging
import re
import aiohttp
from datetime import datetime
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from core.infrastructure_suite import SETTINGS
from bot.enhanced_legal_bot_adapter import EnhancedLegalBotAdapter

logger = logging.getLogger(__name__)
telegram_logger = logging.getLogger("telegram_operations")


class MessageHandlers:
    """Класс для обработки сообщений в Telegram боте."""

    def __init__(self, bot_instance):
        """Инициализация обработчика сообщений."""
        self.bot = bot_instance.bot
        self.user_history = bot_instance.user_history
        self.processing_users = bot_instance.processing_users
        self.api_gateway_url = bot_instance.api_gateway_url

    def _fix_telegram_formatting(self, text: str) -> str:
        """КРИТИЧЕСКАЯ принудительная постобработка для Telegram форматирования."""
        logger.info(f"🔧 ИСХОДНЫЙ ТЕКСТ ДЛЯ ИСПРАВЛЕНИЯ: {text[:200]}...")

        # 1. Заменяем ### заголовки на **жирный текст**
        text = re.sub(r'^### (.+)$', r'**\1**', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'**\1**', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'**\1**', text, flags=re.MULTILINE)
        text = re.sub(r'^#### (.+)$', r'**\1**', text, flags=re.MULTILINE)

        # Заменяем римские цифры заголовки
        text = re.sub(r'^([IVX]+)\.\s*(.+)$', r'**\1. \2**', text, flags=re.MULTILINE)

        # 2. Заменяем нумерованные списки на буллеты
        text = re.sub(r'^\s*\d+\.\s+(.+)$', r'• \1', text, flags=re.MULTILINE)

        # 3. Заменяем звездочки * на буллеты •
        text = re.sub(r'^\s*\*\s+(.+)$', r'• \1', text, flags=re.MULTILINE)

        # 4. Заменяем дефисы - на буллеты •
        text = re.sub(r'^\s*-\s+(.+)$', r'• \1', text, flags=re.MULTILINE)

        # 5. Удаляем разделители ---
        text = re.sub(r'^---+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^===+\s*$', '', text, flags=re.MULTILINE)

        # 6. Специальная обработка для презентационных отчетов
        # Экранируем потенциально проблематичные символы в Telegram
        text = text.replace('_', '\\_')  # Экранируем подчеркивания
        text = re.sub(r'([*~`\[\]()])', r'\\\1', text)  # Экранируем Markdown символы

        # 7. Очищаем множественные пустые строки
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

        # 8. Удаляем проблематичные символы, которые могут вызвать parsing errors
        text = re.sub(r'[^\w\s\n•\-\.,!?:;()«»"""\'\u0400-\u04FF]', '', text)

        logger.info(f"✅ ИСПРАВЛЕННЫЙ ТЕКСТ: {text[:200]}...")
        return text.strip()

    async def send_formatted_message(self, message: Message, text: str):
        """Отправляет длинные сообщения, разбивая их на части."""
        # КРИТИЧНАЯ ПОСТОБРАБОТКА для правильного форматирования в Telegram
        text = self._fix_telegram_formatting(text)
        logger.info(f"📝 После постобработки: {text[:100]}...")

        max_length = 3800  # Уменьшено для запаса безопасности (Telegram лимит 4096)
        if len(text) > max_length:
            chunks = self.split_long_message(text, max_length)
            for i, chunk in enumerate(chunks):
                await self._send_single_message(message, chunk)
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)
        else:
            await self._send_single_message(message, text)

    def split_long_message(self, text: str, max_length: int) -> list:
        """Разбивает длинное сообщение на части с точным подсчетом символов."""
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""
        paragraphs = text.split('\n\n')

        for paragraph in paragraphs:
            # Точный расчет длины с учетом добавляемых символов
            separator = "\n\n" if current_chunk else ""
            potential_length = len(current_chunk) + len(separator) + len(paragraph)

            if potential_length > max_length:
                # Сохраняем текущий chunk если не пустой
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                # Если один параграф слишком длинный, разбиваем его по предложениям
                if len(paragraph) > max_length:
                    sentence_chunks = self._split_by_sentences(paragraph, max_length)
                    chunks.extend(sentence_chunks[:-1])  # Добавляем все кроме последнего
                    current_chunk = sentence_chunks[-1] if sentence_chunks else ""
                else:
                    current_chunk = paragraph
            else:
                current_chunk += separator + paragraph

        # Добавляем последний chunk
        if current_chunk:
            chunks.append(current_chunk.strip())

        logger.info(f"📑 Разбито на {len(chunks)} частей")
        return chunks

    def _split_by_sentences(self, text: str, max_length: int) -> list:
        """Разбивает текст по предложениям."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    # Если одно предложение слишком длинное, принудительно обрезаем
                    chunks.append(sentence[:max_length-3] + "...")
            else:
                separator = " " if current_chunk else ""
                current_chunk += separator + sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def _send_single_message(self, message: Message, text: str):
        """Отправляет одно сообщение с обработкой ошибок."""
        try:
            await message.answer(text, parse_mode=None)  # Отключаем parse_mode для безопасности
        except TelegramBadRequest as e:
            if "message text is too long" in str(e).lower():
                logger.warning(f"⚠️ Сообщение слишком длинное ({len(text)} символов), разбиваем дополнительно...")
                half_length = len(text) // 2
                await self._send_single_message(message, text[:half_length])
                await self._send_single_message(message, text[half_length:])
            else:
                logger.error(f"❌ Ошибка форматирования Telegram: {e}")
                cleaned_text = re.sub(r'[^\w\s\n•\-\.,!?:;()«»"""\'а-яё]', '', text, flags=re.IGNORECASE)
                await message.answer(cleaned_text, parse_mode=None)
        except Exception as e:
            logger.error(f"❌ Критическая ошибка отправки сообщения: {e}")
            await message.answer("❌ Ошибка при отправке ответа. Попробуйте переформулировать вопрос.", parse_mode=None)

    def _convert_markdown_to_html(self, text: str) -> str:
        """Конвертирует Markdown в HTML."""
        # Заголовки
        text = re.sub(r'^### (.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

        # Жирный и курсив
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)

        # Списки
        text = re.sub(r'^\s*[\*\-]\s+(.+)$', r'• \1', text, flags=re.MULTILINE)

        return text

    def _clean_problematic_markdown(self, text: str) -> str:
        """Очищает проблематичный Markdown для Telegram."""
        # Удаляем неподдерживаемые элементы
        text = re.sub(r'```[\s\S]*?```', '', text)  # Блоки кода
        text = re.sub(r'`[^`]+`', '', text)  # Инлайн код
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Ссылки
        text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)  # Изображения

        # Экранируем специальные символы
        for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            text = text.replace(char, f'\\{char}')

        return text

    async def handle_text_message(self, message: Message):
        """Обработка текстовых сообщений от пользователей."""
        try:
            user_id = message.from_user.id
            question = message.text.strip()

            # Проверяем, не обрабатывается ли уже запрос пользователя
            if user_id in self.processing_users:
                await message.answer("⏳ Подождите, пока обрабатывается предыдущий запрос...")
                return

            # Добавляем пользователя в список обрабатывающихся
            self.processing_users.add(user_id)

            # Логируем запрос
            telegram_logger.info(f"Получен текстовый запрос от пользователя {user_id}: {question}")

            # Добавляем сообщение в историю
            if self.user_history:
                await self.user_history.add_message(
                    user_id=user_id,
                    role="user",
                    content=question,
                    message_type="text"
                )

            try:
                # Отправляем запрос к API Gateway
                result = await self._query_api_gateway(question)

                if result.get('success', False):
                    answer = result.get('answer', 'Ответ не получен')

                    # Добавляем ответ в историю
                    if self.user_history:
                        await self.user_history.add_message(
                            user_id=user_id,
                            role="assistant",
                            content=answer,
                            message_type="text"
                        )

                    # Отправляем ответ с форматированием
                    await self.send_formatted_message(message, answer)

                    telegram_logger.info(f"Успешно отправлен ответ пользователю {user_id}")
                else:
                    error_message = result.get('error', 'Неизвестная ошибка')
                    await message.answer(f"❌ Ошибка при обработке запроса: {error_message}")
                    telegram_logger.error(f"Ошибка API Gateway для пользователя {user_id}: {error_message}")

            except Exception as e:
                logger.error(f"❌ Ошибка при запросе к API Gateway: {e}")
                await message.answer("❌ Произошла ошибка при обработке вашего запроса. Попробуйте еще раз.")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в handle_text_message: {e}")
            await message.answer("❌ Произошла критическая ошибка. Обратитесь к администратору.")
        finally:
            # Убираем пользователя из списка обрабатывающихся
            self.processing_users.discard(user_id)

    async def _query_api_gateway(self, query: str) -> dict:
        """Отправка запроса к API Gateway."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_gateway_url}/api/query"
                data = {
                    "query": query,
                    "max_results": 5
                }

                async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ API Gateway query response: {result.get('success', False)}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ API Gateway query error {response.status}: {error_text}")
                        return {
                            "success": False,
                            "error": f"API Gateway error: {response.status} - {error_text}"
                        }

        except asyncio.TimeoutError:
            logger.error("❌ API Gateway query timeout")
            return {
                "success": False,
                "error": "API Gateway timeout"
            }
        except Exception as e:
            logger.error(f"❌ API Gateway query request error: {e}")
            return {
                "success": False,
                "error": f"API Gateway request error: {str(e)}"
            }