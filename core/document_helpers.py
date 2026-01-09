"""
Helper functions to maintain backward compatibility for document processing.
"""

import asyncio
from typing import List, Dict, Any, Optional
from core.processing_pipeline import UnifiedDocumentProcessor
from core.redis_utils import get_task_status as get_redis_task_status, cancel_task_processing
from core.storage_coordinator import create_storage_coordinator

# --- Document Processing Status ---

def get_document_processing_status(task_id: str) -> str:
    """Gets the status of a document processing task."""
    return get_redis_task_status(task_id)

def cancel_document_processing(task_id: str) -> bool:
    """Cancels a document processing task."""
    return cancel_task_processing(task_id)

# --- Document Summaries and Information ---

async def get_documents_summary() -> List[Dict[str, Any]]:
    """Gets a summary of all general documents."""
    storage = await create_storage_coordinator()
    # This is a placeholder. The actual implementation should be in StorageCoordinator.
    try:
        return await storage.postgres.execute_query("SELECT * FROM documents")
    except Exception as e:
        print(f"Warning: PostgreSQL не доступен: {e}")
        return []  # Возвращаем пустой список если PostgreSQL недоступен

async def get_regulatory_documents_summary(industry_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Gets a summary of regulatory documents."""
    storage = await create_storage_coordinator()
    
    base_query = "SELECT * FROM regulatory_documents"
    params = {}
    
    if industry_filter:
        base_query += " WHERE industry = $1"
        params['industry'] = industry_filter
    
    try:
        return await storage.postgres.execute_query(base_query, params)
    except Exception as e:
        print(f"Warning: PostgreSQL не доступен: {e}")
        return []  # Возвращаем пустой список если PostgreSQL недоступен

async def get_available_industries() -> List[str]:
    """Gets a list of all available industries."""
    storage = await create_storage_coordinator()
    # This is a placeholder. The actual implementation should be in StorageCoordinator.
    try:
        results = await storage.postgres.execute_query(
            "SELECT DISTINCT extracted_data->>'industry' as industry FROM regulatory_documents"
        )
        return [row["industry"] for row in results if row["industry"]]
    except Exception as e:
        print(f"Warning: Не удалось получить список отраслей: {e}")
        return []  # Возвращаем пустой список если есть проблемы с БД

async def get_industries_with_counts() -> Dict[str, int]:
    """Gets a dictionary of industries with their document counts."""
    storage = await create_storage_coordinator()
    # This is a placeholder. The actual implementation should be in StorageCoordinator.
    results = await storage.postgres.execute_query(
        "SELECT extracted_data->>'industry' as industry, COUNT(*) as count FROM regulatory_documents GROUP BY industry"
    )
    return {row["industry"]: row["count"] for row in results if row["industry"]}


# --- Document Processing ---

async def run_regulatory_processing_for_file(file_path: str, task_id: Optional[str] = None) -> Dict[str, Any]:
    """Runs regulatory processing for a single file."""
    processor = UnifiedDocumentProcessor()
    await processor.initialize()
    return await processor.process_single_document(file_path, force_type=DocumentType.REGULATORY, task_id=task_id)

async def run_regulatory_pdf_processing(file_path: str, original_filename: str, task_id: Optional[str] = None) -> Dict[str, Any]:
    """Runs regulatory processing for a PDF file."""
    processor = UnifiedDocumentProcessor()
    await processor.initialize()
    metadata = {"original_filename": original_filename}
    return await processor.process_single_document(file_path, force_type=DocumentType.REGULATORY, metadata=metadata, task_id=task_id)

# --- Unified Processor Creation ---

async def create_unified_processor(file_path: str) -> Optional[Dict[str, Any]]:
    """Creates a unified processor and processes a single document."""
    processor = UnifiedDocumentProcessor()
    await processor.initialize()
    result = await processor.process_single_document(file_path)
    return result if result.get("success") else None

# --- Combined Summaries ---

async def get_combined_documents_summary() -> List[Dict[str, Any]]:
    """Gets a combined summary of all documents."""
    general_docs = await get_documents_summary()
    regulatory_docs = await get_regulatory_documents_summary()
    return general_docs + regulatory_docs