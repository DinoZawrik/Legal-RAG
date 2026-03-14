from ..common import * # noqa: F401,F403
from ..errors import ProcessingPipelineError
from .extractors import (
    extract_doc_content,
    extract_enhanced_docx_content,
    extract_rtf_content,
    extract_spreadsheet_content,
)

class IngestionPipeline:
    """
    Основной pipeline для обработки и индексации документов.
    Объединяет функциональность из ingestion_pipeline.py
    """
    
    def __init__(self):
        self.llm = get_llm_client()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        self.vector_store = None
        
    async def initialize(self):
        """Инициализация pipeline."""
        try:
            # Vector store будет инициализирован асинхронно при первом использовании
            self.vector_store = None
            logger.info(" Ingestion pipeline инициализирован")
        except Exception as e:
            logger.error(f" Ошибка инициализации ingestion pipeline: {e}")
            raise ProcessingPipelineError(f"Initialization failed: {e}")
    
    def extract_text_from_file(self, file_path: Union[str, Path]) -> str:
        """Извлечение текста из различных типов файлов."""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        try:
            if extension == '.pdf':
                return extract_text_from_pdf(str(file_path))
            
            elif extension == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            elif extension == '.docx':
                return extract_enhanced_docx_content(file_path)

            elif extension == '.doc':
                return extract_doc_content(file_path)

            elif extension == '.rtf':
                return extract_rtf_content(file_path)

            elif extension in ['.xlsx', '.xls', '.csv']:
                return extract_spreadsheet_content(file_path, extension)
            
            else:
                raise ProcessingPipelineError(f"Unsupported file type: {extension}")
                
        except Exception as e:
            logger.error(f" Ошибка извлечения текста из {file_path}: {e}")
            raise ProcessingPipelineError(f"Text extraction failed: {e}")
    
    
    def create_chunks(self, text: str, metadata: Dict[str, Any] = None) -> List[TextChunk]:
        """Создание чанков из текста."""
        try:
            chunks = self.text_splitter.split_text(text)
            
            text_chunks = []
            for i, chunk_text in enumerate(chunks):
                chunk = TextChunk(
                    id=str(uuid.uuid4()),
                    text=chunk_text,
                    metadata={
                        **(metadata or {}),
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "chunk_type": "text"
                    }
                )
                text_chunks.append(chunk)
            
            logger.info(f" Создано {len(text_chunks)} текстовых чанков")
            return text_chunks
            
        except Exception as e:
            logger.error(f" Ошибка создания чанков: {e}")
            raise ProcessingPipelineError(f"Chunk creation failed: {e}")
    
    async def process_document(self, file_path: Union[str, Path], 
                             metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Полная обработка документа."""
        try:
            # Извлечение текста
            text = self.extract_text_from_file(file_path)
            
            if not text.strip():
                raise ProcessingPipelineError("Document contains no extractable text")
            
            # Создание чанков
            base_metadata = {
                "source_path": str(file_path),
                "file_name": Path(file_path).name,
                "processed_at": datetime.now().isoformat(),
                **(metadata or {})
            }
            
            chunks = self.create_chunks(text, base_metadata)
            
            # Инициализация vector store если нужно
            if not self.vector_store:
                await self.initialize()
            
            # Сохранение документа полностью (включая чанки в PostgreSQL, ChromaDB и Redis)
            # Сохранение документа в storage
            storage_result = None
            try:
                from core.storage_coordinator import create_storage_coordinator
                storage = await create_storage_coordinator()
                
                storage_result = await storage.store_document_complete(
                    file_path=str(file_path),
                    chunks=chunks,
                    metadata=base_metadata
                )
                
                if storage_result and storage_result.get('duplicate'):
                    logger.info(f" Документ '{Path(file_path).name}' уже существовал в системе")
                else:
                    logger.info(f" Документ '{Path(file_path).name}' полностью сохранен (PostgreSQL + ChromaDB + Redis)")
                
            except Exception as e:
                logger.warning(f" Не удалось сохранить документ: {e}")
            
            # Формирование результата с учетом дедупликации
            result = {
                "success": True,
                "file_path": str(file_path),
                "chunks_created": len(chunks),
                "total_characters": len(text),
                "metadata": base_metadata
            }
            
            # Добавляем информацию о дедупликации из storage_result
            if storage_result:
                result["document_id"] = storage_result.get("document_id")
                result["duplicate"] = storage_result.get("duplicate", False)
                result["file_hash"] = storage_result.get("file_hash")
                result["storage_locations"] = storage_result.get("storage_locations")
                
                if storage_result.get('duplicate'):
                    result["message"] = storage_result.get("message", "Документ является дубликатом")
            
            logger.info(f" Документ {Path(file_path).name} успешно обработан")
            return result
            
        except Exception as e:
            logger.error(f" Ошибка обработки документа {file_path}: {e}")
            return {
                "success": False,
                "file_path": str(file_path),
                "error": str(e)
            }


