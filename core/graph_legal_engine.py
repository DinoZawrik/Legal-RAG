#!/usr/bin/env python3
"""
🕸️ Graph Legal Intelligence Engine
Гибридная система: Neo4j (структура) + ChromaDB (семантика) + Universal Legal System (интеллект)

Решает критические проблемы:
- Потеря численных ограничений (80%, 3 года)
- Путаница между версиями законов и юрисдикциями
- Отсутствие точных ссылок на статьи
- Галлюцинации и общие ответы

Архитектура:
Neo4j: (:Law)-[:CONTAINS]->(:Article)-[:HAS]->(:Constraint)
ChromaDB: Семантический поиск содержания
Universal Legal System: Интеллектуальная обработка
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
import re

from core.graph_types import GraphNode, GraphRelation, GraphContext

# Реальный Neo4j через наш connection модуль
try:
    print("[DEBUG] Пытаемся импортировать neo4j_real_connection...")
    from core.neo4j_real_connection import Neo4jRealConnection, get_neo4j_connection
    NEO4J_REAL_AVAILABLE = True
    print("[DEBUG] Neo4j import successful! NEO4J_REAL_AVAILABLE = True")
except ImportError as e:
    print(f"[DEBUG] Neo4j import failed: {e}")
    NEO4J_REAL_AVAILABLE = False
    Neo4jRealConnection = None
    get_neo4j_connection = None
except Exception as e:
    print(f"[DEBUG] Unexpected Neo4j import error: {e}")
    import traceback
    traceback.print_exc()
    NEO4J_REAL_AVAILABLE = False
    Neo4jRealConnection = None
    get_neo4j_connection = None

# MIGRATED: core.universal_legal_ner (deprecated) → core.ner
from core.ner import UniversalLegalNER
try:
    from core.ner.ner import LegalEntity
except ImportError:
    LegalEntity = None
from core.universal_legal_system import UniversalLegalSystem, UniversalQueryResult

logger = logging.getLogger(__name__)




class GraphLegalOntology:
    """
    Правовая онтология для графовой базы данных
    Определяет типы узлов и связей в правовой системе
    """

    # Типы узлов
    NODE_TYPES = {
        "Law": {
            "properties": ["number", "title", "adoption_date", "status", "jurisdiction"],
            "description": "Федеральный закон, кодекс, подзаконный акт"
        },
        "Article": {
            "properties": ["number", "title", "law_reference", "content_hash"],
            "description": "Статья, пункт, часть закона"
        },
        "Constraint": {
            "properties": ["value", "type", "unit", "condition"],
            "description": "Численное ограничение, процент, срок"
        },
        "LegalConcept": {
            "properties": ["name", "definition", "category", "synonyms"],
            "description": "Правовое понятие, термин, институт"
        },
        "Procedure": {
            "properties": ["name", "steps", "duration", "requirements"],
            "description": "Правовая процедура, алгоритм действий"
        }
    }

    # Типы связей
    RELATION_TYPES = {
        "CONTAINS": "Закон содержит статью, статья содержит ограничение",
        "REFERENCES": "Статья ссылается на другую статью",
        "APPLIES_TO": "Ограничение применяется к понятию",
        "DEFINES": "Статья определяет понятие",
        "REGULATES": "Статья регулирует процедуру",
        "DIFFERS_FROM": "Закон отличается от другого закона",
        "SUPERSEDES": "Закон отменяет другой закон",
        "MODIFIES": "Закон изменяет другой закон",
        "REQUIRES": "Процедура требует выполнения условий",
        "CONTRADICTS": "Потенциальное противоречие между нормами"
    }


class MockNeo4jConnection:
    """
    Мок-соединение с Neo4j для разработки
    Будет заменено на реальное соединение при установке Neo4j
    """

    def __init__(self):
        self.nodes = {}  # id -> GraphNode
        self.relations = []  # List[GraphRelation]
        self.logger = logging.getLogger(self.__class__.__name__)

    async def create_node(self, node: GraphNode) -> str:
        """Создание узла в графе"""
        self.nodes[node.id] = node
        self.logger.debug(f"Created node {node.type}:{node.id}")
        return node.id

    async def create_relation(self, relation: GraphRelation) -> str:
        """Создание связи в графе"""
        self.relations.append(relation)
        self.logger.debug(f"Created relation {relation.from_node}-[{relation.relation_type}]->{relation.to_node}")
        return f"{relation.from_node}_{relation.relation_type}_{relation.to_node}"

    async def find_nodes(self, node_type: str = None, properties: Dict[str, Any] = None) -> List[GraphNode]:
        """Поиск узлов по типу и свойствам"""
        results = []
        for node in self.nodes.values():
            if node_type and node.type != node_type:
                continue
            if properties:
                if not all(node.properties.get(k) == v for k, v in properties.items()):
                    continue
            results.append(node)
        return results

    async def traverse(self, start_node_id: str, depth: int = 2) -> GraphContext:
        """Обход графа от узла на заданную глубину"""
        if start_node_id not in self.nodes:
            return GraphContext(None, [], [], 0, 0.0)

        central_node = self.nodes[start_node_id]
        related_nodes = []
        relevant_relations = []

        # Простой обход - найти все связанные узлы
        for relation in self.relations:
            if relation.from_node == start_node_id:
                if relation.to_node in self.nodes:
                    related_nodes.append(self.nodes[relation.to_node])
                    relevant_relations.append(relation)
            elif relation.to_node == start_node_id:
                if relation.from_node in self.nodes:
                    related_nodes.append(self.nodes[relation.from_node])
                    relevant_relations.append(relation)

        return GraphContext(
            central_node=central_node,
            related_nodes=related_nodes,
            relations=relevant_relations,
            traversal_depth=1,  # Упрощенно
            confidence_score=0.8 if related_nodes else 0.1
        )


class GraphDocumentExtractor:
    """
    Извлекает структурированные данные из правовых документов для графа
    Расширяет Universal Legal NER для создания узлов и связей
    """

    def __init__(self):
        self.ner_engine = UniversalLegalNER()
        self.ontology = GraphLegalOntology()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def extract_graph_structure(self, document: Dict[str, Any]) -> Tuple[List[GraphNode], List[GraphRelation]]:
        """Извлечение графовой структуры из документа"""

        content = document.get("content", "")
        metadata = document.get("metadata", {})

        nodes: List[GraphNode] = []
        relations: List[GraphRelation] = []

        try:
            law_node = await self._create_law_node(document)
            nodes.append(law_node)

            hierarchy_nodes, hierarchy_relations = await self._extract_hierarchy_nodes(document, law_node.id)
            nodes.extend(hierarchy_nodes)
            relations.extend(hierarchy_relations)

            entities = self.ner_engine.extract_entities(content)

            constraint_nodes = await self._extract_constraint_nodes(entities, law_node.id)
            concept_nodes = await self._extract_concept_nodes(entities, law_node.id)
            nodes.extend(constraint_nodes)
            nodes.extend(concept_nodes)

            extracted_relations = await self._extract_relations(nodes, entities, content)
            relations.extend(extracted_relations)

            self.logger.info(
                "Extracted %s nodes, %s relations from document",
                len(nodes),
                len(relations),
            )

        except Exception as e:
            self.logger.error(f"Error extracting graph structure: {e}")

        return nodes, relations

    async def _create_law_node(self, document: Dict[str, Any]) -> GraphNode:
        metadata = document.get("metadata", {})

        law_number = metadata.get("document_number", "")
        if not law_number:
            content = document.get("content", "")
            law_match = re.search(r'N\s*(\d+-[А-Я]+)', content)
            if law_match:
                law_number = law_match.group(1)

        return GraphNode(
            id=f"law_{law_number}_{metadata.get('document_id', 'unknown')}",
            type="Law",
            properties={
                "number": law_number,
                "title": metadata.get("title", ""),
                "adoption_date": metadata.get("adoption_date", ""),
                "document_id": metadata.get("document_id", ""),
                "document_type": metadata.get("document_type", "federal_law"),
            },
        )

    async def _extract_hierarchy_nodes(
        self,
        document: Dict[str, Any],
        law_id: str,
    ) -> Tuple[List[GraphNode], List[GraphRelation]]:
        nodes: List[GraphNode] = []
        relations: List[GraphRelation] = []

        hierarchy = document.get("hierarchy_chunks") or document.get("chunks") or []
        if not hierarchy:
            return nodes, relations

        def _make_node_id(prefix: str, *args: str) -> str:
            sanitized = [str(arg).replace(" ", "_") for arg in args if arg]
            return "_".join([prefix, *sanitized])

        for chunk in hierarchy:
            properties = chunk.get("metadata", {})
            chunk_text = chunk.get("text") or chunk.get("content", "")

            hierarchy_path = properties.get("hierarchy_path")
            if isinstance(hierarchy_path, str):
                path_segments = hierarchy_path.split("|")
            elif isinstance(hierarchy_path, list):
                path_segments = hierarchy_path
            else:
                path_segments = []

            section_number = properties.get("section_number")
            chapter_number = properties.get("chapter_number")
            article_number = properties.get("article_number")
            part_number = properties.get("part_number")
            point_number = properties.get("point_number")
            subpoint_number = properties.get("subpoint_number")

            section_id = chapter_id = article_id = part_id = point_id = subpoint_id = None

            if section_number:
                section_id = _make_node_id("section", law_id, section_number)
                nodes.append(
                    GraphNode(
                        id=section_id,
                        type="Section",
                        properties={
                            "number": section_number,
                            "title": properties.get("section_title", ""),
                            "law_reference": law_id,
                        },
                    )
                )
                relations.append(
                    GraphRelation(
                        from_node=law_id,
                        to_node=section_id,
                        relation_type="CONTAINS",
                    )
                )

            if chapter_number:
                chapter_id = _make_node_id("chapter", law_id, section_number or "", chapter_number)
                nodes.append(
                    GraphNode(
                        id=chapter_id,
                        type="Chapter",
                        properties={
                            "number": chapter_number,
                            "title": properties.get("chapter_title", ""),
                            "law_reference": law_id,
                            "section": section_number,
                        },
                    )
                )
                parent = chapter_id
                if section_id:
                    relations.append(
                        GraphRelation(
                            from_node=section_id,
                            to_node=chapter_id,
                            relation_type="CONTAINS",
                        )
                    )
                else:
                    relations.append(
                        GraphRelation(
                            from_node=law_id,
                            to_node=chapter_id,
                            relation_type="CONTAINS",
                        )
                    )

            if article_number:
                article_id = _make_node_id("article", law_id, article_number)
                nodes.append(
                    GraphNode(
                        id=article_id,
                        type="Article",
                        properties={
                            "number": article_number,
                            "law_reference": law_id,
                            "section": section_number,
                            "chapter": chapter_number,
                            "title": properties.get("article_title", ""),
                            "content": chunk_text[:2000],
                        },
                    )
                )
                parent = chapter_id or section_id or law_id
                relations.append(
                    GraphRelation(
                        from_node=parent,
                        to_node=article_id,
                        relation_type="CONTAINS",
                    )
                )

            if part_number:
                part_id = _make_node_id("part", law_id, article_number or "", part_number)
                nodes.append(
                    GraphNode(
                        id=part_id,
                        type="Part",
                        properties={
                            "number": part_number,
                            "law_reference": law_id,
                            "article": article_number,
                            "content": chunk_text[:1500],
                        },
                    )
                )
                relations.append(
                    GraphRelation(
                        from_node=article_id or law_id,
                        to_node=part_id,
                        relation_type="CONTAINS",
                    )
                )

            if point_number:
                point_id = _make_node_id("point", law_id, article_number or "", part_number or "", point_number)
                nodes.append(
                    GraphNode(
                        id=point_id,
                        type="Point",
                        properties={
                            "number": point_number,
                            "law_reference": law_id,
                            "article": article_number,
                            "part": part_number,
                            "content": chunk_text[:1200],
                        },
                    )
                )
                relations.append(
                    GraphRelation(
                        from_node=part_id or article_id or law_id,
                        to_node=point_id,
                        relation_type="CONTAINS",
                    )
                )

            if subpoint_number:
                subpoint_id = _make_node_id("subpoint", law_id, article_number or "", part_number or "", point_number or "", subpoint_number)
                nodes.append(
                    GraphNode(
                        id=subpoint_id,
                        type="Subpoint",
                        properties={
                            "number": subpoint_number,
                            "law_reference": law_id,
                            "article": article_number,
                            "part": part_number,
                            "point": point_number,
                            "content": chunk_text[:800],
                        },
                    )
                )
                relations.append(
                    GraphRelation(
                        from_node=point_id or part_id or article_id or law_id,
                        to_node=subpoint_id,
                        relation_type="CONTAINS",
                    )
                )

        return nodes, relations

    async def _extract_article_nodes(self, content: str, law_id: str, entities: List[LegalEntity]) -> List[GraphNode]:
        """Извлечение узлов статей"""
        nodes = []

        # Ищем статьи в тексте
        article_patterns = [
            r'Статья\s+(\d+)\.?\s*([^\n]*)',
            r'статья\s+(\d+)\.?\s*([^\n]*)',
            r'Пункт\s+(\d+)\.?\s*([^\n]*)',
            r'Часть\s+(\d+)\.?\s*([^\n]*)'
        ]

        found_articles = set()

        for pattern in article_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                article_num = match.group(1)
                article_title = match.group(2).strip()

                if article_num not in found_articles:
                    found_articles.add(article_num)

                    node = GraphNode(
                        id=f"article_{law_id}_{article_num}",
                        type="Article",
                        properties={
                            "number": int(article_num),
                            "title": article_title,
                            "law_reference": law_id,
                            "content_snippet": content[max(0, match.start()-100):match.end()+200]
                        }
                    )
                    nodes.append(node)

        # Также ищем статьи в сущностях NER
        for entity in entities:
            if entity.entity_type == "article_reference":
                article_match = re.search(r'статья\s*(\d+)', entity.text, re.IGNORECASE)
                if article_match:
                    article_num = article_match.group(1)
                    if article_num not in found_articles:
                        found_articles.add(article_num)

                        node = GraphNode(
                            id=f"article_{law_id}_{article_num}",
                            type="Article",
                            properties={
                                "number": int(article_num),
                                "title": entity.text,
                                "law_reference": law_id,
                                "confidence": entity.confidence
                            }
                        )
                        nodes.append(node)

        return nodes

    async def _extract_constraint_nodes(self, entities: List[LegalEntity], law_id: str) -> List[GraphNode]:
        """Извлечение узлов ограничений"""
        nodes = []

        constraint_id = 0
        for entity in entities:
            if entity.entity_type == "numerical_constraint":
                constraint_id += 1

                # Парсим значение и тип
                value = entity.text
                constraint_type = "unknown"
                unit = ""

                if "%" in value:
                    constraint_type = "percentage"
                    unit = "percent"
                elif any(time_word in value.lower() for time_word in ["лет", "год", "месяц", "день"]):
                    constraint_type = "temporal"
                    if "лет" in value.lower() or "год" in value.lower():
                        unit = "years"
                elif any(money_word in value.lower() for money_word in ["рубл", "копе", "евро", "доллар"]):
                    constraint_type = "monetary"
                    unit = "currency"

                node = GraphNode(
                    id=f"constraint_{law_id}_{constraint_id}",
                    type="Constraint",
                    properties={
                        "value": value,
                        "type": constraint_type,
                        "unit": unit,
                        "confidence": entity.confidence,
                        "raw_text": entity.text
                    }
                )
                nodes.append(node)

        return nodes

    async def _extract_concept_nodes(self, entities: List[LegalEntity], law_id: str) -> List[GraphNode]:
        """Извлечение узлов правовых понятий"""
        nodes = []

        concept_id = 0
        for entity in entities:
            if entity.entity_type in ["legal_concept", "definition", "authority_modal"]:
                concept_id += 1

                node = GraphNode(
                    id=f"concept_{law_id}_{concept_id}",
                    type="LegalConcept",
                    properties={
                        "name": entity.text,
                        "category": entity.entity_type,
                        "confidence": entity.confidence,
                        "context": entity.context if hasattr(entity, 'context') else ""
                    }
                )
                nodes.append(node)

        return nodes

    async def _extract_relations(self, nodes: List[GraphNode], entities: List[LegalEntity], content: str) -> List[GraphRelation]:
        """Извлечение связей между узлами"""
        relations = []

        laws = [n for n in nodes if n.type == "Law"]
        articles = [n for n in nodes if n.type == "Article"]
        parts = [n for n in nodes if n.type == "Part"]
        points = [n for n in nodes if n.type == "Point"]
        subpoints = [n for n in nodes if n.type == "Subpoint"]
        constraints = [n for n in nodes if n.type == "Constraint"]
        concepts = [n for n in nodes if n.type == "LegalConcept"]

        article_lookup = {node.id: node for node in articles}
        part_lookup = {node.id: node for node in parts}
        point_lookup = {node.id: node for node in points}
        subpoint_lookup = {node.id: node for node in subpoints}

        for constraint in constraints:
            raw_text = constraint.properties.get("raw_text", "")
            linked = False
            for article in articles:
                snippet = article.properties.get("content", "")
                if raw_text and raw_text in snippet:
                    relations.append(
                        GraphRelation(
                            from_node=article.id,
                            to_node=constraint.id,
                            relation_type="CONTAINS",
                        )
                    )
                    linked = True
                    break
            if not linked:
                for part in parts:
                    snippet = part.properties.get("content", "")
                    if raw_text and raw_text in snippet:
                        relations.append(
                            GraphRelation(
                                from_node=part.id,
                                to_node=constraint.id,
                                relation_type="CONTAINS",
                            )
                        )
                        linked = True
                        break

        for concept in concepts:
            name = (concept.properties.get("name") or "").lower()
            for article in articles:
                snippet = article.properties.get("content", "").lower()
                if name and name in snippet:
                    relations.append(
                        GraphRelation(
                            from_node=article.id,
                            to_node=concept.id,
                            relation_type="DEFINES",
                        )
                    )
            for part in parts:
                snippet = part.properties.get("content", "").lower()
                if name and name in snippet:
                    relations.append(
                        GraphRelation(
                            from_node=part.id,
                            to_node=concept.id,
                            relation_type="EXPLAINS",
                        )
                    )

        for constraint in constraints:
            raw_text = (constraint.properties.get("raw_text") or "").lower()
            for concept in concepts:
                concept_name = (concept.properties.get("name") or "").lower()
                if concept_name and concept_name in raw_text:
                    relations.append(
                        GraphRelation(
                            from_node=constraint.id,
                            to_node=concept.id,
                            relation_type="APPLIES_TO",
                        )
                    )

        for entity in entities:
            if getattr(entity, "entity_type", None) == "article_reference" and entity.metadata:
                target_article = entity.metadata.get("article")
                source_article = entity.metadata.get("source_article")
                if source_article and target_article:
                    source_id = next(
                        (
                            node.id
                            for node in articles
                            if str(node.properties.get("number")) == str(source_article)
                        ),
                        None,
                    )
                    target_id = next(
                        (
                            node.id
                            for node in articles
                            if str(node.properties.get("number")) == str(target_article)
                        ),
                        None,
                    )
                    if source_id and target_id:
                        relations.append(
                            GraphRelation(
                                from_node=source_id,
                                to_node=target_id,
                                relation_type="REFERENCES",
                            )
                        )

        return relations


class GraphLegalIntelligenceEngine:
    """
    Главный движок Graph Legal Intelligence
    Объединяет Universal Legal System с графовой базой данных
    """

    def __init__(self):
        # Инициализация компонентов
        self.graph_db = None  # Будет установлен в initialize()
        self.document_extractor = GraphDocumentExtractor()
        self.universal_system = UniversalLegalSystem()

        self.logger = logging.getLogger(self.__class__.__name__)

        # Флаги состояния
        self.neo4j_available = False
        self.fallback_to_mock = False

        # Статистика работы
        self.stats = {
            "total_documents_processed": 0,
            "total_nodes_created": 0,
            "total_relations_created": 0,
            "graph_enhanced_queries": 0,
            "hybrid_search_improvements": 0,
            "neo4j_mode": "unknown"
        }

    async def initialize(self) -> None:
        """Инициализация Graph Legal Intelligence Engine"""
        try:
            self.logger.info("🕸️ Initializing Graph Legal Intelligence Engine...")

            # Попытка подключения к реальному Neo4j
            if NEO4J_REAL_AVAILABLE:
                try:
                    self.logger.info("🔄 Attempting to connect to real Neo4j...")
                    self.graph_db = await get_neo4j_connection()
                    self.neo4j_available = True
                    self.stats["neo4j_mode"] = "real"
                    self.logger.info("✅ Connected to real Neo4j successfully")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to connect to real Neo4j: {e}")
                    self.graph_db = None
                    self.neo4j_available = False

            # Fallback к мок соединению если Neo4j недоступен
            if not self.neo4j_available:
                self.logger.info("🔄 Falling back to Mock Neo4j Connection...")
                self.graph_db = MockNeo4jConnection()
                self.fallback_to_mock = True
                self.stats["neo4j_mode"] = "mock"
                self.logger.info("✅ Mock Neo4j Connection initialized")

            self.logger.info("✅ Graph Legal Intelligence Engine initialized successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Graph Legal Intelligence Engine: {e}")
            raise

    async def process_document_to_graph(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка документа и добавление в граф"""

        try:
            self.logger.info(f"Processing document to graph: {document.get('metadata', {}).get('document_id', 'unknown')}")

            # 1. Извлекаем графовую структуру
            nodes, relations = await self.document_extractor.extract_graph_structure(document)

            # 2. Добавляем узлы в граф
            created_nodes = 0
            for node in nodes:
                await self.graph_db.create_node(node)
                created_nodes += 1

            # 3. Добавляем связи в граф
            created_relations = 0
            for relation in relations:
                await self.graph_db.create_relation(relation)
                created_relations += 1

            # 4. Обновляем статистику
            self.stats["total_documents_processed"] += 1
            self.stats["total_nodes_created"] += created_nodes
            self.stats["total_relations_created"] += created_relations

            result = {
                "success": True,
                "document_id": document.get("metadata", {}).get("document_id"),
                "nodes_created": created_nodes,
                "relations_created": created_relations,
                "graph_processing_completed": True
            }

            self.logger.info(f"Document processed successfully: {created_nodes} nodes, {created_relations} relations")
            return result

        except Exception as e:
            self.logger.error(f"Error processing document to graph: {e}")
            return {
                "success": False,
                "error": str(e),
                "graph_processing_completed": False
            }

    async def graph_enhanced_query(
        self,
        query: str,
        context_documents: List[Dict[str, Any]] = None,
        max_chunks: int = 7,
        graph_depth: int = 2
    ) -> UniversalQueryResult:
        """
        Гибридный запрос: Universal Legal System + Graph Context
        """

        self.logger.info(f"Processing graph-enhanced query: {query[:100]}...")
        start_time = datetime.now()

        try:
            # 1. Обычная обработка через Universal Legal System
            universal_result = await self.universal_system.process_query(
                query=query,
                context_documents=context_documents,
                max_chunks=max_chunks,
                strict_verification=True
            )

            # 2. Поиск релевантных узлов в графе
            graph_context = await self._find_relevant_graph_context(query, universal_result)

            # 3. Обогащение результата графовым контекстом
            enhanced_result = await self._enhance_with_graph_context(universal_result, graph_context)

            # 4. Обновляем статистику
            self.stats["graph_enhanced_queries"] += 1
            if enhanced_result.confidence_score > universal_result.confidence_score:
                self.stats["hybrid_search_improvements"] += 1

            processing_time = (datetime.now() - start_time).total_seconds()
            enhanced_result.processing_time = processing_time

            self.logger.info(f"Graph-enhanced query completed in {processing_time:.2f}s")
            return enhanced_result

        except Exception as e:
            self.logger.error(f"Error in graph-enhanced query: {e}")
            # Возвращаем обычный результат Universal System если граф не работает
            return universal_result if 'universal_result' in locals() else UniversalQueryResult(
                success=False,
                query=query,
                answer="",
                entities_found=[],
                verification_results=[],
                chunks_used=[],
                search_analysis=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )

    async def _find_relevant_graph_context(self, query: str, universal_result: UniversalQueryResult) -> List[GraphContext]:
        """Поиск релевантного контекста в графе"""

        contexts = []

        try:
            # Ищем узлы по сущностям из Universal Legal System
            for entity in universal_result.entities_found:

                # Ищем статьи
                if entity.entity_type == "article_reference":
                    article_nodes = await self.graph_db.find_nodes(
                        node_type="Article",
                        properties={"title": entity.text}
                    )
                    for node in article_nodes:
                        context = await self.graph_db.traverse(node.id, depth=2)
                        if context.central_node:
                            contexts.append(context)

                # Ищем ограничения
                elif entity.entity_type == "numerical_constraint":
                    constraint_nodes = await self.graph_db.find_nodes(
                        node_type="Constraint",
                        properties={"value": entity.text}
                    )
                    for node in constraint_nodes:
                        context = await self.graph_db.traverse(node.id, depth=2)
                        if context.central_node:
                            contexts.append(context)

                # Ищем понятия
                elif entity.entity_type == "legal_concept":
                    concept_nodes = await self.graph_db.find_nodes(
                        node_type="LegalConcept",
                        properties={"name": entity.text}
                    )
                    for node in concept_nodes:
                        context = await self.graph_db.traverse(node.id, depth=1)
                        if context.central_node:
                            contexts.append(context)

        except Exception as e:
            self.logger.warning(f"Error finding graph context: {e}")

        return contexts

    async def _enhance_with_graph_context(
        self,
        universal_result: UniversalQueryResult,
        graph_contexts: List[GraphContext]
    ) -> UniversalQueryResult:
        """Обогащение результата графовым контекстом"""

        if not graph_contexts:
            return universal_result

        # Создаем копию результата для модификации
        enhanced_result = universal_result

        try:
            # Собираем дополнительную информацию из графа
            graph_info = []

            for context in graph_contexts:
                if context.central_node:

                    # Информация о связанных узлах
                    related_info = []
                    for node in context.related_nodes:
                        if node.type == "Constraint":
                            related_info.append(f"Ограничение: {node.properties.get('value', '')}")
                        elif node.type == "Article":
                            related_info.append(f"Статья {node.properties.get('number', '')}")
                        elif node.type == "LegalConcept":
                            related_info.append(f"Понятие: {node.properties.get('name', '')}")

                    if related_info:
                        graph_info.extend(related_info)

            # Добавляем графовую информацию к ответу
            if graph_info:
                graph_supplement = f"\n\n🕸️ Дополнительная информация из правового графа:\n" + "\n".join(f"• {info}" for info in graph_info[:5])
                enhanced_result.answer += graph_supplement

                # Повышаем уверенность если нашли точные связи
                if enhanced_result.confidence_score < 0.9:
                    enhanced_result.confidence_score = min(enhanced_result.confidence_score + 0.2, 1.0)

        except Exception as e:
            self.logger.warning(f"Error enhancing with graph context: {e}")

        return enhanced_result

    def get_graph_stats(self) -> Dict[str, Any]:
        """Статистика работы графового движка"""
        return {
            "engine_stats": self.stats.copy(),
            "graph_db_stats": {
                "total_nodes": len(self.graph_db.nodes),
                "total_relations": len(self.graph_db.relations),
                "node_types": {},
                "relation_types": {}
            },
            "universal_system_stats": self.universal_system.get_system_stats()
        }


# Глобальная инстанция Graph Legal Intelligence Engine
_graph_legal_engine = None

async def get_graph_legal_engine() -> GraphLegalIntelligenceEngine:
    """Получение глобального экземпляра Graph Legal Intelligence Engine"""
    global _graph_legal_engine
    if _graph_legal_engine is None:
        _graph_legal_engine = GraphLegalIntelligenceEngine()
        await _graph_legal_engine.initialize()
    return _graph_legal_engine


if __name__ == "__main__":
    # Тестирование Graph Legal Intelligence Engine
    async def test_graph_system():
        print("🕸️ Testing Graph Legal Intelligence Engine")

        engine = GraphLegalIntelligenceEngine()

        # Тестовый документ
        test_document = {
            "content": """
            Статья 7. Плата концедента

            1. Размер платы концедента не может превышать 80% от стоимости объекта концессионного соглашения.
            2. Плата концедента определяется концедентом.

            Статья 4. Срок концессионного соглашения

            Срок концессионного соглашения не может быть менее трех лет.
            """,
            "metadata": {
                "document_id": "test_document",
                "document_number": "LAW-001",
                "title": "Базовый закон о концессионных соглашениях",
                "document_type": "federal_law"
            }
        }

        # 1. Обрабатываем документ в граф
        print("📄 Processing document to graph...")
        process_result = await engine.process_document_to_graph(test_document)
        print(f"✅ Processing result: {process_result}")

        # 2. Тестируем гибридный запрос
        print("\n🔍 Testing graph-enhanced query...")
        test_query = "Каков размер платы концедента по этому нормативному акту?"

        result = await engine.graph_enhanced_query(
            query=test_query,
            context_documents=[test_document],
            max_chunks=5,
            graph_depth=2
        )

        print(f"✅ Query result:")
        print(f"   Success: {result.success}")
        print(f"   Answer: {result.answer}")
        print(f"   Confidence: {result.confidence_score:.2f}")
        print(f"   Entities found: {len(result.entities_found)}")
        print(f"   Processing time: {result.processing_time:.2f}s")

        # 3. Статистика системы
        stats = engine.get_graph_stats()
        print(f"\n📊 System stats: {stats}")

    asyncio.run(test_graph_system())