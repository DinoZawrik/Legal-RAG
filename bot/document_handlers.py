#!/usr/bin/env python3
"""
🤖 Telegram Bot Document Handlers
Модуль для обработки документов в телеграм-боте.

Включает функциональность:
- Обработка загрузки документов
- Выбор типа документа
- Обработка архивов
- Интеграция с API Gateway
"""

import asyncio
import logging
import os
import tempfile
import uuid
import aiohttp
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.admin_panel import check_user_permission_async
from bot.keyboards import DOC_TYPE_PREFIX
from bot.states import Form
from bot.presentation_scanner import scan_presentation_for_bot

logger = logging.getLogger(__name__)
telegram_logger = logging.getLogger("telegram_operations")


class DocumentHandlers:
    """Класс для обработки документов в Telegram боте."""

    def __init__(self, bot_instance):
        """Инициализация обработчика документов."""
        self.bot = bot_instance.bot
        self.processing_pipeline = bot_instance.processing_pipeline
        self.archive_processor = bot_instance.archive_processor
        self.processing_users = bot_instance.processing_users
        self.api_gateway_url = bot_instance.api_gateway_url
        self.user_history = bot_instance.user_history
        self.async_redis = bot_instance.async_redis

    async def handle_document_upload(self, message: Message, state: FSMContext):
        """Обработка загрузки документа."""
        try:
            user_id = message.from_user.id
            telegram_logger.info(f"Получен документ от пользователя {user_id}")

            # Проверяем права доступа
            has_permission = await check_user_permission_async(user_id)
            if not has_permission:
                await message.answer("❌ У вас нет прав для загрузки документов. Используйте /request_access.")
                return

            # Проверяем, не обрабатывается ли уже файл пользователя
            if user_id in self.processing_users:
                await message.answer("⏳ Дождитесь завершения обработки предыдущего файла...")
                return

            document = message.document
            file_name = document.file_name
            file_size = document.file_size

            # Проверки файла
            if file_size > 20 * 1024 * 1024:  # 20 МБ
                await message.answer("❌ Размер файла превышает 20 МБ. Загрузите файл меньшего размера.")
                return

            if not any(file_name.lower().endswith(ext) for ext in ['.pdf', '.zip', '.pptx']):
                await message.answer("❌ Поддерживаются только файлы: PDF, ZIP, PPTX")
                return

            # Добавляем пользователя в обработку
            self.processing_users.add(user_id)

            try:
                # Скачиваем файл
                file_info = await self.bot.get_file(document.file_id)

                # Создаем временный файл
                temp_dir = tempfile.gettempdir()
                temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file_name}")

                await self.bot.download_file(file_info.file_path, temp_file_path)

                # Сохраняем путь в Redis для использования в callback
                await self.set_user_temp_file_path(user_id, temp_file_path)

                telegram_logger.info(f"Файл {file_name} сохранен: {temp_file_path}")

                # Определяем тип файла
                if file_name.lower().endswith('.pptx'):
                    # Для презентаций сразу определяем тип
                    await self._process_presentation(message, temp_file_path, file_name)
                elif file_name.lower().endswith('.zip'):
                    # Для архивов показываем выбор типа
                    await self._show_document_type_selection(message, state, file_name, is_archive=True)
                else:
                    # Для PDF показываем выбор типа
                    await self._show_document_type_selection(message, state, file_name, is_archive=False)

            except Exception as e:
                logger.error(f"❌ Ошибка при загрузке файла: {e}")
                await message.answer("❌ Ошибка при загрузке файла. Попробуйте еще раз.")
            finally:
                # Убираем пользователя из обработки только при ошибке
                # При успешной загрузке убираем после обработки
                pass

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в handle_document_upload: {e}")
            await message.answer("❌ Критическая ошибка при обработке документа.")
            self.processing_users.discard(user_id)

    async def _show_document_type_selection(self, message: Message, state: FSMContext, file_name: str, is_archive: bool = False):
        """Показать выбор типа документа."""
        try:
            file_type = "архива" if is_archive else "документа"

            selection_text = f"""📄 **Выберите тип {file_type}**

📁 Файл: `{file_name}`

🔍 **Доступные типы:**
• **Регулятивный** - Законы, постановления, нормативы
• **Общий** - Договоры, письма, прочие документы

💡 **Совет:** Правильный выбор типа улучшает качество анализа."""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📜 Регулятивный документ",
                        callback_data=f"{DOC_TYPE_PREFIX}regulatory"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📄 Общий документ",
                        callback_data=f"{DOC_TYPE_PREFIX}general"
                    )
                ]
            ])

            await message.answer(selection_text, reply_markup=keyboard)
            await state.set_state(Form.selecting_document_type)

        except Exception as e:
            logger.error(f"❌ Ошибка в _show_document_type_selection: {e}")
            await message.answer("❌ Ошибка при отображении выбора типа документа.")

    async def handle_document_type_selection(self, callback_query: CallbackQuery, state: FSMContext):
        """Обработка выбора типа документа."""
        try:
            user_id = callback_query.from_user.id
            document_type = callback_query.data.replace(DOC_TYPE_PREFIX, "")

            telegram_logger.info(f"Выбран тип документа: {document_type} пользователем {user_id}")

            # Получаем путь к файлу из Redis
            temp_file_path = await self.get_user_temp_file_path(user_id)
            if not temp_file_path or not os.path.exists(temp_file_path):
                await callback_query.answer("❌ Файл не найден. Загрузите документ заново.")
                return

            original_filename = os.path.basename(temp_file_path).split('_', 1)[1]

            await callback_query.answer(f"✅ Выбран тип: {document_type}")
            await callback_query.message.edit_text(
                f"🔄 Обрабатываем файл `{original_filename}` как {document_type} документ...\n\n⏳ Это может занять несколько минут..."
            )

            # Определяем тип файла и обрабатываем
            if original_filename.lower().endswith('.zip'):
                await self._handle_archive_processing(callback_query.message, temp_file_path, original_filename, document_type)
            else:
                await self._handle_single_document_processing(callback_query.message, temp_file_path, original_filename, document_type)

            await state.clear()

        except Exception as e:
            logger.error(f"❌ Ошибка в handle_document_type_selection: {e}")
            await callback_query.answer("❌ Ошибка при обработке выбора.")

    async def _handle_archive_processing(self, message: Message, file_path: str, original_filename: str, document_type: str):
        """Обработка архива документов."""
        try:
            user_id = message.chat.id
            telegram_logger.info(f"Начинаем обработку архива {original_filename}")

            # Обрабатываем архив
            result = await self.process_document_via_api_gateway(
                file_path=file_path,
                original_filename=original_filename,
                document_type=document_type,
                is_presentation=False
            )

            if result.get('success', False):
                processed_files = result.get('processed_files', 0)
                skipped_files = result.get('skipped_files', 0)
                total_files = result.get('total_files', 0)
                processing_time = result.get('processing_time', 0)

                success_text = f"""✅ **Архив успешно обработан!**

📊 **Статистика обработки:**
• Всего файлов: {total_files}
• Обработано: {processed_files}
• Пропущено: {skipped_files}
• Время обработки: {processing_time:.1f} сек

📁 **Файл:** `{original_filename}`
🏷️ **Тип:** {document_type}

💬 **Теперь вы можете задавать вопросы по содержимому архива!**"""

                await message.edit_text(success_text)

                # Добавляем в историю
                if self.user_history:
                    await self.user_history.add_message(
                        user_id=user_id,
                        role="system",
                        content=f"Обработан архив {original_filename} ({processed_files} файлов)",
                        message_type="document"
                    )

            else:
                error_message = result.get('error', 'Неизвестная ошибка')
                await message.edit_text(f"❌ Ошибка при обработке архива: {error_message}")

        except Exception as e:
            logger.error(f"❌ Ошибка при обработке архива: {e}")
            await message.edit_text(f"❌ Ошибка при обработке архива: {str(e)}")
        finally:
            # Очищаем временный файл
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить временный файл {file_path}: {e}")

            # Убираем пользователя из обработки
            self.processing_users.discard(user_id)

    async def _handle_single_document_processing(self, message: Message, file_path: str, original_filename: str, document_type: str):
        """Обработка одного документа."""
        try:
            user_id = message.chat.id
            telegram_logger.info(f"Начинаем обработку документа {original_filename}")

            # Обрабатываем документ через API Gateway
            result = await self.process_document_via_api_gateway(
                file_path=file_path,
                original_filename=original_filename,
                document_type=document_type,
                is_presentation=False
            )

            if result.get('success', False):
                chunks_created = result.get('chunks_created', 0)
                processing_time = result.get('processing_time', 0)
                document_id = result.get('document_id', 'N/A')

                success_text = f"""✅ **Документ успешно обработан!**

📊 **Статистика обработки:**
• Создано фрагментов: {chunks_created}
• Время обработки: {processing_time:.1f} сек
• ID документа: {document_id}

📁 **Файл:** `{original_filename}`
🏷️ **Тип:** {document_type}

💬 **Теперь вы можете задавать вопросы по содержимому документа!**"""

                await message.edit_text(success_text)

                # Добавляем в историю
                if self.user_history:
                    await self.user_history.add_message(
                        user_id=user_id,
                        role="system",
                        content=f"Обработан документ {original_filename} ({chunks_created} фрагментов)",
                        message_type="document"
                    )

            else:
                error_message = result.get('error', 'Неизвестная ошибка')
                await message.edit_text(f"❌ Ошибка при обработке документа: {error_message}")

        except Exception as e:
            logger.error(f"❌ Ошибка при обработке документа: {e}")
            await message.edit_text(f"❌ Ошибка при обработке документа: {str(e)}")
        finally:
            # Очищаем временный файл
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить временный файл {file_path}: {e}")

            # Убираем пользователя из обработки
            self.processing_users.discard(user_id)

    async def _process_presentation(self, message: Message, file_path: str, original_filename: str):
        """Обработка презентации."""
        try:
            user_id = message.from_user.id
            telegram_logger.info(f"Обработка презентации {original_filename}")

            await message.answer(f"🔄 Обрабатываем презентацию `{original_filename}`...\n\n⏳ Это может занять несколько минут...")

            # Сканируем презентацию
            scan_result = await scan_presentation_for_bot(file_path, original_filename)

            if scan_result['success']:
                await message.answer(f"✅ Презентация `{original_filename}` успешно обработана!\n\n💬 Теперь вы можете задавать вопросы по её содержимому.")

                # Добавляем в историю
                if self.user_history:
                    await self.user_history.add_message(
                        user_id=user_id,
                        role="system",
                        content=f"Обработана презентация {original_filename}",
                        message_type="document"
                    )
            else:
                error_message = scan_result.get('error', 'Неизвестная ошибка')
                await message.answer(f"❌ Ошибка при обработке презентации: {error_message}")

        except Exception as e:
            logger.error(f"❌ Ошибка при обработке презентации: {e}")
            await message.answer(f"❌ Ошибка при обработке презентации: {str(e)}")
        finally:
            # Очищаем временный файл
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить временный файл {file_path}: {e}")

            # Убираем пользователя из обработки
            self.processing_users.discard(user_id)

    async def process_document_via_api_gateway(self, file_path: str, original_filename: str, document_type: str = "regulatory", is_presentation: bool = False) -> dict:
        """Обработка документа через API Gateway."""
        try:
            async with aiohttp.ClientSession() as session:
                # Читаем файл в память перед отправкой
                with open(file_path, 'rb') as f:
                    file_content = f.read()

                # Подготавливаем данные для отправки файла напрямую (НЕ путь!)
                data = aiohttp.FormData()
                data.add_field('file', file_content, filename=original_filename, content_type='application/pdf')
                data.add_field('original_filename', original_filename)
                data.add_field('category', document_type)  # API ожидает 'category', а не 'document_type'
                data.add_field('is_presentation', str(is_presentation).lower())

                # Отправляем запрос к API Gateway
                url = f"{self.api_gateway_url}/api/upload"

                async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ API Gateway response: {result}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ API Gateway error {response.status}: {error_text}")
                        return {
                            "success": False,
                            "error": f"API Gateway error: {response.status} - {error_text}"
                        }

        except asyncio.TimeoutError:
            logger.error("❌ API Gateway timeout")
            return {
                "success": False,
                "error": "API Gateway timeout"
            }
        except Exception as e:
            logger.error(f"❌ API Gateway request error: {e}")
            return {
                "success": False,
                "error": f"API Gateway request error: {str(e)}"
            }

    async def set_user_temp_file_path(self, user_id: int, file_path: str):
        """Сохранить путь к временному файлу пользователя в Redis."""
        try:
            if self.async_redis:
                key = f"user:{user_id}:temp_file_path"
                await self.async_redis.set(key, file_path, ex=3600)  # Сохраняем на 1 час
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пути файла в Redis: {e}")

    async def get_user_temp_file_path(self, user_id: int) -> str:
        """Получить путь к временному файлу пользователя из Redis."""
        try:
            if self.async_redis:
                key = f"user:{user_id}:temp_file_path"
                file_path = await self.async_redis.get(key)
                return file_path.decode() if file_path else None
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения пути файла из Redis: {e}")
            return None