#!/usr/bin/env python3
"""
Общие типы и классы для графовой системы
Решает проблему циклических импортов между graph_legal_engine и neo4j_real_connection
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class GraphNode:
    """Узел в правовом графе"""
    id: str
    type: str  # Law, Article, Constraint, LegalConcept
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphRelation:
    """Связь в правовом графе"""
    from_node: str
    to_node: str
    relation_type: str  # CONTAINS, REFERENCES, APPLIES_TO, DIFFERS_FROM
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphContext:
    """Контекст из графовой базы данных"""
    central_node: 'GraphNode'
    related_nodes: List['GraphNode']
    relations: List['GraphRelation']
    traversal_depth: int
    confidence_score: float
