from ..common import *  # noqa: F401,F403
from ..errors import ProcessingPipelineError
from .chunking import create_chunks as build_chunks
from .document_processing import (
    extract_regulatory_data,
    process_document,
    validate_extracted_data,
)
from .prompts import (
    build_extraction_prompt,
    build_presentation_aggregation_prompt,
    build_presentation_extraction_prompt,
    build_presentation_page_scanning_prompt,
    build_presentation_quality_check_prompt,
    build_presentation_retry_prompt,
    build_validation_prompt,
)

class RegulatoryPipeline:
    """
    Pipeline для обработки регулятивных документов.
    Объединяет функциональность из regulatory_pipeline.py
    """
    
    def __init__(self):
        self.llm = get_llm_client()
        self.extraction_prompt = build_extraction_prompt()
        self.validation_prompt = build_validation_prompt()
        self.presentation_extraction_prompt = build_presentation_extraction_prompt()
        self.presentation_page_scanning_prompt = build_presentation_page_scanning_prompt()
        self.presentation_quality_check_prompt = build_presentation_quality_check_prompt()
        self.presentation_retry_prompt = build_presentation_retry_prompt()
        self.presentation_aggregation_prompt = build_presentation_aggregation_prompt()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ".", " ", ""]
        )
    
    async def check_document_exists_by_filename(self, filename: str) -> Optional[str]:
        """Проверка существования документа по имени файла в PostgreSQL."""
        try:
            logger.info(f"🔍 Запрос к базе данных для файла: {filename}")
            from core.storage_coordinator import create_storage_coordinator
            storage = await create_storage_coordinator()
            
            async with storage.postgres.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id FROM documents WHERE filename = $1 AND document_type = 'regulatory'", 
                    filename
                )
                if row:
                    logger.info(f"✅ Найден существующий документ с ID: {row['id']}")
                    return str(row['id'])
                else:
                    logger.info(f"❌ Документ с именем '{filename}' не найден в базе")
                    return None
                
            
            logger.info(f"✅ Агрегация завершена: обработано {len(processed_pages)} страниц")
            return extracted_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка агрегации результатов: {e}")
            # Возвращаем минимальный результат
            return ExtractedData(
                document_type="presentation",
                document_number="",
                adoption_date="",
                issuing_authority="",
                summary=f"Ошибка агрегации: {e}",
                key_requirements=[],
                scope="",
                related_documents=[],
                metadata={
                    "error": str(e),
                    "pages_attempted": len(processed_pages)
                }
            )
    
    async def extract_regulatory_data(
        self, text: str, metadata: Optional[Dict] = None
    ) -> ExtractedData:
        return await extract_regulatory_data(self, text, metadata)

    async def validate_extracted_data(
        self, extracted_data: ExtractedData
    ) -> ExtractedData:
        return await validate_extracted_data(self, extracted_data)

    async def process_regulatory_document(
        self,
        document_path: Union[str, Path],
        task_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> RegulatoryDocument:
        return await process_document(self, document_path, task_id, metadata)

    def create_chunks(self, text: str, metadata: Dict[str, Any] = None) -> List[TextChunk]:
        return build_chunks(self, text, metadata or {})



