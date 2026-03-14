from .common import * # noqa: F401,F403
from .errors import ProcessingPipelineError
from .ingestion import IngestionPipeline
from .regulatory import RegulatoryPipeline

class UnifiedDocumentProcessor:
    """
    Объединенный процессор документов.
    Комбинирует ingestion и regulatory pipelines.
    """
    
    def __init__(self):
        # Используем настоящий LangGraph pipeline для контекстного извлечения
        # Избегаем циклического импорта - инициализируем позже
        self.contextual_pipeline = None
        self.ingestion_pipeline = IngestionPipeline() # Для обычных документов
        self.regulatory_pipeline = RegulatoryPipeline()
        self.processing_stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "start_time": None
        }
    
    async def initialize(self):
        """Инициализация всех pipeline."""
        await self.ingestion_pipeline.initialize()
        logger.info(" Unified document processor инициализирован")
    
    def detect_document_type(self, file_path: Union[str, Path], text: str = None, metadata: Dict[str, Any] = None) -> DocumentType:
        """Определение типа документа."""
        file_path = Path(file_path)
        filename = file_path.name.lower()
        
        # DEBUG: Логируем metadata для отладки
        logger.info(f" DEBUG: detect_document_type metadata = {metadata}")
        
        # Приоритет: проверяем metadata на is_presentation
        if metadata:
            is_presentation = metadata.get('is_presentation')
            presentation_supplement = metadata.get('presentation_supplement')
            logger.info(f" DEBUG: is_presentation = {is_presentation}, presentation_supplement = {presentation_supplement}")
            
            if is_presentation or presentation_supplement:
                logger.info(" DEBUG: Detected as PRESENTATION due to metadata")
                return DocumentType.PRESENTATION
        
        # Проверка по расширению файла для презентаций
        presentation_extensions = ['.ppt', '.pptx', '.pdf']
        if file_path.suffix.lower() in presentation_extensions:
            # Для PDF проверяем контекст - если это презентация
            if 'презентация' in filename or 'presentation' in filename:
                return DocumentType.PRESENTATION
        
        # Проверка по названию файла
        regulatory_keywords = [
            'закон', 'постановление', 'приказ', 'распоряжение', 
            'инструкция', 'правила', 'регламент', 'положение'
        ]
        
        if any(keyword in filename for keyword in regulatory_keywords):
            return DocumentType.REGULATORY
        
        # Проверка по содержимому (если доступно)
        if text:
            text_lower = text.lower()[:1000] # Первые 1000 символов
            if any(keyword in text_lower for keyword in regulatory_keywords):
                return DocumentType.REGULATORY
        
        # По умолчанию - обычный документ
        return DocumentType.GENERAL
    
    async def process_single_document(self, file_path: Union[str, Path], 
                                    force_type: Optional[DocumentType] = None,
                                    metadata: Dict[str, Any] = None,
                                    task_id: Optional[str] = None) -> Dict[str, Any]:
        """Обработка одного документа с автоматическим определением типа."""
        try:
            self.processing_stats["total_processed"] += 1
            
            # Определение типа документа
            doc_type = force_type or self.detect_document_type(file_path, metadata=metadata)
            
            result = {
                "file_path": str(file_path),
                "document_type": doc_type.value if hasattr(doc_type, 'value') else str(doc_type),
                "success": False,
                "processing_time": 0
            }
            
            start_time = datetime.now()
            
            if doc_type == DocumentType.REGULATORY:
                # Обработка как регулятивный документ
                regulatory_doc = await self.regulatory_pipeline.process_regulatory_document(
                    file_path, task_id, metadata
                )
                
                result.update({
                    "success": regulatory_doc.processing_status == "completed",
                    "regulatory_data": regulatory_doc.extracted_data.metadata,
                    "document_id": regulatory_doc.id
                })
                
                # Добавляем информацию о дедупликации для regulatory документов
                logger.info(f" DEBUG: regulatory_doc.id = {regulatory_doc.id}")
                logger.info(f" DEBUG: hasattr storage_result = {hasattr(regulatory_doc, 'storage_result')}")
                logger.info(f" DEBUG: storage_result value = {getattr(regulatory_doc, 'storage_result', None)}")
                
                if hasattr(regulatory_doc, 'storage_result') and regulatory_doc.storage_result:
                    storage_result = regulatory_doc.storage_result
                    result["duplicate"] = storage_result.get("duplicate", False)
                    result["file_hash"] = storage_result.get("file_hash")
                    result["message"] = storage_result.get("message", "")
                    if storage_result.get("duplicate"):
                        result["chunks_created"] = 0 # Для дубликатов чанки не создаются
                    else:
                        result["chunks_created"] = storage_result.get("chunks_stored", 0)
                
                logger.info(f" DEBUG: final result for regulatory = {result}")
                
            elif doc_type == DocumentType.PRESENTATION:
                # Обработка как презентация с контекстным извлечением
                logger.info(f" Обрабатываем презентацию через контекстный pipeline: {Path(file_path).name}")
                
                # Используем НАСТОЯЩИЙ LangGraph pipeline для презентаций
                from core.infrastructure_suite import IngestionState
                import uuid
                
                initial_state: IngestionState = {
                    "document_path": str(file_path),
                    "document_id": str(uuid.uuid4()),
                    "page_images": [],
                    "chunks_per_page": {},
                    "current_page_index": 0,
                    "current_page_image": None,
                    "current_page_markdown": None,
                    "current_page_json_data": [],
                    "current_validation_report": None,
                    "retry_attempts": 0,
                    "extracted_data": None,
                    "status": "initializing",
                    "error_message": None,
                    "cancel_requested": False,
                    "etalon_validation_score": 0.0,
                    "etalon_detailed_report": {},
                    "overall_accuracy_scores": [],
                    "context_quality_scores": []
                }
                
                contextual_result = self.contextual_pipeline.invoke(
                    initial_state, 
                    config={
                        "configurable": {"task_id": task_id or str(uuid.uuid4())[:8]},
                        "recursion_limit": 100
                    }
                )

                # Извлекаем РЕАЛЬНЫЕ данные из LangGraph результата
                if contextual_result is None:
                    logger.error(" LangGraph pipeline returned None")
                    contextual_data = {"error": "LangGraph pipeline returned None"}
                    chunks_created = 0
                else:
                    logger.info(f" LangGraph pipeline status: {contextual_result.get('status')}")
                    logger.info(f" DEBUG: contextual_result keys: {list(contextual_result.keys()) if isinstance(contextual_result, dict) else 'Not a dict'}")
                    
                    contextual_data = {}
                    chunks_created = 0
                
                if contextual_result and contextual_result.get("status") == "assembled":
                    logger.info(f" DEBUG: LangGraph завершился успешно, status='assembled'")
                    
                    # Извлекаем чанки из chunks_per_page
                    chunks_per_page = contextual_result.get("chunks_per_page", {})
                    all_chunks = []
                    
                    for page_num, page_chunks in chunks_per_page.items():
                        if isinstance(page_chunks, list):
                            all_chunks.extend(page_chunks)
                        logger.info(f" DEBUG: Страница {page_num}: {len(page_chunks) if isinstance(page_chunks, list) else 0} чанков")
                    
                    chunks_created = len(all_chunks)
                    logger.info(f" DEBUG: Получено {chunks_created} чанков из LangGraph")
                    
                    # Извлекаем contextual chunks из результата
                    contextual_chunks = []
                    total_elements = 0
                    total_relationships = 0
                    total_insights = 0
                    total_searchable_length = 0
                    
                    for chunk in all_chunks:
                        if hasattr(chunk, 'content') and hasattr(chunk.content, 'elements'):
                            # Это ContextualChunk
                            contextual_chunk = chunk.content
                            chunk_data = {
                                "slide_number": contextual_chunk.slide_number,
                                "slide_title": contextual_chunk.slide_title,
                                "slide_type": contextual_chunk.slide_type,
                                "elements": contextual_chunk.elements,
                                "relationships": contextual_chunk.relationships,
                                "key_insights": contextual_chunk.key_insights,
                                "searchable_text": contextual_chunk.searchable_text,
                                "context_summary": contextual_chunk.context_summary,
                                "metadata": contextual_chunk.metadata
                            }
                            contextual_chunks.append(chunk_data)
                            
                            total_elements += len(contextual_chunk.elements)
                            total_relationships += len(contextual_chunk.relationships)
                            total_insights += len(contextual_chunk.key_insights)
                            total_searchable_length += len(contextual_chunk.searchable_text)
                    
                    contextual_data = {
                        "contextual_chunks": contextual_chunks,
                        "total_elements": total_elements,
                        "total_relationships": total_relationships,
                        "total_insights": total_insights,
                        "total_searchable_length": total_searchable_length,
                        "processing_method": "Universal Contextual Extraction v2.0"
                    } if contextual_chunks else {}
                    
                    logger.info(f" Извлечено {len(contextual_chunks)} контекстных чанков с {total_searchable_length} символами текста")
                    
                    # КРИТИЧНО: Присваиваем ContextualChunk в основную переменную chunks для сохранения
                    chunks = all_chunks
                    logger.info(f" Переназначено {len(chunks)} ContextualChunk для основной системы сохранения")
                    
                    # Сохраняем chunks в векторную базу данных
                    try:
                        logger.info(f" DEBUG: Пытаемся сохранить {len(all_chunks)} чанков в ChromaDB")
                        vector_store = await create_vector_store()
                        logger.info(f" DEBUG: Vector store создан: {vector_store is not None}")
                        if vector_store and all_chunks:
                            # Преобразуем ContextualChunk в Document objects для ChromaDB
                            documents = []
                            document_id = contextual_result.get("document_id", str(uuid.uuid4()))
                            for chunk in all_chunks:
                                if hasattr(chunk, 'content') and hasattr(chunk.content, 'searchable_text'):
                                    contextual_chunk = chunk.content
                                    doc = {
                                        "page_content": contextual_chunk.searchable_text,
                                        "metadata": {
                                            "document_id": str(document_id),
                                            "chunk_id": getattr(chunk, 'id', str(uuid.uuid4())),
                                            "slide_number": contextual_chunk.slide_number,
                                            "slide_title": contextual_chunk.slide_title,
                                            "slide_type": contextual_chunk.slide_type,
                                            "elements_count": len(contextual_chunk.elements),
                                            "relationships_count": len(contextual_chunk.relationships),
                                            "source_filename": Path(file_path).name,
                                            "chunk_type": "contextual"
                                        }
                                    }
                                    documents.append(doc)
                            
                            logger.info(f" DEBUG: Создано {len(documents)} документов для сохранения")
                            if documents:
                                logger.info(f" DEBUG: Вызываем add_documents_to_vector_store с {len(documents)} документами")
                                result = await add_documents_to_vector_store(vector_store, documents)
                                logger.info(f" DEBUG: Результат сохранения: {result}")
                                logger.info(f" Сохранено {len(documents)} контекстных документов в ChromaDB")
                            
                    except Exception as storage_error:
                        logger.error(f" Ошибка сохранения в векторную базу: {storage_error}")
                    
                else:
                    error_msg = contextual_result.get('error_message') if contextual_result else 'LangGraph returned None'
                    logger.error(f" LangGraph pipeline failed: {error_msg}")
                    contextual_data = {"error": "LangGraph processing failed"}

                result.update({
                    "success": contextual_result and contextual_result.get("status") == "assembled",
                    "document_id": extracted_data.document_id if (contextual_result and contextual_result.get("extracted_data")) else str(uuid.uuid4()),
                    "duplicate": False, # LangGraph не обрабатывает дубликаты
                    "chunks_created": chunks_created,
                    "contextual_data": contextual_data,
                    "message": f"Presentation processed with {chunks_created} chunks created"
                })
                
                logger.info(f" DEBUG: final result for presentation = {result}")
                
            else:
                # Обработка как обычный документ
                ingestion_result = await self.ingestion_pipeline.process_document(
                    file_path, metadata
                )
                
                result.update(ingestion_result)
            
            # Подсчет времени
            processing_time = (datetime.now() - start_time).total_seconds()
            result["processing_time"] = processing_time
            
            if result["success"]:
                self.processing_stats["successful"] += 1
            else:
                self.processing_stats["failed"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f" Ошибка обработки документа {file_path}: {e}")
            self.processing_stats["failed"] += 1
            
            return {
                "file_path": str(file_path),
                "document_type": "unknown",
                "success": False,
                "error": str(e),
                "processing_time": 0
            }
    
    async def process_batch(self, file_paths: List[Union[str, Path]], 
                          concurrency: int = 3,
                          progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Пакетная обработка документов."""
        self.processing_stats["start_time"] = datetime.now()
        
        # Создание семафора для ограничения параллельности
        semaphore = asyncio.Semaphore(concurrency)
        
        async def process_with_semaphore(file_path):
            async with semaphore:
                return await self.process_single_document(file_path)
        
        # Обработка всех файлов
        tasks = [process_with_semaphore(fp) for fp in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обработка результатов
        successful_results = []
        failed_results = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_results.append({
                    "file_path": str(file_paths[i]),
                    "error": str(result)
                })
            elif result.get("success"):
                successful_results.append(result)
            else:
                failed_results.append(result)
            
            # Вызов callback для прогресса
            if progress_callback:
                progress_callback(i + 1, len(file_paths))
        
        processing_time = (datetime.now() - self.processing_stats["start_time"]).total_seconds()
        
        return {
            "total_files": len(file_paths),
            "successful": len(successful_results),
            "failed": len(failed_results),
            "processing_time": processing_time,
            "successful_results": successful_results,
            "failed_results": failed_results,
            "stats": self.processing_stats
        }


# Convenience functions для обратной совместимости
async def create_ingestion_pipeline() -> IngestionPipeline:
    """Создание ingestion pipeline."""
    pipeline = IngestionPipeline()
    await pipeline.initialize()
    return pipeline


async def process_regulatory_document(document_path: Union[str, Path], 
                                    task_id: Optional[str] = None) -> RegulatoryDocument:
    """Обработка регулятивного документа."""
    pipeline = RegulatoryPipeline()
    return await pipeline.process_regulatory_document(document_path, task_id)


async def create_unified_processor() -> UnifiedDocumentProcessor:
    """Создание объединенного процессора документов."""
    processor = UnifiedDocumentProcessor()
    await processor.initialize()
    return processor
