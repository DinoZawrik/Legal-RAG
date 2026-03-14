"""Helpers for presentation-specific processing in regulatory pipeline."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List

from langchain_core.output_parsers import StrOutputParser

from ..common import logger
from ..errors import ProcessingPipelineError

if TYPE_CHECKING: # pragma: no cover - type hints only
    from .pipeline import ExtractedData, RegulatoryPipeline
else:
    ExtractedData = Any # type: ignore
    RegulatoryPipeline = Any # type: ignore


async def process_presentation_with_pages(
    pipeline: "RegulatoryPipeline",
    file_path: str,
    metadata: Dict[str, Any],
):
    from core.infrastructure_suite import SystemUtilities

    try:
        logger.info(" Начинаем сложную обработку презентации: %s", Path(file_path).name)
        start_time = datetime.now()

        pages = SystemUtilities.extract_text_from_pdf_pages(file_path)
        if pages:
            content_pages = [page for page in pages if page["has_content"]]
            logger.info(
                " Презентация содержит %s страниц, из них %s с содержимым",
                len(pages),
                len(content_pages),
            )

        if not pages:
            raise ProcessingPipelineError("Не удалось извлечь страницы из презентации")

        processed_pages: List[Dict[str, Any]] = []
        for page_info in pages:
            if not page_info["has_content"]:
                logger.debug(" Пропущена пустая страница %s", page_info["page_number"])
                continue

            page_result = await process_single_page(pipeline, page_info, metadata)
            processed_pages.append(page_result)
            await asyncio.sleep(5.0)

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        successful_pages = sum(
            1 for page in processed_pages if page["processing_status"] == "completed"
        )
        failed_pages = sum(
            1 for page in processed_pages if page["processing_status"] == "failed"
        )
        retries_count = sum(
            1
            for page in processed_pages
            if page.get("quality_check", {}).get("retry_needed", False)
        )

        logger.info(
            " Обработано %s страниц из %s за %.1fс",
            successful_pages,
            len(pages),
            processing_time,
        )
        logger.info(" Статистика: %s %s %s повторов", successful_pages, failed_pages, retries_count)

        final_result = await aggregate_page_results(pipeline, processed_pages, metadata)

        if hasattr(final_result, "metadata") and isinstance(final_result.metadata, dict):
            final_result.metadata.setdefault("processing_metrics", {}).update(
                {
                    "total_processing_time_seconds": processing_time,
                    "successful_pages": successful_pages,
                    "failed_pages": failed_pages,
                    "retries_performed": retries_count,
                    "processing_completed_at": end_time.isoformat(),
                }
            )

        return final_result

    except Exception as exc: # pragma: no cover - defensive logging
        logger.error(" Ошибка сложной обработки презентации: %s", exc)
        raise ProcessingPipelineError(f"Presentation processing failed: {exc}") from exc


async def process_single_page(
    pipeline: "RegulatoryPipeline",
    page_info: Dict[str, Any],
    metadata: Dict[str, Any],
):
    page_number = page_info["page_number"]
    total_pages = page_info["total_pages"]
    page_text = page_info["text"]

    logger.info(" Обработка страницы %s/%s", page_number, total_pages)

    scanning_chain = pipeline.presentation_page_scanning_prompt | pipeline.llm | StrOutputParser()

    try:
        extracted_text = await scanning_chain.ainvoke(
            {
                "page_number": page_number,
                "total_pages": total_pages,
                "page_text": page_text,
            }
        )
        extracted_data = _parse_json_response(extracted_text, page_number, "страницы")

        quality_result = await check_page_quality(pipeline, page_text, extracted_data, page_number)

        if quality_result.get("retry_needed", False):
            logger.info(" Повторное сканирование страницы %s", page_number)
            extracted_data = await retry_page_scanning(
                pipeline,
                page_info,
                quality_result.get("suggestions", ""),
            )

        return {
            "page_number": page_number,
            "total_pages": total_pages,
            "extracted_data": extracted_data,
            "quality_check": quality_result,
            "processing_status": "completed",
        }

    except Exception as exc:
        logger.error(" Ошибка обработки страницы %s: %s", page_number, exc)
        return {
            "page_number": page_number,
            "total_pages": total_pages,
            "extracted_data": {},
            "error": str(exc),
            "processing_status": "failed",
        }


async def check_page_quality(
    pipeline: "RegulatoryPipeline",
    page_text: str,
    extracted_data: Dict[str, Any],
    page_number: int,
):
    try:
        quality_chain = pipeline.presentation_quality_check_prompt | pipeline.llm | StrOutputParser()
        quality_text = await quality_chain.ainvoke(
            {
                "page_text": page_text[:2000],
                "extracted_data": json.dumps(extracted_data, ensure_ascii=False, indent=2),
            }
        )
        quality_result = _parse_json_response(quality_text, page_number, "проверки качества")

        quality_score = quality_result.get("quality_score", "НЕОПРЕДЕЛЕНО")
        retry_needed = quality_result.get("retry_needed", False)
        logger.info(
            " Качество страницы %s: %s (повтор: %s)",
            page_number,
            quality_score,
            retry_needed,
        )
        return quality_result

    except Exception as exc:
        logger.warning(" Ошибка проверки качества для страницы %s: %s", page_number, exc)
        return {
            "quality_score": "ОШИБКА",
            "retry_needed": False,
            "error": str(exc),
        }


async def retry_page_scanning(
    pipeline: "RegulatoryPipeline",
    page_info: Dict[str, Any],
    suggestions: str,
):
    try:
        retry_chain = pipeline.presentation_retry_prompt | pipeline.llm | StrOutputParser()
        extracted_text = await retry_chain.ainvoke(
            {
                "page_number": page_info["page_number"],
                "total_pages": page_info["total_pages"],
                "page_text": page_info["text"],
                "suggestions": suggestions,
            }
        )
        improved_data = _parse_json_response(
            extracted_text,
            page_info["page_number"],
            "повторного сканирования",
        )
        logger.info(
            " Повторное сканирование страницы %s завершено",
            page_info["page_number"],
        )
        return improved_data

    except Exception as exc:
        logger.error(" Ошибка повторного сканирования страницы %s: %s", page_info["page_number"], exc)
        return {"error": str(exc)}


async def aggregate_page_results(
    pipeline: "RegulatoryPipeline",
    processed_pages: Iterable[Dict[str, Any]],
    metadata: Dict[str, Any],
) -> "ExtractedData":
    try:
        processed_pages = list(processed_pages)
        logger.info(" Агрегация результатов %s страниц", len(processed_pages))

        aggregation_chain = pipeline.presentation_aggregation_prompt | pipeline.llm | StrOutputParser()
        aggregation_input = json.dumps(processed_pages, ensure_ascii=False, indent=2)
        aggregation_text = await aggregation_chain.ainvoke({"page_results": aggregation_input})

        aggregated_data = _parse_json_response(aggregation_text, 0, "агрегации страниц")

        return ExtractedData(
            document_type=metadata.get("document_type", "presentation"),
            source_document=metadata.get("source_document", "unknown"),
            metadata={
                **(metadata or {}),
                "pages_processed": len(processed_pages),
                "aggregation_timestamp": datetime.utcnow().isoformat(),
            },
            extracted_fields=aggregated_data,
        )

    except Exception as exc:
        logger.error(" Ошибка агрегации результатов презентации: %s", exc)
        raise ProcessingPipelineError(f"Presentation aggregation failed: {exc}") from exc


def _parse_json_response(response: str, page_number: int, context: str) -> Dict[str, Any]:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        import re

        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

        logger.warning(" Не удалось распарсить JSON для %s (%s)", context, page_number)
        return {"raw_response": response}


# Late import to avoid circular dependency in type hints
__all__ = [
    "process_presentation_with_pages",
    "process_single_page",
    "check_page_quality",
    "retry_page_scanning",
    "aggregate_page_results",
]
