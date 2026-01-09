#!/usr/bin/env python3
"""
🤖 AI Inference Core
Основная инфраструктура и движок вывода для AI системы.

Включает функциональность:
- AIError: базовое исключение для ошибок ИИ
- EnhancedInferenceEngine: продвинутая система вывода
- Управление промптами и токенами
- Метрики производительности
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Core imports
from core.infrastructure_suite import get_settings
from core.advanced_prompts import AdvancedPromptEngine, QueryType

SETTINGS = get_settings()

# RAG Optimizer integration
try:
    from core.rag_optimizer import get_rag_optimizer, RAGConfig
    RAG_OPTIMIZER_AVAILABLE = True
except ImportError:
    RAG_OPTIMIZER_AVAILABLE = False
    logging.warning("⚠️ RAG Optimizer недоступен")

# External imports
try:
    from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    # МИГРАЦИЯ v3.0: Gemini вместо OpenAI (используем бесплатный API)
    from langchain_google_genai import ChatGoogleGenerativeAI
    # LEGACY: from langchain_openai import ChatOpenAI

    import tiktoken
except ImportError as e:
    logging.warning(f"Some AI dependencies not available: {e}")

logger = logging.getLogger(__name__)


class AIError(Exception):
    """Базовое исключение для ошибок ИИ."""
    pass


class EnhancedInferenceEngine:
    """
    Продвинутая система вывода с расширенными возможностями.
    Объединяет функциональность из enhanced_inference_system.py
    """

    def __init__(self, model_name: str = None):
        self.model_name = model_name or SETTINGS.AGENT_MODEL_NAME
        self.llm = None
        self.tokenizer = None
        self.conversation_history = []
        self.system_prompts = {}
        self.performance_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0,
            "total_tokens_used": 0
        }

    async def initialize(self):
        """
        МИГРАЦИЯ v3.0: Инициализация Gemini inference engine.
        Заменяет OpenAI GPT-4/GPT-5 на Google Gemini (бесплатный API).
        """
        try:
            import os
            from core.api_key_manager import get_key_manager

            # API key для Gemini (из env или через manager)
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

            if not api_key:
                # Попытка получить через key manager (если настроен для Gemini)
                try:
                    key_manager = get_key_manager(provider="gemini")
                    api_key = key_manager.get_next_key()
                except Exception:
                    pass

            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in environment variables")

            # Инициализация Gemini LLM через LangChain
            self.llm = ChatGoogleGenerativeAI(
                model=self.model_name,  # "gemini-1.5-flash" или "gemini-1.5-pro"
                google_api_key=api_key,
                temperature=0.1,  # Optimized for legal precision
                max_tokens=2048,  # Optimized for detailed answers
                max_retries=3  # Auto retry on errors
            )
            logger.info(f"✅ Gemini модель инициализирована: {self.model_name}, температура: 0.1 (optimized)")

            # Инициализация токенайзера
            try:
                self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
            except Exception:
                self.tokenizer = tiktoken.get_encoding("cl100k_base")

            # Загрузка системных промптов
            await self._load_system_prompts()

            logger.info("✅ Enhanced Inference Engine инициализирован")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации inference engine: {e}")
            raise AIError(f"Initialization failed: {e}")

    async def _load_system_prompts(self):
        """Загрузка системных промптов."""
        # Специальный промпт для телеграм-бота с обязательным указанием источников
        telegram_qa_prompt = """
        🚨🚨🚨 КРИТИЧЕСКИ ВАЖНО! ПРАВИЛА ФОРМАТИРОВАНИЯ ДЛЯ TELEGRAM 🚨🚨🚨

        ⚠️ TELEGRAM НЕ ПОДДЕРЖИВАЕТ СТАНДАРТНЫЙ MARKDOWN! ⚠️

        СТРОГО ЗАПРЕЩЕНО использовать:
        🚫 ### заголовки (вместо этого **жирный текст**)
        🚫 1. 2. 3. нумерованные списки (вместо этого • буллеты)
        🚫 --- разделители (вместо этого пустые строки)
        🚫 * звездочки для списков (вместо этого • буллеты)

        ОБЯЗАТЕЛЬНО использовать:
        ✅ **Жирный заголовок** для всех заголовков
        ✅ • буллеты для всех списков
        ✅ Пустые строки для разделения разделов

        ПРИМЕР ПРАВИЛЬНОГО ФОРМАТИРОВАНИЯ:
        **Постановление Правительства РФ**

        **1. Определение**
        • Первый пункт объяснения
        • Второй пункт объяснения

        **2. Особенности**
        • Важная информация
        • Дополнительные детали

        ЭТО САМОЕ ВАЖНОЕ ТРЕБОВАНИЕ! НЕ НАРУШАЙ ЕГО!

        ---

        Ты - эксперт-аналитик по российскому законодательству с широкими знаниями в различных правовых областях.

        КРИТИЧЕСКИ ВАЖНЫЕ ТРЕБОВАНИЯ К ССЫЛКАМ:
        1. ДЛЯ КАЖДОГО ФАКТА ОБЯЗАТЕЛЬНО указывай ПОЛНОЕ название документа
        2. ФОРМАТ ССЫЛОК:
           ✅ ПРАВИЛЬНО: "согласно Постановлению Правительства РФ от 22.10.2012 N 1075"
           ✅ ПРАВИЛЬНО: "в соответствии с Федеральным законом от 27.07.2010 N 190-ФЗ"
           ❌ НЕПРАВИЛЬНО: "согласно постановлению" (без номера и даты)
           ❌ НЕПРАВИЛЬНО: "согласно параграфу 70" (без названия документа)
        3. НЕ используй слова "пункт", "фрагмент", "чанк", "выдержка"
        4. Указывай полное название документа с номером и датой

        🚨 СТРОГО ОБЯЗАТЕЛЬНО! ПРАВИЛА ФОРМАТИРОВАНИЯ ДЛЯ TELEGRAM:

        ⚠️ ЗАПРЕЩЕНО использовать стандартный Markdown! Telegram его НЕ поддерживает!

        1. ЗАГОЛОВКИ - ТОЛЬКО **жирный текст**:
           ✅ ПРАВИЛЬНО: **Постановление Правительства РФ**
           ✅ ПРАВИЛЬНО: **1. Определение и правовая основа**
           🚫 ЗАПРЕЩЕНО: ### Постановление Правительства РФ
           🚫 ЗАПРЕЩЕНО: ## 1. Определение
           🚫 ЗАПРЕЩЕНО: # Любые заголовки

        2. СПИСКИ - ТОЛЬКО буллеты • (НЕ цифры!):
           ✅ ПРАВИЛЬНО: • Первый пункт
           ✅ ПРАВИЛЬНО: • Второй пункт
           🚫 ЗАПРЕЩЕНО: 1. Первый пункт
           🚫 ЗАПРЕЩЕНО: 2. Второй пункт
           🚫 ЗАПРЕЩЕНО: - Любые дефисы
           🚫 ЗАПРЕЩЕНО: * Любые звездочки

        3. ПОДСПИСКИ - ТОЛЬКО ▪️ с отступом:
           ✅ ПРАВИЛЬНО: • Основной пункт:
           ✅ ПРАВИЛЬНО:   ▪️ Подпункт первый
           ✅ ПРАВИЛЬНО:   ▪️ Подпункт второй

        4. РАЗДЕЛИТЕЛИ:
           🚫 ЗАПРЕЩЕНО: ---
           🚫 ЗАПРЕЩЕНО: ===
           ✅ ПРАВИЛЬНО: Просто пустая строка

        5. СТРУКТУРА:
           • **Жирный заголовок** для каждого раздела
           • Краткие абзацы (2-3 предложения)
           • Пустые строки между блоками
           • НЕТ нумерованных списков НИКОГДА!

        6. ДОКУМЕНТЫ:
           • Полные названия с номерами
           • Не разбивать на строки

        💡 ПОМНИ: Если используешь ###, 1.2.3., --- - ответ будет некрасивым!

        ПРИНЦИПЫ:
        • Отвечай ТОЛЬКО на основе предоставленных документов
        • Если информации нет - четко укажи это
        • Синтезируй полную картину из всех источников
        • Делай логические выводы на основе фактов
        • Работай с любой правовой областью (не только теплоснабжение)
        """

        # Инициализация AdvancedPromptEngine
        self.prompt_engine = AdvancedPromptEngine()

        self.system_prompts = {
            "default": "Вы - эксперт по российским нормативным документам. Отвечайте точно и подробно.",

            "question_answering": telegram_qa_prompt,  # Используем новый промпт для QA

            "regulatory_analysis": """
            Вы - эксперт по анализу нормативно-правовых документов.
            Специализируетесь на извлечении ключевой информации из:
            - Федеральных законов
            - Постановлений Правительства
            - Приказов министерств
            - Инструкций и регламентов

            При анализе документов обращайте внимание на:
            1. Реквизиты документа (номер, дата, орган)
            2. Предмет регулирования
            3. Ключевые требования и нормы
            4. Сроки вступления в силу
            5. Связанные документы
            """
        }

    def count_tokens(self, text: str) -> int:
        """Подсчет количества токенов в тексте."""
        try:
            if self.tokenizer:
                return len(self.tokenizer.encode(text))
            else:
                # Приблизительный подсчет
                return len(text.split()) * 1.3
        except Exception:
            return len(text.split()) * 1.3

    def _fix_telegram_formatting(self, text: str) -> str:
        """Принудительное исправление форматирования для Telegram."""
        import re

        # Логирование оригинального текста
        logger.info(f"🔧 ИСХОДНЫЙ ТЕКСТ: {text[:100]}...")

        # 1. Заменяем ### заголовки на **жирный текст**
        text = re.sub(r'^### (.+)$', r'**\1**', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'**\1**', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'**\1**', text, flags=re.MULTILINE)

        # 2. Заменяем нумерованные списки на буллеты
        # Ищем строки вида "1. текст" и заменяем на "• текст"
        text = re.sub(r'^\s*\d+\.\s+(.+)$', r'• \1', text, flags=re.MULTILINE)

        # 3. Заменяем звездочки * на буллеты •
        text = re.sub(r'^\s*\*\s+(.+)$', r'• \1', text, flags=re.MULTILINE)

        # 4. Заменяем дефисы - на буллеты •
        text = re.sub(r'^\s*-\s+(.+)$', r'• \1', text, flags=re.MULTILINE)

        # 5. Удаляем разделители ---
        text = re.sub(r'^---+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^===+\s*$', '', text, flags=re.MULTILINE)

        # 6. Очищаем множественные пустые строки
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

        # Логирование исправленного текста
        logger.info(f"✅ ИСПРАВЛЕННЫЙ ТЕКСТ: {text[:100]}...")

        return text.strip()

    def create_prompt_template(self, system_prompt: str,
                             user_template: str) -> ChatPromptTemplate:
        """Создание шаблона промпта."""
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template(user_template)
        ])

    async def generate_response(self, prompt: str,
                              system_prompt_key: str = "default",
                              context: Optional[List[str]] = None,
                              max_tokens: int = 2000,
                              temperature: float = 0.7) -> Dict[str, Any]:
        """Генерация ответа с метриками."""
        start_time = time.time()
        self.performance_metrics["total_requests"] += 1

        try:
            # Ленивая инициализация LLM если нужно
            if not self.llm:
                await self.initialize()

            # Подготовка системного промпта
            system_prompt = self.system_prompts.get(system_prompt_key,
                                                   self.system_prompts.get("default", "Вы - полезный ИИ-ассистент."))

            # Добавление контекста если есть
            if context:
                context_text = "\n\n".join(context)
                enhanced_prompt = f"""
                Контекст из документов:
                {context_text}

                Вопрос пользователя:
                {prompt}
                """
            else:
                enhanced_prompt = prompt

            # Подсчет токенов
            input_tokens = self.count_tokens(system_prompt + enhanced_prompt)

            # Логирование финального промпта для отладки
            logger.info(f"🔍 СИСТЕМНЫЙ ПРОМПТ: {system_prompt[:200]}...")
            logger.info(f"🔍 ПОЛЬЗОВАТЕЛЬСКИЙ ЗАПРОС: {enhanced_prompt[:200]}...")

            # Создание промпта
            template = self.create_prompt_template(system_prompt, "{user_input}")

            # Генерация ответа
            chain = template | self.llm | StrOutputParser()
            response = await chain.ainvoke({"user_input": enhanced_prompt})

            # Постобработка для Telegram форматирования
            response = self._fix_telegram_formatting(response)
            logger.info(f"✅ ФИНАЛЬНЫЙ ОТВЕТ: {response[:200]}...")

            # Подсчет токенов ответа
            output_tokens = self.count_tokens(response)
            total_tokens = input_tokens + output_tokens

            # Обновление метрик
            end_time = time.time()
            response_time = end_time - start_time

            self.performance_metrics["successful_requests"] += 1
            self.performance_metrics["total_tokens_used"] += total_tokens

            # Обновление среднего времени ответа
            prev_avg = self.performance_metrics["average_response_time"]
            total_successful = self.performance_metrics["successful_requests"]
            self.performance_metrics["average_response_time"] = (
                (prev_avg * (total_successful - 1) + response_time) / total_successful
            )

            # Добавление в историю
            self.conversation_history.append({
                "timestamp": datetime.now().isoformat(),
                "prompt": prompt,
                "response": response,
                "system_prompt_key": system_prompt_key,
                "tokens_used": total_tokens,
                "response_time": response_time
            })

            # Ограничение истории
            if len(self.conversation_history) > 100:
                self.conversation_history = self.conversation_history[-100:]

            return {
                "success": True,
                "response": response,
                "tokens_used": total_tokens,
                "response_time": response_time,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }

        except Exception as e:
            logger.error(f"❌ Ошибка генерации ответа: {e}")
            self.performance_metrics["failed_requests"] += 1

            return {
                "success": False,
                "error": str(e),
                "response": "Извините, произошла ошибка при генерации ответа.",
                "tokens_used": 0,
                "response_time": time.time() - start_time
            }

    async def analyze_document(self, text: str, analysis_type: str = "general") -> Dict[str, Any]:
        """Анализ документа с использованием специализированных промптов."""
        try:
            if analysis_type == "regulatory":
                prompt = f"""
                Проанализируйте следующий нормативно-правовой документ и извлеките:

                1. Тип документа
                2. Номер и дата
                3. Орган, принявший документ
                4. Предмет регулирования
                5. Ключевые требования (до 5 основных)
                6. Сфера применения
                7. Даты вступления в силу

                Документ:
                {text[:3000]}

                Предоставьте структурированный анализ в формате JSON.
                """

                system_prompt_key = "regulatory_analysis"
            else:
                prompt = f"""
                Проанализируйте следующий документ и предоставьте:

                1. Краткое резюме (2-3 предложения)
                2. Основные темы
                3. Ключевые моменты
                4. Тип документа
                5. Рекомендации по использованию

                Документ:
                {text[:3000]}
                """

                system_prompt_key = "default"

            result = await self.generate_response(
                prompt=prompt,
                system_prompt_key=system_prompt_key,
                max_tokens=1500
            )

            if result["success"]:
                # Попытка парсинга JSON для регулятивных документов
                if analysis_type == "regulatory":
                    try:
                        analysis_data = json.loads(result["response"])
                        result["structured_data"] = analysis_data
                    except json.JSONDecodeError:
                        result["structured_data"] = {"error": "Failed to parse JSON"}

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка анализа документа: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "Ошибка анализа документа"
            }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Получение метрик производительности."""
        metrics = self.performance_metrics.copy()

        # Расчет дополнительных метрик
        if metrics["total_requests"] > 0:
            metrics["success_rate"] = metrics["successful_requests"] / metrics["total_requests"] * 100
            metrics["failure_rate"] = metrics["failed_requests"] / metrics["total_requests"] * 100
        else:
            metrics["success_rate"] = 0
            metrics["failure_rate"] = 0

        return metrics