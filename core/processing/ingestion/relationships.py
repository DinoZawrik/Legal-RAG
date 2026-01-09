"""Вспомогательные функции для построения связей между элементами презентаций."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from core.infrastructure_suite import ElementRelationship, PageLayout

logger = logging.getLogger(__name__)


def infer_spatial_relationships(elements_data: List[Dict], page_layout: Optional[PageLayout]) -> List[ElementRelationship]:
    relationships: List[ElementRelationship] = []
    if not page_layout or not page_layout.elements:
        return relationships

    element_positions = {}
    for elem in page_layout.elements:
        pos = elem.position
        if isinstance(pos, dict) and pos:
            element_positions[elem.element_id] = pos

    for elem_data in elements_data:
        elem_id = elem_data.get("element_id", "")
        elem_type = elem_data.get("type", "")

        if elem_id not in element_positions:
            continue

        pos = element_positions[elem_id]

        for other_elem in elements_data:
            other_id = other_elem.get("element_id", "")
            other_type = other_elem.get("type", "")

            if other_id == elem_id or other_id not in element_positions:
                continue

            other_pos = element_positions[other_id]

            if _are_spatially_related(pos, other_pos):
                rel_type = _determine_spatial_relationship_type(elem_type, other_type, pos, other_pos)
                if rel_type:
                    relationships.append(
                        ElementRelationship(
                            from_element=elem_id,
                            to_element=other_id,
                            relationship_type=rel_type,
                            confidence=0.6,
                            description=f"Spatial relationship detected: {elem_type} -> {other_type}",
                        )
                    )

    return relationships


def infer_content_relationships(elements_data: List[Dict]) -> List[ElementRelationship]:
    relationships: List[ElementRelationship] = []

    for i, elem1 in enumerate(elements_data):
        elem1_id = elem1.get("element_id", "")
        elem1_type = elem1.get("type", "")
        elem1_content = elem1.get("content", "")

        for elem2 in elements_data[i + 1 :]:
            elem2_id = elem2.get("element_id", "")
            elem2_type = elem2.get("type", "")
            elem2_content = elem2.get("content", "")

            rel_type = _determine_content_relationship(elem1_type, elem2_type, elem1_content, elem2_content)
            if rel_type:
                relationships.append(
                    ElementRelationship(
                        from_element=elem1_id,
                        to_element=elem2_id,
                        relationship_type=rel_type["type"],
                        confidence=rel_type["confidence"],
                        description=rel_type["description"],
                    )
                )

    return relationships


def infer_reference_relationships(elements_data: List[Dict]) -> List[ElementRelationship]:
    relationships: List[ElementRelationship] = []

    element_index: Dict[str, str] = {}
    for elem in elements_data:
        elem_id = elem.get("element_id", "")
        elem_type = (elem.get("type") or "").lower()
        if elem_type in {"table", "chart", "map"}:
            possible_refs = {
                elem_id.lower(),
                elem_type,
                f"{elem_type}_1",
                "table",
                "таблица",
                "tbl",
                "chart",
                "график",
                "diagram",
                "diagramma",
                "figure",
                "рисунок",
                "map",
                "карта",
            }
            for ref in possible_refs:
                element_index[ref] = elem_id

    for elem in elements_data:
        if (elem.get("type") or "").lower() != "text":
            continue

        content_raw = elem.get("content", "")
        if isinstance(content_raw, list):
            content = " ".join(str(item) for item in content_raw).lower()
        else:
            content = str(content_raw).lower()

        elem_id = elem.get("element_id", "")
        for ref_key, target_id in element_index.items():
            if ref_key in content and target_id != elem_id:
                relationships.append(
                    ElementRelationship(
                        from_element=elem_id,
                        to_element=target_id,
                        relationship_type="reference",
                        confidence=0.7,
                        description=f"Text references element {ref_key}",
                    )
                )

    return relationships


def deduplicate_relationships(relationships: List[ElementRelationship]) -> List[ElementRelationship]:
    unique: Dict[tuple[str, str, str], ElementRelationship] = {}
    for rel in relationships:
        key = (rel.from_element, rel.to_element, rel.relationship_type)
        if key not in unique or unique[key].confidence < rel.confidence:
            unique[key] = rel
    return list(unique.values())


def _determine_spatial_relationship_type(type1: str, type2: str, pos1: Dict, pos2: Dict) -> Optional[str]:
    if type1 == "table" and type2 == "chart":
        return "data_source"
    if type1 == "text" and type2 in {"table", "chart", "map"}:
        return "summary"
    if type1 in {"chart", "map"} and type2 == "text":
        return "supports"
    return "spatial_proximity"


def _determine_content_relationship(type1: str, type2: str, content1: Any, content2: Any) -> Optional[Dict[str, Any]]:
    if isinstance(content1, list):
        content1_lower = " ".join(str(item) for item in content1).lower()
    else:
        content1_lower = str(content1).lower()

    if isinstance(content2, list):
        content2_lower = " ".join(str(item) for item in content2).lower()
    else:
        content2_lower = str(content2).lower()

    if type1 == "table" and type2 == "chart":
        return {
            "type": "data_source",
            "confidence": 0.8,
            "description": "Table provides data for chart",
        }

    if type1 == "chart" and type2 == "text":
        return {
            "type": "supports",
            "confidence": 0.7,
            "description": "Chart is described by text",
        }

    common_numbers = _find_common_numbers(content1_lower, content2_lower)
    if len(common_numbers) >= 2:
        preview = ", ".join(common_numbers[:3])
        return {
            "type": "data_correlation",
            "confidence": 0.6,
            "description": f"Shared numerical references: {preview}",
        }

    return None


def _find_common_numbers(text1: str, text2: str) -> List[str]:
    numbers1 = set(re.findall(r"\d+(?:[.,]\d+)?", text1))
    numbers2 = set(re.findall(r"\d+(?:[.,]\d+)?", text2))
    return list(numbers1.intersection(numbers2))


def _are_spatially_related(pos1: Dict, pos2: Dict) -> bool:
    pos1_str = str(pos1).lower()
    pos2_str = str(pos2).lower()

    proximity_keywords = ["top", "bottom", "left", "right", "center", "upper", "lower"]
    shared_keywords = sum(1 for keyword in proximity_keywords if keyword in pos1_str and keyword in pos2_str)

    return shared_keywords >= 1


__all__ = [
    "deduplicate_relationships",
    "infer_content_relationships",
    "infer_reference_relationships",
    "infer_spatial_relationships",
]
