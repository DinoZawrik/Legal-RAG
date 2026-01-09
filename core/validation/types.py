"""
Базовые типы и модели для системы валидации качества правовых консультаций.
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from ..enhanced_response_generator import StructuredResponse, ResponseSection, ResponseQuality

class ValidationSeverity(Enum):
    """Уровни серьезности проблем валидации"""
    CRITICAL = "critical"    # Критические ошибки (неверные правовые ссылки)
    HIGH = "high"           # Серьезные проблемы (неполнота анализа)
    MEDIUM = "medium"       # Умеренные проблемы (стилистические несоответствия)
    LOW = "low"            # Незначительные проблемы (мелкие недочеты)
    INFO = "info"          # Информационные сообщения

class ValidationCategory(Enum):
    """Категории валидации"""
    FACTUAL_ACCURACY = "factual_accuracy"        # Фактическая точность
    LEGAL_CORRECTNESS = "legal_correctness"      # Правовая корректность
    LOGICAL_CONSISTENCY = "logical_consistency"   # Логическая последовательность
    COMPLETENESS = "completeness"                # Полнота ответа
    RELEVANCE = "relevance"                      # Релевантность
    USER_ADAPTATION = "user_adaptation"          # Адаптация к пользователю
    FORMAL_REQUIREMENTS = "formal_requirements"   # Формальные требования
    SAFETY = "safety"                           # Безопасность советов

@dataclass
class ValidationIssue:
    """Проблема, выявленная при валидации"""
    issue_id: str
    category: ValidationCategory
    severity: ValidationSeverity
    title: str
    description: str

    # Локализация проблемы
    section: Optional[ResponseSection] = None
    line_number: Optional[int] = None
    text_fragment: Optional[str] = None

    # Дополнительные данные
    suggestions: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationReport:
    """Отчет о валидации ответа"""
    response_id: str
    timestamp: datetime

    # Результаты валидации
    issues: List[ValidationIssue] = field(default_factory=list)
    overall_score: float = 0.0
    quality_grade: ResponseQuality = ResponseQuality.POOR

    # Группированные проблемы
    issues_by_category: Dict[ValidationCategory, List[ValidationIssue]] = field(default_factory=dict)
    issues_by_severity: Dict[ValidationSeverity, List[ValidationIssue]] = field(default_factory=dict)

    # Рекомендации
    priority_fixes: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)

    # Статистика
    validation_time_ms: float = 0.0
    total_checks_performed: int = 0
    error_occurred: bool = False
    error_message: Optional[str] = None

# Типы для удобства
ValidationRules = Dict[ValidationCategory, Dict[str, Any]]
LegalTermsSet = Set[str]
CommonMistakes = Dict[str, List[str]]
SafetyKeywords = Dict[str, List[str]]