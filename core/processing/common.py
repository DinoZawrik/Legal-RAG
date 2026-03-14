#!/usr/bin/env python3
"""
Processing Pipeline Suite
Объединенный модуль для обработки документов и данных.

Включает функциональность из:
- ingestion_pipeline.py
- regulatory_pipeline.py 
- document_manager.py (частично)

Объединяет различные pipeline для обработки документов:
- Ingestion Pipeline: основная обработка документов
- Regulatory Pipeline: обработка регулятивных документов
- Document Management: управление жизненным циклом документов
"""

import asyncio
import logging
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import json

# Core imports
from core.infrastructure_suite import (
    DocumentType, 
    ExtractedData, 
    TextChunk,
    RegulatoryDocument,
    SystemUtilities
)
# Temporary imports until full migration
try:
    # Import from data_storage_suite instead of deprecated modules
    from core.data_storage_suite import create_vector_store
    from core.data_storage_suite import add_documents_to_vector_store
    from core.data_storage_suite import update_task_status
except ImportError:
    # Fallback to suite imports
    from core.data_storage_suite import VectorStoreManager
    
    async def add_documents_to_vector_store(vector_store, chunks):
        if hasattr(vector_store, 'add_documents'):
            result = vector_store.add_documents(chunks)
            # Если результат - корутина, ждем ее
            if hasattr(result, '__await__'):
                return await result
            return result
        else:
            # Create manager if needed
            manager = VectorStoreManager()
            await manager.initialize()
            return await manager.add_documents(chunks)
    
    def update_task_status(task_id, status, message, progress):
        # Simplified implementation for now
        logger.info(f"Task {task_id}: {status} - {message} ({progress}%)")
        pass

# Convenience functions
def get_llm_client():
    return SystemUtilities.get_llm_client()

def extract_text_from_pdf(file_path: str) -> str:
    return SystemUtilities.extract_text_from_pdf(file_path)

# External imports
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    import docx
    from openpyxl import load_workbook
except ImportError as e:
    logging.warning(f"Some optional dependencies not available: {e}")

logger = logging.getLogger(__name__)


