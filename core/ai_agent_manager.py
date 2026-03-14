#!/usr/bin/env python3
"""
AI Agent Manager
Менеджер для управления ИИ-агентами.

Включает функциональность:
- AgentManager: система управления агентами
- Регистрация и конфигурация агентов
- Управление диалогами и разговорами
- Очистка старых разговоров
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from core.ai_inference_core import EnhancedInferenceEngine

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Менеджер для управления ИИ-агентами.
    Упрощенная версия функциональности из agent.py
    """

    def __init__(self, inference_engine: EnhancedInferenceEngine):
        self.inference_engine = inference_engine
        self.agents = {}
        self.active_conversations = {}

    def register_agent(self, agent_id: str, agent_config: Dict[str, Any]):
        """Регистрация нового агента."""
        self.agents[agent_id] = {
            "id": agent_id,
            "name": agent_config.get("name", f"Agent-{agent_id}"),
            "system_prompt": agent_config.get("system_prompt", "default"),
            "capabilities": agent_config.get("capabilities", []),
            "created_at": datetime.now(),
            "conversation_count": 0
        }

        logger.info(f" Агент {agent_id} зарегистрирован")

    async def chat_with_agent(self, agent_id: str, message: str,
                            conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Общение с агентом."""
        try:
            if agent_id not in self.agents:
                return {
                    "success": False,
                    "error": f"Agent {agent_id} not found"
                }

            agent = self.agents[agent_id]

            # Создание или получение разговора
            if not conversation_id:
                conversation_id = str(uuid.uuid4())

            if conversation_id not in self.active_conversations:
                self.active_conversations[conversation_id] = {
                    "agent_id": agent_id,
                    "messages": [],
                    "created_at": datetime.now()
                }

            conversation = self.active_conversations[conversation_id]

            # Добавление сообщения в историю
            conversation["messages"].append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now()
            })

            # Генерация ответа
            response = await self.inference_engine.generate_response(
                prompt=message,
                system_prompt_key=agent["system_prompt"]
            )

            if response["success"]:
                # Добавление ответа в историю
                conversation["messages"].append({
                    "role": "assistant",
                    "content": response["response"],
                    "timestamp": datetime.now()
                })

                # Обновление счетчика разговоров
                agent["conversation_count"] += 1

            response.update({
                "agent_id": agent_id,
                "conversation_id": conversation_id,
                "agent_name": agent["name"]
            })

            return response

        except Exception as e:
            logger.error(f" Ошибка общения с агентом {agent_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_id": agent_id
            }

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса агента."""
        if agent_id in self.agents:
            agent = self.agents[agent_id].copy()
            agent["active_conversations"] = len([
                conv for conv in self.active_conversations.values()
                if conv["agent_id"] == agent_id
            ])
            return agent
        return None

    def list_agents(self) -> List[Dict[str, Any]]:
        """Список всех зарегистрированных агентов."""
        agents_list = []
        for agent_id, agent in self.agents.items():
            agent_info = agent.copy()
            agent_info["active_conversations"] = len([
                conv for conv in self.active_conversations.values()
                if conv["agent_id"] == agent_id
            ])
            agents_list.append(agent_info)
        return agents_list

    def get_conversation_history(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Получение истории разговора."""
        return self.active_conversations.get(conversation_id)

    def cleanup_conversations(self, max_age_hours: int = 24):
        """Очистка старых разговоров."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        to_remove = [
            conv_id for conv_id, conv in self.active_conversations.items()
            if conv["created_at"] < cutoff_time
        ]

        for conv_id in to_remove:
            del self.active_conversations[conv_id]

        logger.info(f" Очищено {len(to_remove)} старых разговоров")

    def get_manager_stats(self) -> Dict[str, Any]:
        """Статистика менеджера агентов."""
        total_conversations = sum(agent["conversation_count"] for agent in self.agents.values())
        active_conversations = len(self.active_conversations)

        return {
            "total_agents": len(self.agents),
            "active_conversations": active_conversations,
            "total_conversations": total_conversations,
            "agents": [
                {
                    "id": agent_id,
                    "name": agent["name"],
                    "conversation_count": agent["conversation_count"],
                    "capabilities": agent["capabilities"]
                }
                for agent_id, agent in self.agents.items()
            ]
        }