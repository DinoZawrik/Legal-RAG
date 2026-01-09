"""Nodes responsible for image preparation and layout analysis."""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from typing import Any, Dict

import fitz
from langchain_core.messages import HumanMessage

from core.infrastructure_suite import (
    ElementRelationship,
    IngestionState,
    PageLayout,
    SpatialElement,
)
from core.universal_presentation_prompts import create_layout_analyzer_prompt

from ..llm import llm_vision, retry_with_key_rotation
from ..runtime import _check_cancel_requested

logger = logging.getLogger(__name__)


def load_and_convert_to_images(state: IngestionState, config: dict) -> dict:
    task_id = config.get("configurable", {}).get("task_id")
    if _check_cancel_requested(task_id):
        logger.info("Load and Convert: Отмена обработки для задачи %s.", task_id)
        return {"status": "cancelled"}

    document_path = state["document_path"]
    try:
        doc = fitz.open(document_path)
        images_base64: list[str] = []
        for page in doc:
            if _check_cancel_requested(task_id):
                logger.info(
                    "Load and Convert: Отмена обработки страницы в процессе для задачи %s.",
                    task_id,
                )
                doc.close()
                return {"status": "cancelled"}
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
            images_base64.append(base64.b64encode(img_bytes).decode("utf-8"))
        doc.close()
        return {
            "page_images": images_base64,
            "current_page_index": 0,
            "current_page_image": images_base64[0] if images_base64 else None,
            "chunks_per_page": {},
            "status": "converted",
        }
    except Exception as exc:  # pragma: no cover - depends on file input
        logger.error("Failed to load and convert document %s to images: %s", document_path, exc)
        return {"status": "failed", "error_message": str(exc), "page_images": []}


def prepare_page_data(state: IngestionState, config: dict) -> dict:
    task_id = config.get("configurable", {}).get("task_id")
    if _check_cancel_requested(task_id):
        logger.info("Prepare Page Data: Отмена обработки для задачи %s.", task_id)
        return {"status": "cancelled"}

    page_index = state["current_page_index"]
    if page_index < len(state["page_images"]):
        return {"current_page_image": state["page_images"][page_index]}
    return {"current_page_image": None}


def layout_analyzer_node(state: IngestionState, config: dict) -> dict:
    task_id = config.get("configurable", {}).get("task_id")
    if _check_cancel_requested(task_id):
        logger.info("Layout Analyzer: Отмена обработки для задачи %s.", task_id)
        return {"status": "cancelled"}

    current_image = state.get("current_page_image")
    page_number = state.get("current_page_index", 0) + 1

    if not current_image:
        logger.warning("Layout Analyzer: Нет изображения для анализа на странице %d", page_number)
        return {"page_layout": None, "status": "no_image"}

    layout_prompt = create_layout_analyzer_prompt()

    try:
        message = HumanMessage(
            content=[
                {"type": "text", "text": layout_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{current_image}"}},
            ]
        )

        logger.info("Layout Analyzer: Ожидание 10 секунд перед AI запросом (rate limiting)")
        time.sleep(10)

        response = retry_with_key_rotation(llm_vision.invoke, [message])
        layout_text = response.content

        logger.info(
            "Layout Analyzer - страница %d: Получен анализ макета (%d символов)",
            page_number,
            len(layout_text),
        )

        page_layout = _parse_layout_response(layout_text, page_number)
        return {"page_layout": page_layout, "layout_analysis_raw": layout_text, "status": "layout_analyzed"}

    except Exception as exc:  # pragma: no cover - depends on external API
        logger.error("Layout Analyzer: Ошибка анализа макета страницы %d: %s", page_number, exc)
        return {"page_layout": None, "status": "error", "error": str(exc)}


def _parse_layout_response(layout_text: str, page_number: int) -> PageLayout:
    json_match = re.search(r"\{.*\}", layout_text, re.DOTALL)
    if json_match:
        try:
            layout_json = json.loads(json_match.group())
            return _build_layout_from_json(layout_json, page_number)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Layout Analyzer: Ошибка парсинга ответа: %s. Создаю fallback структуру", exc)

    return PageLayout(
        page_number=page_number,
        elements=[
            SpatialElement(
                element_id="content_1",
                element_type="mixed",
                position={"area": "full_page"},
                caption="Основное содержимое страницы",
                content_summary=layout_text[:200] + "..." if len(layout_text) > 200 else layout_text,
            )
        ],
        relationships=[],
        layout_type="mixed",
    )


def _build_layout_from_json(layout_json: Dict[str, Any], page_number: int) -> PageLayout:
    elements: list[SpatialElement] = []
    relationships: list[ElementRelationship] = []

    for elem_data in layout_json.get("elements", []):
        elements.append(
            SpatialElement(
                element_id=elem_data.get("element_id", f"elem_{len(elements)}"),
                element_type=elem_data.get("element_type", "unknown"),
                position=elem_data.get("position", {}),
                caption=elem_data.get("caption"),
                content_summary=elem_data.get("content_summary"),
            )
        )

    for rel_data in layout_json.get("relationships", []):
        relationships.append(
            ElementRelationship(
                from_element=rel_data.get("from_element", ""),
                to_element=rel_data.get("to_element", ""),
                relationship_type=rel_data.get("relationship_type", "related"),
                confidence=rel_data.get("confidence", 1.0),
                description=rel_data.get("description"),
            )
        )

    return PageLayout(
        page_number=page_number,
        elements=elements,
        relationships=relationships,
        layout_type=layout_json.get("layout_type", "mixed"),
    )


__all__ = ["layout_analyzer_node", "load_and_convert_to_images", "prepare_page_data"]
