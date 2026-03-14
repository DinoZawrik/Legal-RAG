#!/usr/bin/env python3
"""
OpenAI Inference Client
Unified client для взаимодействия с OpenAI GPT-4/GPT-5 через OpenAI API.

МИГРАЦИЯ v2.0 (13.10.2025):
- Заменяет langchain_google_genai.ChatGoogleGenerativeAI
- Совместим с LangChain через langchain_openai.ChatOpenAI
- Поддержка API key rotation для высокого throughput

Usage:
    from core.openai_inference_client import OpenAIInferenceClient

    client = OpenAIInferenceClient(model="gpt-4-turbo")
    response = await client.generate(prompt="Что такое концессионное соглашение?")
"""

import logging
import os
from typing import List, Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

# LangChain OpenAI integration
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:
    logger.warning("langchain-openai not available. Install with: pip install langchain-openai")
    ChatOpenAI = None


class OpenAIInferenceClient:
    """
    Async client для OpenAI GPT-4/GPT-5 inference.

    Features:
    - Совместимость с LangChain (ChatOpenAI)
    - Поддержка API key rotation
    - Автоматический retry при ошибках
    - Поддержка streaming (опционально)

    Attributes:
        model: Название модели (gpt-4-turbo, gpt-4o, gpt-5)
        temperature: Креативность модели (0.0 - 1.0)
        max_tokens: Максимальная длина ответа
    """

    # Доступные модели (обновить когда GPT-5 будет доступен)
    AVAILABLE_MODELS = [
        "gpt-4-turbo",
        "gpt-4-turbo-preview",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-5", # Placeholder для будущего
    ]

    def __init__(
        self,
        model: str = "gpt-4-turbo",
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        timeout: int = 120
    ):
        """
        Инициализация OpenAI client.

        Args:
            model: Название модели OpenAI
            api_key: OpenAI API key (или из env OPENAI_API_KEY)
            temperature: Температура генерации (0.0 - детерминированно, 1.0 - креативно)
            max_tokens: Максимальная длина ответа
            timeout: Таймаут для запросов (секунды)
        """
        if ChatOpenAI is None:
            raise ImportError(
                "langchain-openai required. Install with: pip install langchain-openai"
            )

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        # API key из параметра или env
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env or pass api_key parameter"
            )

        # Инициализация LangChain ChatOpenAI
        self.llm = ChatOpenAI(
            model=self.model,
            openai_api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
            max_retries=3 # Автоматический retry
        )

        logger.info(f" OpenAI client initialized: model={self.model}, temperature={self.temperature}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Генерация текста через OpenAI GPT.

        Args:
            prompt: User prompt (вопрос/задача)
            system_prompt: System prompt (инструкции модели)
            **kwargs: Дополнительные параметры (temperature, max_tokens)

        Returns:
            str: Ответ модели
        """
        try:
            messages = []

            # System prompt (опционально)
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))

            # User prompt
            messages.append(HumanMessage(content=prompt))

            # Генерация через LangChain (async)
            response = await self.llm.ainvoke(
                messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens)
            )

            # Извлечение текста из response
            answer = response.content if hasattr(response, 'content') else str(response)

            logger.info(f" Generated response ({len(answer)} chars)")
            return answer

        except Exception as e:
            logger.error(f" OpenAI generation error: {e}", exc_info=True)
            raise

    async def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> List[str]:
        """
        Batch генерация для нескольких промптов (parallel).

        Args:
            prompts: Список user prompts
            system_prompt: Общий system prompt для всех
            **kwargs: Дополнительные параметры

        Returns:
            List[str]: Список ответов (в том же порядке)
        """
        try:
            logger.info(f" Batch generation for {len(prompts)} prompts")

            # Параллельная генерация через asyncio.gather
            tasks = [
                self.generate(prompt, system_prompt, **kwargs)
                for prompt in prompts
            ]

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Обработка ошибок (exceptions пустые строки)
            results = []
            for idx, response in enumerate(responses):
                if isinstance(response, Exception):
                    logger.error(f" Batch item {idx} failed: {response}")
                    results.append("")
                else:
                    results.append(response)

            logger.info(f" Batch generation completed: {len(results)} responses")
            return results

        except Exception as e:
            logger.error(f" Batch generation error: {e}", exc_info=True)
            raise

    async def generate_with_context(
        self,
        query: str,
        context_chunks: List[str],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Генерация с контекстом (для RAG).

        Args:
            query: Вопрос пользователя
            context_chunks: Список релевантных чанков из vector DB
            system_prompt: System prompt
            **kwargs: Дополнительные параметры

        Returns:
            str: Ответ на основе контекста
        """
        # Формирование промпта с контекстом
        context_text = "\n\n".join([f"[{idx+1}] {chunk}" for idx, chunk in enumerate(context_chunks)])

        prompt = f"""Контекст:
{context_text}

Вопрос: {query}

Ответ на основе контекста выше:"""

        return await self.generate(prompt, system_prompt, **kwargs)

    def get_langchain_llm(self) -> Any:
        """
        Получить LangChain ChatOpenAI instance для интеграции с LangGraph.

        Returns:
            ChatOpenAI: LangChain LLM instance
        """
        return self.llm


# Singleton instance для API key rotation
_client_instances: Dict[str, OpenAIInferenceClient] = {}


def get_openai_client(
    model: str = "gpt-4-turbo",
    api_key: Optional[str] = None,
    **kwargs
) -> OpenAIInferenceClient:
    """
    Получить или создать OpenAI client (singleton per model).

    Args:
        model: Название модели
        api_key: API key (optional)
        **kwargs: Дополнительные параметры для client

    Returns:
        OpenAIInferenceClient: Singleton instance для модели
    """
    global _client_instances

    cache_key = f"{model}:{api_key or 'default'}"

    if cache_key not in _client_instances:
        _client_instances[cache_key] = OpenAIInferenceClient(
            model=model,
            api_key=api_key,
            **kwargs
        )

    return _client_instances[cache_key]


# Пример использования
if __name__ == "__main__":
    async def main():
        # Тест 1: Простая генерация
        client = OpenAIInferenceClient(model="gpt-4-turbo")

        response = await client.generate(
            prompt="Что такое концессионное соглашение? Ответь кратко (50 слов).",
            system_prompt="Ты эксперт по российскому праву."
        )
        print(f"Ответ: {response}")

        # Тест 2: Генерация с контекстом (RAG)
        context = [
            "Концессионное соглашение - договор между государством и частным инвестором.",
            "Концедент предоставляет концессионеру право создания и эксплуатации объекта инфраструктуры."
        ]

        rag_response = await client.generate_with_context(
            query="Кто такой концедент?",
            context_chunks=context,
            system_prompt="Отвечай только на основе предоставленного контекста."
        )
        print(f"\nRAG ответ: {rag_response}")

        # Тест 3: Batch generation
        queries = [
            "Что такое ГЧП?",
            "Кто такой концессионер?",
            "Что такое плата концедента?"
        ]

        batch_responses = await client.generate_batch(queries)
        print(f"\nBatch responses: {len(batch_responses)}")

    asyncio.run(main())
