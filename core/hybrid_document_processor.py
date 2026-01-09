#!/usr/bin/env python3
"""
🔄 Hybrid Document Processor
Интегрированная система обработки документов с автоматической индексацией в граф.

Процесс обработки:
1. Извлечение текста (как обычно)
2. Создание чанков (как обычно)
3. Сохранение в PostgreSQL + ChromaDB + Redis (как обычно)
4. 🆕 Извлечение правовых сущностей (Universal Legal NER)
5. 🆕 Создание графовых структур (Graph Document Extractor)
6. 🆕 Сохранение в Neo4j (Graph Database)

Решает проблему 32.5% ошибок через автоматическую индексацию в граф!
"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

# Core components
from core.processing_pipeline import IngestionPipeline
# MIGRATED: core.universal_legal_ner (deprecated) → core.ner
from core.ner import UniversalLegalNER
try:
    from core.ner.ner import LegalEntity, EntityType
except ImportError:
    LegalEntity = None
    EntityType = None
from core.graph_legal_engine import GraphNode, GraphRelation, GraphDocumentExtractor
from core.neo4j_real_connection import Neo4jRealConnection

logger = logging.getLogger(__name__)


class HybridDocumentProcessor:
    """
    Гибридный процессор документов с автоматической индексацией в граф.
    Объединяет традиционную обработку + графовую индексацию.
    """

    def __init__(self):
        # Традиционный pipeline
        self.ingestion_pipeline = IngestionPipeline()

        # Новые компоненты для графа
        self.legal_ner = UniversalLegalNER()
        self.graph_extractor = GraphDocumentExtractor()
        self.neo4j_connection = None

        # Конфигурация
        self.graph_enabled = True
        self.min_entities_for_graph = 3  # Минимум сущностей для создания графа

    async def initialize(self):
        """Инициализация всех компонентов"""
        # Инициализация традиционного pipeline
        await self.ingestion_pipeline.initialize()

        # Инициализация Neo4j если включен граф
        if self.graph_enabled:
            try:
                self.neo4j_connection = Neo4jRealConnection()
                connected = await self.neo4j_connection.connect()
                if connected:
                    logger.info("[SUCCESS] Neo4j connected for hybrid processing")
                else:
                    logger.warning("[WARNING] Neo4j connection failed - disabling graph processing")
                    self.graph_enabled = False
            except Exception as e:
                logger.warning(f"[WARNING] Neo4j initialization failed: {e} - disabling graph processing")
                self.graph_enabled = False

    async def process_document_hybrid(self, file_path: Union[str, Path],
                                    metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Полная гибридная обработка документа:
        1. Традиционная обработка (PostgreSQL + ChromaDB + Redis)
        2. Извлечение правовых сущностей
        3. Создание графовых структур
        4. Сохранение в Neo4j
        """

        try:
            # Шаг 1: Традиционная обработка документа
            logger.info(f"[STEP 1] Traditional processing: {Path(file_path).name}")
            traditional_result = await self.ingestion_pipeline.process_document(file_path, metadata)

            if not traditional_result.get("success"):
                return traditional_result

            # Проверяем на дубликат
            if traditional_result.get("duplicate"):
                logger.info(f"[INFO] Document is duplicate - skipping graph processing")
                return traditional_result

            # Шаг 2: Извлечение правовых сущностей (если граф включен)
            graph_result = {
                "graph_enabled": self.graph_enabled,
                "entities_extracted": 0,
                "graph_nodes_created": 0,
                "graph_relations_created": 0,
                "graph_processing_success": False
            }

            if self.graph_enabled and self.neo4j_connection:
                try:
                    # Извлекаем полный текст документа заново для NER
                    full_text = self.ingestion_pipeline.extract_text_from_file(file_path)

                    logger.info(f"[STEP 2] Legal entity extraction: {Path(file_path).name}")
                    entities_collection = self.legal_ner.extract_entities(full_text)
                    entities = entities_collection.get_all_entities()  # Получаем список всех сущностей
                    graph_result["entities_extracted"] = len(entities)

                    if len(entities) >= self.min_entities_for_graph:
                        # Шаг 3: Создание графовых структур
                        logger.info(f"[STEP 3] Graph structure creation: {len(entities)} entities found")

                        document_metadata = {
                            "document_id": traditional_result.get("document_id"),
                            "file_name": Path(file_path).name,
                            "file_path": str(file_path),
                            "processed_at": datetime.now().isoformat(),
                            **(metadata or {})
                        }

                        graph_nodes, graph_relations = await self._create_graph_structures(
                            entities, full_text, document_metadata
                        )

                        # Шаг 4: Сохранение в Neo4j
                        logger.info(f"[STEP 4] Neo4j indexing: {len(graph_nodes)} nodes, {len(graph_relations)} relations")

                        nodes_created = 0
                        relations_created = 0

                        # Создаем узлы
                        for node in graph_nodes:
                            try:
                                await self.neo4j_connection.create_node(node)
                                nodes_created += 1
                            except Exception as e:
                                logger.debug(f"Node creation skipped (may exist): {e}")

                        # Создаем связи
                        for relation in graph_relations:
                            try:
                                await self.neo4j_connection.create_relation(relation)
                                relations_created += 1
                            except Exception as e:
                                logger.debug(f"Relation creation skipped: {e}")

                        graph_result.update({
                            "graph_nodes_created": nodes_created,
                            "graph_relations_created": relations_created,
                            "graph_processing_success": True
                        })

                        logger.info(f"[SUCCESS] Graph processing completed: {nodes_created} nodes, {relations_created} relations")
                    else:
                        logger.info(f"[INFO] Not enough entities for graph ({len(entities)} < {self.min_entities_for_graph})")

                except Exception as e:
                    logger.error(f"[ERROR] Graph processing failed: {e}")
                    graph_result["graph_error"] = str(e)

            # Объединяем результаты
            hybrid_result = {**traditional_result, **graph_result}
            hybrid_result["processing_type"] = "hybrid"

            return hybrid_result

        except Exception as e:
            logger.error(f"[ERROR] Hybrid document processing failed: {e}")
            return {
                "success": False,
                "file_path": str(file_path),
                "error": str(e),
                "processing_type": "hybrid"
            }

    async def _create_graph_structures(self, entities: List[LegalEntity],
                                     full_text: str,
                                     document_metadata: Dict[str, Any]) -> tuple[List[GraphNode], List[GraphRelation]]:
        """Создание графовых структур из правовых сущностей"""

        nodes = []
        relations = []

        # Создаем основной узел документа
        doc_node = GraphNode(
            id=f"document_{document_metadata.get('document_id', uuid.uuid4())}",
            type="Document",
            properties={
                "title": document_metadata.get("file_name", ""),
                "file_path": document_metadata.get("file_path", ""),
                "processed_at": document_metadata.get("processed_at", ""),
                "total_entities": len(entities)
            }
        )
        nodes.append(doc_node)

        # Группируем сущности по типам
        entities_by_type = {}
        for entity in entities:
            entity_type = entity.entity_type.value
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)

        # Создаем узлы для каждого типа сущностей
        for entity_type, type_entities in entities_by_type.items():
            for i, entity in enumerate(type_entities):
                # Создаем узел сущности
                entity_node = GraphNode(
                    id=f"{entity_type}_{i}_{hash(entity.text) % 10000}",
                    type=self._map_entity_type_to_graph_type(entity.entity_type),
                    properties={
                        "text": entity.text,
                        "context": entity.context,
                        "confidence": entity.confidence,
                        "start_pos": entity.start_pos,
                        "end_pos": entity.end_pos,
                        "entity_type": entity_type,
                        **entity.metadata
                    }
                )
                nodes.append(entity_node)

                # Связываем с документом
                doc_relation = GraphRelation(
                    from_node=doc_node.id,
                    to_node=entity_node.id,
                    relation_type="CONTAINS",
                    properties={
                        "extraction_confidence": entity.confidence,
                        "position_in_text": entity.start_pos
                    }
                )
                relations.append(doc_relation)

        # Создаем связи между связанными сущностями
        self._create_entity_relations(entities, nodes, relations)

        return nodes, relations

    def _map_entity_type_to_graph_type(self, entity_type: EntityType) -> str:
        """Маппинг типов сущностей на типы графовых узлов"""
        mapping = {
            EntityType.NUMERICAL_CONSTRAINT: "Constraint",
            EntityType.TEMPORAL_CONSTRAINT: "TimeConstraint",
            EntityType.AUTHORITY_MODAL: "Authority",
            EntityType.CONDITIONAL_CLAUSE: "Condition",
            EntityType.DEFINITION_BLOCK: "Definition",
            EntityType.PROCEDURE_STEP: "Procedure",
            EntityType.DOCUMENT_REFERENCE: "Reference",
            EntityType.SCOPE_DELIMITER: "Scope",
            EntityType.ENFORCEMENT_MECHANISM: "Enforcement"
        }
        return mapping.get(entity_type, "Entity")

    def _create_entity_relations(self, entities: List[LegalEntity],
                               nodes: List[GraphNode],
                               relations: List[GraphRelation]):
        """Создание связей между сущностями на основе их взаимоотношений"""

        # Простая эвристика: связываем близкие по тексту сущности
        for i, entity1 in enumerate(entities):
            for j, entity2 in enumerate(entities[i+1:], i+1):
                # Если сущности близко в тексте (в пределах 200 символов)
                distance = abs(entity1.start_pos - entity2.start_pos)
                if distance < 200:
                    # Определяем тип связи
                    relation_type = self._determine_relation_type(entity1, entity2)
                    if relation_type:
                        # Находим соответствующие узлы
                        node1_id = f"{entity1.entity_type.value}_{i}_{hash(entity1.text) % 10000}"
                        node2_id = f"{entity2.entity_type.value}_{j}_{hash(entity2.text) % 10000}"

                        relation = GraphRelation(
                            from_node=node1_id,
                            to_node=node2_id,
                            relation_type=relation_type,
                            properties={
                                "text_distance": distance,
                                "confidence": (entity1.confidence + entity2.confidence) / 2
                            }
                        )
                        relations.append(relation)

    def _determine_relation_type(self, entity1: LegalEntity, entity2: LegalEntity) -> Optional[str]:
        """Определение типа связи между сущностями"""

        type1 = entity1.entity_type
        type2 = entity2.entity_type

        # Определяем связи на основе типов сущностей
        if type1 == EntityType.NUMERICAL_CONSTRAINT and type2 == EntityType.DEFINITION_BLOCK:
            return "APPLIES_TO"
        elif type1 == EntityType.DOCUMENT_REFERENCE and type2 == EntityType.NUMERICAL_CONSTRAINT:
            return "CONTAINS"
        elif type1 == EntityType.AUTHORITY_MODAL and type2 == EntityType.PROCEDURE_STEP:
            return "REQUIRES"
        elif type1 == EntityType.DEFINITION_BLOCK and type2 == EntityType.SCOPE_DELIMITER:
            return "SCOPED_BY"

        # По умолчанию - общая связь если типы совместимы
        compatible_pairs = [
            (EntityType.NUMERICAL_CONSTRAINT, EntityType.TEMPORAL_CONSTRAINT),
            (EntityType.DEFINITION_BLOCK, EntityType.CONDITIONAL_CLAUSE),
            (EntityType.AUTHORITY_MODAL, EntityType.ENFORCEMENT_MECHANISM)
        ]

        if (type1, type2) in compatible_pairs or (type2, type1) in compatible_pairs:
            return "RELATED_TO"

        return None

    async def migrate_existing_documents(self, limit: int = 10) -> Dict[str, Any]:
        """Миграция существующих документов в граф"""

        if not self.graph_enabled:
            return {"error": "Graph processing is disabled"}

        try:
            # Получаем список существующих документов из storage
            from core.storage_coordinator import create_storage_coordinator
            storage = await create_storage_coordinator()

            # Простой запрос существующих документов
            # Это нужно будет адаптировать под вашу структуру storage
            documents = await storage.get_recent_documents(limit=limit)

            migrated_count = 0
            total_nodes = 0
            total_relations = 0

            for doc in documents[:limit]:
                try:
                    file_path = doc.get("file_path") or doc.get("source_path")
                    if file_path and Path(file_path).exists():
                        logger.info(f"[MIGRATE] Processing: {Path(file_path).name}")

                        # Обрабатываем только графовую часть (традиционная уже сохранена)
                        full_text = self.ingestion_pipeline.extract_text_from_file(file_path)
                        entities_collection = self.legal_ner.extract_entities(full_text)
                        entities = entities_collection.get_all_entities()

                        if len(entities) >= self.min_entities_for_graph:
                            document_metadata = {
                                "document_id": doc.get("document_id"),
                                "file_name": Path(file_path).name,
                                "file_path": str(file_path),
                                "migrated_at": datetime.now().isoformat()
                            }

                            nodes, relations = await self._create_graph_structures(
                                entities, full_text, document_metadata
                            )

                            # Сохраняем в граф
                            for node in nodes:
                                try:
                                    await self.neo4j_connection.create_node(node)
                                    total_nodes += 1
                                except:
                                    pass

                            for relation in relations:
                                try:
                                    await self.neo4j_connection.create_relation(relation)
                                    total_relations += 1
                                except:
                                    pass

                            migrated_count += 1
                            logger.info(f"[SUCCESS] Migrated: {Path(file_path).name}")

                except Exception as e:
                    logger.error(f"[ERROR] Migration failed for document: {e}")

            return {
                "success": True,
                "migrated_documents": migrated_count,
                "total_nodes_created": total_nodes,
                "total_relations_created": total_relations
            }

        except Exception as e:
            logger.error(f"[ERROR] Migration process failed: {e}")
            return {"success": False, "error": str(e)}

    async def close(self):
        """Закрытие соединений"""
        if self.neo4j_connection:
            await self.neo4j_connection.close()


# Глобальный инстанс для использования в API
_hybrid_processor = None

async def get_hybrid_processor() -> HybridDocumentProcessor:
    """Получение глобального инстанса гибридного процессора"""
    global _hybrid_processor
    if _hybrid_processor is None:
        _hybrid_processor = HybridDocumentProcessor()
        await _hybrid_processor.initialize()
    return _hybrid_processor


# Convenience функции для совместимости
async def process_document_hybrid(file_path: Union[str, Path],
                                metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Удобная функция для гибридной обработки документа"""
    processor = await get_hybrid_processor()
    return await processor.process_document_hybrid(file_path, metadata)


async def migrate_existing_documents_to_graph(limit: int = 10) -> Dict[str, Any]:
    """Удобная функция для миграции существующих документов в граф"""
    processor = await get_hybrid_processor()
    return await processor.migrate_existing_documents(limit)


if __name__ == "__main__":
    # Тестирование гибридной обработки
    async def test_hybrid_processing():
        processor = HybridDocumentProcessor()
        await processor.initialize()

        # Тест на образце документа (если есть)
        test_files = [
            "test_document.pdf",
            "test_document.txt"
        ]

        for test_file in test_files:
            if Path(test_file).exists():
                print(f"Testing hybrid processing: {test_file}")
                result = await processor.process_document_hybrid(test_file)
                print(f"Result: {result}")
                break
        else:
            print("No test files found for testing")

        await processor.close()

    asyncio.run(test_hybrid_processing())