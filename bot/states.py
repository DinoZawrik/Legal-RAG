#!/usr/bin/env python3
"""
Telegram Bot States
FSM состояния для телеграм-бота.

Содержит определения состояний для конечного автомата (FSM)
при взаимодействии с пользователем через Telegram.
"""

from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    """Класс состояний для конечного автомата."""
    selecting_document_type = State()