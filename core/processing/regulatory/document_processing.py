"""High-level orchestration helpers for regulatory documents."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from langchain_core.output_parsers import StrOutputParser

from ..common import (
    ExtractedData,
    RegulatoryDocument,
    TextChunk,
    add_documents_to_vector_store,
    extract_text_from_pdf,
    logger,
    update_task_status,
)
from ..errors import ProcessingPipelineError
from .chunking import create_chunks
from .presentation import process_presentation_with_pages


async def process_document(
    pipeline: "RegulatoryPipeline",
    document_path: Union[str, Path],
    task_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> RegulatoryDocument:
    metadata = metadata.copy() if metadata else {}

    try:
        filename = metadata.get("original_filename") or Path(document_path).name
        logger.info("🔄 Начинаем обработку файла '%s'", filename)

        if task_id:
            update_task_status(task_id, "processing", "Начало обработки документа", 10)

        text = extract_text_from_pdf(str(document_path))
        if not text.strip():
            logger.warning("⚠️ PDF файл %s существует, но не содержит извлекаемого текста", filename)

        if task_id:
            update_task_status(task_id, "processing", "Текст извлечен", 30)

        metadata["file_path"] = document_path
        extracted_data = await extract_regulatory_data(pipeline, text, metadata)

        if task_id:
            update_task_status(task_id, "processing", "Данные извлечены", 60)

        validated_data = await validate_extracted_data(pipeline, extracted_data)

        if task_id:
            update_task_status(task_id, "processing", "Данные валидированы", 80)

        chunk_source_text = text
        if validated_data.document_type == "presentation":
            presentation_content = [validated_data.summary]
            presentation_content.extend(validated_data.key_requirements or [])
            chunk_source_text = "\n\n".join(filter(None, presentation_content)) or text

        chunk_metadata = {
            "document_type": validated_data.document_type,
            "document_number": validated_data.document_number,
            "source_document": filename,
            "processing_timestamp": datetime.utcnow().isoformat(),
            **metadata,
        }

        text_chunks = create_chunks(pipeline, chunk_source_text, chunk_metadata)

        if pipeline.vector_store is None and hasattr(pipeline, "vector_store"):
            from core.data_storage_suite import create_vector_store

            pipeline.vector_store = await create_vector_store()

        if pipeline.vector_store and text_chunks:
            await add_documents_to_vector_store(pipeline.vector_store, text_chunks)
            logger.info("✅ %s чанков добавлено в векторное хранилище", len(text_chunks))
        else:
            logger.warning("⚠️ Векторное хранилище недоступно или чанки отсутствуют")

        regulatory_document = RegulatoryDocument(
            raw_text=text,
            extracted_data=validated_data,
            metadata={
                "source_file": filename,
                "processed_at": datetime.utcnow().isoformat(),
                "chunk_count": len(text_chunks),
                **metadata,
            },
            chunks=text_chunks,
            processing_status="completed",
            created_at=datetime.utcnow(),
        )

        if task_id:
            update_task_status(task_id, "completed", "Документ обработан", 100)

        return regulatory_document

    except Exception as exc:
        logger.error("❌ Ошибка обработки %s: %s", document_path, exc)
        if task_id:
            update_task_status(task_id, "failed", f"Ошибка: {exc}", 100)

        return RegulatoryDocument(
            raw_text="",
            extracted_data=ExtractedData(
                document_type="unknown",
                document_number="",
                adoption_date="",
                issuing_authority="",
                summary=f"Ошибка обработки: {exc}",
                key_requirements=[],
                scope="",
                related_documents=[],
                metadata={"error": str(exc)},
            ),
            metadata={"error": str(exc)},
            chunks=[],
            processing_status="failed",
            created_at=datetime.utcnow(),
        )


async def extract_regulatory_data(
    pipeline: "RegulatoryPipeline", text: str, metadata: Optional[Dict[str, Any]] = None
) -> ExtractedData:
    try:
        metadata = metadata or {}
        is_presentation = metadata.get("is_presentation", False)

        if is_presentation:
            file_path = metadata.get("file_path") or metadata.get("source_path")
            if file_path:
                return await process_presentation_with_pages(pipeline, file_path, metadata)

            logger.warning("📊 Используется упрощенная обработка презентации - нет пути к файлу")
            extraction_chain = pipeline.presentation_extraction_prompt | pipeline.llm | StrOutputParser()
            extracted_text = await extraction_chain.ainvoke({"document_text": text[:4000]})
        else:
            extraction_chain = pipeline.extraction_prompt | pipeline.llm | StrOutputParser()
            extracted_text = await extraction_chain.ainvoke({"document_text": text[:4000]})

        extracted_json = _load_json(extracted_text)

        extracted_data = ExtractedData(
            document_type=extracted_json.get("document_type", "unknown"),
            document_number=extracted_json.get("document_number", ""),
            adoption_date=extracted_json.get("adoption_date", ""),
            issuing_authority=extracted_json.get("issuing_authority", ""),
            summary=extracted_json.get("summary", ""),
            key_requirements=extracted_json.get("key_requirements", []),
            scope=extracted_json.get("scope", ""),
            related_documents=extracted_json.get("related_documents", []),
            metadata=extracted_json,
        )

        logger.info("✅ Извлечены данные: %s", extracted_data.document_type)
        return extracted_data

    except Exception as exc:
        logger.error("❌ Ошибка извлечения регулятивных данных: %s", exc)
        return ExtractedData(
            document_type="unknown",
            document_number="",
            adoption_date="",
            issuing_authority="",
            summary="Ошибка извлечения данных",
            key_requirements=[],
            scope="",
            related_documents=[],
            metadata={"error": str(exc)},
        )


async def validate_extracted_data(
    pipeline: "RegulatoryPipeline", extracted_data: ExtractedData
) -> ExtractedData:
    try:
        validation_chain = pipeline.validation_prompt | pipeline.llm | StrOutputParser()
        data_text = json.dumps(extracted_data.metadata, ensure_ascii=False, indent=2)
        await validation_chain.ainvoke({"extracted_data": data_text})
        logger.info("✅ Данные прошли валидацию")
        return extracted_data

    except Exception as exc:
        logger.warning("⚠️ Ошибка валидации данных: %s", exc)
        return extracted_data


def _load_json(raw_text: str) -> Dict[str, Any]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        import re

        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise ProcessingPipelineError("Failed to parse extracted data as JSON")

__all__ = [
    "process_document",
    "extract_regulatory_data",
    "validate_extracted_data",
]
