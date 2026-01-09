from typing import List, Dict, Optional, Any
from core.ai_inference_suite import UnifiedAISystem
from bot.text_formatters import enhanced_formatter
import logging

logger = logging.getLogger(__name__)


class TelegramAgentWrapper:
    def __init__(self):
        """Инициализация обертки для работы с новой AI системой."""
        self.ai_system = UnifiedAISystem()
        logger.info("✅ TelegramAgentWrapper инициализирован с UnifiedAISystem")

    async def process_question(
        self,
        question: str,
        chat_history: List[Dict[str, Any]] = None,
        document_ids: Optional[List[str]] = None,
        industry_filters: Optional[List[str]] = None,
        regulatory_doc_type: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> List[str]:
        """
        Обрабатывает вопрос пользователя с помощью новой AI системы.
        Принимает историю чата для поддержания контекста.
        Параметры:
            question: текст вопроса пользователя
            chat_history: список словарей с историей сообщений
            document_ids: список ID PDF документов для поиска
            industry_filters: список отраслей для фильтрации регуляторных документов
            regulatory_doc_type: тип регуляторного документа для фильтрации
            document_type: тип документов ('pdf', 'regulatory', или None для всех)
        """
        logger.info(f"🤔 AgentWrapper: Получен вопрос: {question}")
        logger.info(f"📄 AgentWrapper: Используемые document_ids: {document_ids}")
        logger.info(f"🏭 AgentWrapper: Фильтры отраслей: {industry_filters}")
        logger.info(f"📋 AgentWrapper: Тип регуляторного документа: {regulatory_doc_type}")
        logger.info(f"🔍 AgentWrapper: Тип документов: {document_type}")

        try:
            # Проверяем статус системы
            system_status = self.ai_system.get_system_status()
            if not system_status.get('initialized'):
                logger.error("❌ AI система не инициализирована")
                return ["⚠️ Система временно недоступна. Попробуйте позже."]

            # Формируем расширенный вопрос с контекстом истории чата
            enhanced_question = self._build_enhanced_question(question, chat_history)
            
            # Обрабатываем вопрос через новую систему
            logger.info("🔄 Отправка вопроса в AI систему...")
            result = await self.ai_system.process_question(enhanced_question)
            
            if not result.get('success', True):
                logger.error(f"❌ Ошибка обработки: {result.get('answer', 'Неизвестная ошибка')}")
                return ["⚠️ Произошла ошибка при обработке вопроса. Попробуйте переформулировать."]

            # Извлекаем ответ и источники
            answer = result.get('answer', 'Нет ответа')
            sources = result.get('sources', [])
            confidence = result.get('confidence', 0.0)
            context_used = result.get('context_used', False)

            logger.info(f"✅ Получен ответ. Уверенность: {confidence:.2f}, Контекст: {context_used}")
            logger.info(f"📚 Источников найдено: {len(sources)}")

            # Форматируем ответ для Telegram
            formatted_answer = enhanced_formatter.format_text(answer)

            # Добавляем источники если есть
            if sources:
                source_list = []
                for i, source in enumerate(sources[:5], 1):  # Максимум 5 источников
                    # Извлекаем имя файла с приоритетом original_filename
                    filename = source.get("filename")
                    if not filename:
                        metadata = source.get("metadata", {})
                        filename = metadata.get("original_filename") or metadata.get("filename") or metadata.get("file_name", "Неизвестный файл")

                    source_list.append(f"{i}. {filename}")

                sources_text = "\n".join(source_list)
                formatted_answer += f"\n\n📚 *Источники:*\n{sources_text}"

            # Формируем полный ответ
            full_response = formatted_answer

            # Проверяем длину и разбиваем на части если нужно
            message_parts = enhanced_formatter.split_long_message(full_response)

            return message_parts if message_parts else ["Пустой ответ от системы."]

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в AgentWrapper: {e}")
            return [f"⚠️ Произошла ошибка: {str(e)}"]

    def _build_enhanced_question(self, question: str, chat_history: List[Dict[str, Any]] = None) -> str:
        """Создает расширенный вопрос с учетом истории чата."""
        if not chat_history:
            return question
        
        # Берем последние 3 сообщения из истории для контекста
        context_messages = []
        for msg in chat_history[-6:]:  # Последние 3 диалога (6 сообщений)
            if msg["type"] == "human":
                context_messages.append(f"Пользователь: {msg['content']}")
            elif msg["type"] == "ai":
                context_messages.append(f"Ассистент: {msg['content'][:200]}...")  # Ограничиваем длину
        
        if context_messages:
            context = "\n".join(context_messages)
            return f"Контекст предыдущих сообщений:\n{context}\n\nТекущий вопрос: {question}"
        
        return question
