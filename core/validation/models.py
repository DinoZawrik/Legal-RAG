"""
Validation models and enums (Context7 validated).

Pydantic v2 compliant data models for quality validation system.
Uses ConfigDict, Field, and proper type hints as per Context7 best practices.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ValidationSeverity(str, Enum):
    """Уровни серьезности проблем валидации"""
    CRITICAL = "critical"    # Критические ошибки (неверные правовые ссылки)
    HIGH = "high"           # Серьезные проблемы (неполнота анализа)
    MEDIUM = "medium"       # Умеренные проблемы (стилистические несоответствия)
    LOW = "low"            # Незначительные проблемы (мелкие недочеты)
    INFO = "info"          # Информационные сообщения


class ValidationCategory(str, Enum):
    """Категории валидации"""
    FACTUAL_ACCURACY = "factual_accuracy"        # Фактическая точность
    LEGAL_CORRECTNESS = "legal_correctness"      # Правовая корректность
    LOGICAL_CONSISTENCY = "logical_consistency"   # Логическая последовательность
    COMPLETENESS = "completeness"                # Полнота ответа
    RELEVANCE = "relevance"                      # Релевантность
    USER_ADAPTATION = "user_adaptation"          # Адаптация к пользователю
    FORMAL_REQUIREMENTS = "formal_requirements"   # Формальные требования
    SAFETY = "safety"                           # Безопасность советов


class ValidationIssue(BaseModel):
    """
    Проблема, выявленная при валидации.

    Context7 compliant: Uses Pydantic v2 ConfigDict and Field patterns.
    """
    model_config = ConfigDict(
        strict=True,
        validate_assignment=True,
        use_enum_values=False,  # Keep enum objects, not strings
        arbitrary_types_allowed=True  # Allow ResponseSection type
    )

    issue_id: str = Field(..., min_length=1, description="Unique issue identifier")
    category: ValidationCategory = Field(..., description="Validation category")
    severity: ValidationSeverity = Field(..., description="Issue severity level")
    title: str = Field(..., min_length=1, max_length=200, description="Issue title")
    description: str = Field(..., min_length=1, description="Detailed description")

    # Локализация проблемы
    section: Optional[Any] = Field(None, description="Response section with issue (ResponseSection)")
    text_excerpt: Optional[str] = Field(None, max_length=500, description="Text excerpt showing issue")
    line_number: Optional[int] = Field(None, ge=0, description="Line number in response")

    # Рекомендации по исправлению
    recommendations: List[str] = Field(
        default_factory=list,
        description="List of recommendations to fix issue"
    )
    auto_fix_available: bool = Field(False, description="Whether auto-fix is available")

    # Контекст
    affected_elements: List[str] = Field(
        default_factory=list,
        description="List of affected elements"
    )
    confidence: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in issue detection (0.0-1.0)"
    )


class ValidationReport(BaseModel):
    """
    Отчет о валидации ответа.

    Context7 compliant: Uses Pydantic v2 ConfigDict and Field patterns.
    """
    model_config = ConfigDict(
        strict=True,
        validate_assignment=True,
        use_enum_values=False,
        arbitrary_types_allowed=True  # Allow ResponseQuality type
    )

    response_id: str = Field(..., min_length=1, description="Unique response identifier")
    timestamp: datetime = Field(..., description="Validation timestamp")
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall quality score (0.0-1.0)"
    )
    quality_grade: Any = Field(..., description="Quality grade (ResponseQuality enum)")

    # Группировка проблем по категориям
    issues_by_category: Dict[ValidationCategory, List[ValidationIssue]] = Field(
        default_factory=dict,
        description="Issues grouped by category"
    )
    issues_by_severity: Dict[ValidationSeverity, List[ValidationIssue]] = Field(
        default_factory=dict,
        description="Issues grouped by severity"
    )

    # Статистика
    total_issues: int = Field(0, ge=0, description="Total number of issues")
    critical_issues: int = Field(0, ge=0, description="Number of critical issues")
    auto_fixable_issues: int = Field(0, ge=0, description="Number of auto-fixable issues")

    # Рекомендации
    priority_fixes: List[str] = Field(
        default_factory=list,
        description="Priority fixes to apply"
    )
    improvement_suggestions: List[str] = Field(
        default_factory=list,
        description="General improvement suggestions"
    )

    # Результаты специализированных проверок
    fact_check_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Fact checking results"
    )
    logic_validation: Dict[str, Any] = Field(
        default_factory=dict,
        description="Logic validation results"
    )
    compliance_check: Dict[str, Any] = Field(
        default_factory=dict,
        description="Compliance check results"
    )


__all__ = [
    "ValidationSeverity",
    "ValidationCategory",
    "ValidationIssue",
    "ValidationReport",
]
