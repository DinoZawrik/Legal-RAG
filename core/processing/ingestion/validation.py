"""Helpers and nodes responsible for validation of contextual extraction."""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from core.infrastructure_suite import (
    ElementRelationship,
    IngestionState,
    ParsedPageTables,
    ValidationReport,
)
from core.processing.ingestion.llm import llm_json_parser, llm_structured, retry_with_key_rotation
from core.processing.ingestion.runtime import _check_cancel_requested
from core.ppp_presentation_prompts import create_ppp_enhanced_validator_prompt

logger = logging.getLogger(__name__)


def contextual_validator_node(state: IngestionState, config: dict) -> dict:
    task_id = config.get("configurable", {}).get("task_id")
    if _check_cancel_requested(task_id):
        logger.info("Contextual Validator: cancellation requested for task %s", task_id)
        return {"status": "cancelled"}

    contextual_chunk = state.get("contextual_data") or state.get("contextual_chunk")
    enhanced_relationships = state.get("enhanced_relationships", [])
    extracted_markdown = state["current_page_markdown"]
    page_number = state["current_page_index"] + 1

    try:
        validation_score, critique, suggestions = _validate_contextual_quality(
            contextual_chunk, enhanced_relationships, extracted_markdown, page_number
        )

        context_threshold = 0.85
        needs_retry = validation_score < context_threshold

        validation_report = ValidationReport(
            is_correct=not needs_retry,
            critique=f"Context quality: {validation_score:.1%}. " + critique,
            suggestions_for_retry=suggestions if needs_retry else None,
        )

        logger.info(
            "Contextual validator - page %d: quality %.1f%%",
            page_number,
            validation_score * 100,
        )

        context_scores = state.get("context_quality_scores", [])
        context_scores.append(validation_score)

        return {
            "current_validation_report": validation_report,
            "context_validation_score": validation_score,
            "context_quality_scores": context_scores,
            "validation_details": {
                "elements_count": len(contextual_chunk.elements) if contextual_chunk else 0,
                "relationships_count": len(enhanced_relationships),
                "context_summary_length": len(contextual_chunk.context_summary) if contextual_chunk else 0,
            },
            "status": "context_validated",
        }

    except Exception as exc:  # pragma: no cover - runtime safety
        logger.error("Contextual validator failed on page %d: %s", page_number, exc)
        return {"status": "failed", "error_message": str(exc)}


def supervisor_node(state: IngestionState, config: dict) -> dict:
    task_id = config.get("configurable", {}).get("task_id")
    if _check_cancel_requested(task_id):
        logger.info("Supervisor: cancellation requested for task %s", task_id)
        return {"status": "cancelled"}

    page_image_base64 = state["current_page_image"]
    extracted_markdown = state["current_page_markdown"]
    page_number = state["current_page_index"] + 1

    parser = PydanticOutputParser(pydantic_object=ValidationReport)
    prompt_template_text = create_ppp_enhanced_validator_prompt()
    prompt_template = f"""
{prompt_template_text}
{{extracted_markdown}}
{{format_instructions}}
"""

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["extracted_markdown"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    try:
        chain = prompt | llm_structured.with_structured_output(ValidationReport)
        logger.info("Supervisor: waiting 10s before LLM call (rate limiting)")
        time.sleep(10)
        report = retry_with_key_rotation(
            chain.invoke,
            {"extracted_markdown": extracted_markdown, "image": page_image_base64},
        )
        logger.info("Supervisor reviewed page %d. is_correct=%s", page_number, report.is_correct)
        return {"current_validation_report": report, "status": "validated"}

    except Exception as exc:  # pragma: no cover - runtime safety
        logger.error("Supervisor validation failed on page %d: %s", page_number, exc)
        return {"status": "failed", "error_message": str(exc)}


def json_parser_node(state: IngestionState, config: dict) -> dict:
    task_id = config.get("configurable", {}).get("task_id")
    if _check_cancel_requested(task_id):
        logger.info("JSON Parser: cancellation requested for task %s", task_id)
        return {"status": "cancelled"}

    extracted_markdown = state["current_page_markdown"]
    page_number = state["current_page_index"] + 1

    markdown_tables = re.findall(r"```markdown\n(.*?)\n```", extracted_markdown, re.DOTALL)
    if not markdown_tables:
        logger.info("JSON Parser: no markdown tables on page %d", page_number)
        return {"current_page_json_data": [], "status": "json_parsed"}

    parser = PydanticOutputParser(pydantic_object=ParsedPageTables)
    prompt_template = PromptTemplate(
        template="""You are a data transformation engine. Convert the provided markdown tables into a single valid JSON object.\n"
        "Assign sequential `table_id` values to each table.\n"
        "Respond with JSON only, no explanations.\n"
        "{format_instructions}\n"
        "Input markdown tables (separated by '---'):\n{markdown_input}\n""",
        input_variables=["markdown_input"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    combined_markdown = "\n---\n".join(markdown_tables)
    chain = prompt_template | llm_json_parser | parser

    try:
        logger.info("JSON Parser: waiting 10s before LLM call (rate limiting)")
        time.sleep(10)
        parsed_result = retry_with_key_rotation(chain.invoke, {"markdown_input": combined_markdown})
        json_list = [table.model_dump() for table in parsed_result.tables]
        logger.info("JSON Parser: parsed %d tables on page %d", len(json_list), page_number)
        return {"current_page_json_data": json_list, "status": "json_parsed"}

    except Exception as exc:  # pragma: no cover - runtime safety
        logger.error("JSON Parser failed on page %d: %s", page_number, exc)
        return {"current_page_json_data": [], "status": "json_parse_failed"}


def calculate_avg_quality(scores: List[float]) -> float:
    return sum(scores) / len(scores) if scores else 0.0


def detect_document_level_isolation(knowledge_graph: Dict) -> List[str]:
    warnings: List[str] = []
    for page in knowledge_graph["document_structure"].get("pages", []):
        elements = page.get("elements", [])
        relationships = page.get("relationships", [])

        if elements and not relationships:
            warnings.append(f"Page {page['page_number']}: all elements are isolated")

        element_ids = {elem.get("element_id") for elem in elements if elem.get("element_id")}
        connected_ids = set()
        for rel in relationships:
            connected_ids.add(rel.get("from"))
            connected_ids.add(rel.get("to"))

        isolated = element_ids - connected_ids
        if isolated:
            warnings.append(f"Page {page['page_number']}: isolated elements {list(isolated)}")

    return warnings


def _validate_contextual_quality(contextual_chunk, enhanced_relationships, extracted_markdown, page_number):
    scores: List[float] = []
    critique_parts: List[str] = []
    suggestions: List[str] = []

    elements_score = _validate_elements_quality(contextual_chunk)
    scores.append(elements_score)
    if elements_score < 0.7:
        critique_parts.append("Element extraction quality is low")
        suggestions.append("Improve identification and description of slide elements")

    relationships_score = _validate_relationships_quality(enhanced_relationships, contextual_chunk)
    scores.append(relationships_score)
    if relationships_score < 0.7:
        critique_parts.append("Relationships between elements are insufficient")
        suggestions.append("Increase logical connections between elements; avoid isolated data")

    context_summary_score = _validate_context_summary(contextual_chunk)
    scores.append(context_summary_score)
    if context_summary_score < 0.6:
        critique_parts.append("Context summary is weak")
        suggestions.append("Produce a richer summary highlighting key relationships")

    isolation_penalty = _check_for_isolated_elements(contextual_chunk, enhanced_relationships)
    if isolation_penalty > 0:
        scores.append(1.0 - isolation_penalty)
        critique_parts.append("CRITICAL: isolated elements detected without relationships")
        suggestions.append("Every element must have at least one connection")

    chunk_quality_score = _validate_chunk_structure(contextual_chunk)
    scores.append(chunk_quality_score)
    if chunk_quality_score < 0.8:
        critique_parts.append("Contextual chunk structure has issues")
        suggestions.append("Ensure all contextual fields are populated correctly")

    final_score = sum(scores) / len(scores) if scores else 0.0
    critique = " ".join(critique_parts) if critique_parts else "Context extraction looks good"
    suggestions_text = " ".join(suggestions) if suggestions else None
    return final_score, critique, suggestions_text


def _validate_elements_quality(contextual_chunk) -> float:
    if not contextual_chunk or not contextual_chunk.elements:
        return 0.0

    quality_score = 0.0
    total_elements = len(contextual_chunk.elements)

    for element in contextual_chunk.elements:
        element_score = 0.0
        if element.get("element_id"):
            element_score += 0.25
        if element.get("type"):
            element_score += 0.25
        if element.get("content"):
            element_score += 0.25
        if element.get("position"):
            element_score += 0.25

        quality_score += element_score

    return quality_score / total_elements if total_elements else 0.0


def _validate_relationships_quality(enhanced_relationships, contextual_chunk) -> float:
    if not contextual_chunk:
        return 0.0

    expected_relationships = max(len(contextual_chunk.elements) - 1, 1)
    actual_relationships = len(enhanced_relationships)

    if actual_relationships == 0:
        return 0.0

    coverage_score = min(actual_relationships / expected_relationships, 1.0)
    confidence_score = sum(rel.confidence for rel in enhanced_relationships) / actual_relationships
    return (coverage_score * 0.6) + (confidence_score * 0.4)


def _validate_context_summary(contextual_chunk) -> float:
    if not contextual_chunk or not contextual_chunk.context_summary:
        return 0.0

    summary = contextual_chunk.context_summary
    length_score = min(len(summary) / 300, 1.0)
    has_key_insights = 1.0 if contextual_chunk.key_insights else 0.5
    return (length_score * 0.5) + (has_key_insights * 0.5)


def _check_for_isolated_elements(contextual_chunk, enhanced_relationships) -> float:
    if not contextual_chunk or not contextual_chunk.elements:
        return 0.0

    element_ids = {elem.get("element_id") for elem in contextual_chunk.elements if elem.get("element_id")}
    connected_ids = set()
    for rel in enhanced_relationships:
        connected_ids.add(rel.from_element)
        connected_ids.add(rel.to_element)

    isolated = element_ids - connected_ids
    if not isolated:
        return 0.0

    isolation_ratio = len(isolated) / len(element_ids) if element_ids else 0.0
    return min(isolation_ratio, 1.0)


def _validate_chunk_structure(contextual_chunk) -> float:
    if not contextual_chunk:
        return 0.0

    required_fields = [
        contextual_chunk.elements,
        contextual_chunk.context_summary,
        contextual_chunk.slide_number,
        contextual_chunk.metadata,
    ]

    structure_score = sum(1 for field in required_fields if field) / len(required_fields)
    return float(structure_score)


__all__ = [
    "calculate_avg_quality",
    "contextual_validator_node",
    "detect_document_level_isolation",
    "json_parser_node",
    "supervisor_node",
]
