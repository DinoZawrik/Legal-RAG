"""Вспомогательные функции для метрик и статистики промптов."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from .types import PromptTemplate, QueryType


def record_performance(
    history: List[Dict[str, Any]],
    templates: Dict[str, PromptTemplate],
    query_type: QueryType,
    prompt_name: str,
    success: bool,
    response_quality: float,
) -> None:
    history.append(
        {
            "timestamp": datetime.now().isoformat(),
            "query_type": query_type.value,
            "prompt_name": prompt_name,
            "success": success,
            "response_quality": response_quality,
        }
    )

    if prompt_name not in templates:
        return

    template = templates[prompt_name]
    if template.usage_count > 0:
        template.performance_score = template.performance_score * 0.8 + response_quality * 0.2
    else:
        template.performance_score = response_quality


def optimize_prompts(history: List[Dict[str, Any]], templates: Dict[str, PromptTemplate]) -> Dict[str, Any]:
    report = {
        "timestamp": datetime.now().isoformat(),
        "templates_analyzed": len(templates),
        "performance_records": len(history),
        "optimizations": [],
    }

    for query_type in QueryType:
        type_records = [record for record in history if record["query_type"] == query_type.value]
        if len(type_records) < 5:
            continue

        avg_quality = sum(r["response_quality"] for r in type_records) / len(type_records)
        success_rate = sum(1 for r in type_records if r["success"]) / len(type_records)

        if avg_quality < 0.7 or success_rate < 0.8:
            report["optimizations"].append(
                {
                    "query_type": query_type.value,
                    "issue": "low_performance",
                    "avg_quality": avg_quality,
                    "success_rate": success_rate,
                    "recommendation": "Consider prompt redesign",
                }
            )

    return report


def collect_stats(templates: Dict[str, PromptTemplate]) -> Dict[str, Any]:
    stats = {
        "total_templates": len(templates),
        "total_usage": sum(t.usage_count for t in templates.values()),
        "templates": {},
        "query_types": {},
    }

    for name, template in templates.items():
        stats["templates"][name] = {
            "usage_count": template.usage_count,
            "performance_score": template.performance_score,
            "query_type": template.query_type.value,
        }

    for query_type in QueryType:
        type_templates = [t for t in templates.values() if t.query_type == query_type]
        stats["query_types"][query_type.value] = {
            "templates_count": len(type_templates),
            "total_usage": sum(t.usage_count for t in type_templates),
            "avg_performance": sum(t.performance_score for t in type_templates) / len(type_templates)
            if type_templates
            else 0,
        }

    return stats


__all__ = ["collect_stats", "optimize_prompts", "record_performance"]
