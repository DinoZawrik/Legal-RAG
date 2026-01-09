#!/usr/bin/env python3
"""
[GRAPH] Real Neo4j Connection для Graph Legal Intelligence Engine
Заменяет мок-соединение на реальное подключение к Neo4j
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
import os
from dataclasses import asdict

# Реальный Neo4j драйвер
try:
    from neo4j import GraphDatabase, basic_auth
    from neo4j.exceptions import ServiceUnavailable, AuthError, DatabaseError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None

from core.graph_types import GraphNode, GraphRelation, GraphContext

logger = logging.getLogger(__name__)


class Neo4jRealConnection:
    """
    Реальное соединение с Neo4j для Graph Legal Intelligence
    """

    def __init__(self, uri: str = None, username: str = None, password: str = None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "change_me_in_env")

        self.driver = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def connect(self) -> bool:
        """Подключение к Neo4j"""
        if not NEO4J_AVAILABLE:
            self.logger.error("[ERROR] Neo4j driver not available. Install: pip install neo4j")
            return False

        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=basic_auth(self.username, self.password),
                max_connection_lifetime=3600,
                keep_alive=True
            )

            # Проверяем соединение
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                test_value = result.single()["test"]

                if test_value == 1:
                    self.logger.info(f"[SUCCESS] Connected to Neo4j at {self.uri}")

                    # Создаем индексы и ограничения для производительности
                    await self._create_indexes_and_constraints()
                    return True
                else:
                    self.logger.error("[ERROR] Neo4j connection test failed")
                    return False

        except ServiceUnavailable as e:
            self.logger.error(f"[ERROR] Neo4j service unavailable: {e}")
            return False
        except AuthError as e:
            self.logger.error(f"[ERROR] Neo4j authentication failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"[ERROR] Neo4j connection error: {e}")
            return False

    async def _create_indexes_and_constraints(self):
        """Создание индексов и ограничений для оптимизации"""

        indexes_and_constraints = [
            # Уникальные ограничения
            "CREATE CONSTRAINT law_id_unique IF NOT EXISTS FOR (l:Law) REQUIRE l.id IS UNIQUE",
            "CREATE CONSTRAINT article_id_unique IF NOT EXISTS FOR (a:Article) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT constraint_id_unique IF NOT EXISTS FOR (c:Constraint) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT concept_id_unique IF NOT EXISTS FOR (lc:LegalConcept) REQUIRE lc.id IS UNIQUE",

            # Индексы для поиска
            "CREATE INDEX law_number_index IF NOT EXISTS FOR (l:Law) ON (l.number)",
            "CREATE INDEX article_number_index IF NOT EXISTS FOR (a:Article) ON (a.number)",
            "CREATE INDEX constraint_value_index IF NOT EXISTS FOR (c:Constraint) ON (c.value)",
            "CREATE INDEX concept_name_index IF NOT EXISTS FOR (lc:LegalConcept) ON (lc.name)",

            # Композитные индексы
            "CREATE INDEX article_law_index IF NOT EXISTS FOR (a:Article) ON (a.law_reference, a.number)",
            "CREATE INDEX constraint_type_index IF NOT EXISTS FOR (c:Constraint) ON (c.type, c.value)"
        ]

        with self.driver.session() as session:
            for statement in indexes_and_constraints:
                try:
                    session.run(statement)
                    self.logger.debug(f"[SUCCESS] Executed: {statement}")
                except Exception as e:
                    # Многие из этих команд могут завершиться с ошибкой если индекс уже существует
                    self.logger.debug(f"Index/constraint already exists or error: {e}")

    async def create_node(self, node: GraphNode) -> str:
        """Создание узла в Neo4j"""
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")

        try:
            with self.driver.session() as session:
                # Подготавливаем свойства узла
                properties = dict(node.properties)
                properties['id'] = node.id

                # Создаем Cypher запрос
                cypher = f"""
                MERGE (n:{node.type} {{id: $id}})
                SET n += $properties
                RETURN n.id as created_id
                """

                result = session.run(cypher, id=node.id, properties=properties)
                record = result.single()

                if record:
                    created_id = record["created_id"]
                    self.logger.debug(f"[SUCCESS] Created node {node.type}:{created_id}")
                    return created_id
                else:
                    raise RuntimeError(f"Failed to create node {node.type}:{node.id}")

        except Exception as e:
            self.logger.error(f"[ERROR] Error creating node {node.type}:{node.id}: {e}")
            raise

    async def create_relation(self, relation: GraphRelation) -> str:
        """Создание связи в Neo4j"""
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")

        try:
            with self.driver.session() as session:
                # Подготавливаем свойства связи
                rel_properties = relation.properties or {}

                cypher = f"""
                MATCH (from_node {{id: $from_id}})
                MATCH (to_node {{id: $to_id}})
                MERGE (from_node)-[r:{relation.relation_type}]->(to_node)
                SET r += $properties
                RETURN id(r) as relation_id
                """

                result = session.run(
                    cypher,
                    from_id=relation.from_node,
                    to_id=relation.to_node,
                    properties=rel_properties
                )

                record = result.single()
                if record:
                    relation_id = str(record["relation_id"])
                    self.logger.debug(f"[SUCCESS] Created relation {relation.from_node}-[{relation.relation_type}]->{relation.to_node}")
                    return relation_id
                else:
                    raise RuntimeError(f"Failed to create relation {relation.relation_type}")

        except Exception as e:
            self.logger.error(f"[ERROR] Error creating relation {relation.relation_type}: {e}")
            raise

    async def find_nodes(self, node_type: str = None, properties: Dict[str, Any] = None) -> List[GraphNode]:
        """Поиск узлов по типу и свойствам"""
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")

        try:
            with self.driver.session() as session:
                # Строим Cypher запрос
                where_clauses = []
                params = {}

                if node_type:
                    cypher = f"MATCH (n:{node_type})"
                else:
                    cypher = "MATCH (n)"

                if properties:
                    for key, value in properties.items():
                        param_name = f"prop_{key}"
                        where_clauses.append(f"n.{key} = ${param_name}")
                        params[param_name] = value

                if where_clauses:
                    cypher += " WHERE " + " AND ".join(where_clauses)

                cypher += " RETURN n, labels(n) as node_labels"

                result = session.run(cypher, **params)

                nodes = []
                for record in result:
                    node_data = dict(record["n"])
                    node_labels = record["node_labels"]

                    # Извлекаем id и остальные свойства
                    node_id = node_data.pop('id', '')
                    node_type_detected = node_labels[0] if node_labels else "Unknown"

                    node = GraphNode(
                        id=node_id,
                        type=node_type_detected,
                        properties=node_data
                    )
                    nodes.append(node)

                self.logger.debug(f"[SUCCESS] Found {len(nodes)} nodes")
                return nodes

        except Exception as e:
            self.logger.error(f"[ERROR] Error finding nodes: {e}")
            return []

    async def traverse(self, start_node_id: str, depth: int = 2) -> GraphContext:
        """Обход графа от узла на заданную глубину"""
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")

        try:
            with self.driver.session() as session:
                # Сложный Cypher запрос для обхода графа
                cypher = f"""
                MATCH (central {{id: $start_id}})
                OPTIONAL MATCH path = (central)-[*1..{depth}]-(connected)
                WITH central, collect(DISTINCT connected) as related_nodes,
                     collect(DISTINCT [rel IN relationships(path) | rel]) as all_relationships
                RETURN central,
                       labels(central) as central_labels,
                       related_nodes,
                       reduce(result = [], rels IN all_relationships | result + [r IN rels | {{
                           type: type(r),
                           start: startNode(r).id,
                           end: endNode(r).id,
                           properties: properties(r)
                       }}]) as relations
                """

                result = session.run(cypher, start_id=start_node_id)
                record = result.single()

                if not record:
                    return GraphContext(None, [], [], 0, 0.0)

                # Обрабатываем центральный узел
                central_data = dict(record["central"])
                central_labels = record["central_labels"]
                central_id = central_data.pop('id', start_node_id)
                central_type = central_labels[0] if central_labels else "Unknown"

                central_node = GraphNode(
                    id=central_id,
                    type=central_type,
                    properties=central_data
                )

                # Обрабатываем связанные узлы
                related_nodes = []
                for node_data in record["related_nodes"]:
                    if node_data:  # Проверяем что узел не None
                        node_dict = dict(node_data)
                        node_id = node_dict.pop('id', '')
                        # Получаем тип узла через дополнительный запрос
                        node_labels_result = session.run("MATCH (n {id: $id}) RETURN labels(n) as labels", id=node_id)
                        node_labels_record = node_labels_result.single()
                        node_type = node_labels_record["labels"][0] if node_labels_record and node_labels_record["labels"] else "Unknown"

                        related_node = GraphNode(
                            id=node_id,
                            type=node_type,
                            properties=node_dict
                        )
                        related_nodes.append(related_node)

                # Обрабатываем связи
                relations = []
                for rel_data in record["relations"]:
                    if rel_data:  # Проверяем что связь не None
                        relation = GraphRelation(
                            from_node=rel_data["start"],
                            to_node=rel_data["end"],
                            relation_type=rel_data["type"],
                            properties=rel_data.get("properties", {})
                        )
                        relations.append(relation)

                # Вычисляем confidence на основе количества связей
                confidence_score = min(0.8 + (len(relations) * 0.05), 1.0) if relations else 0.2

                graph_context = GraphContext(
                    central_node=central_node,
                    related_nodes=related_nodes,
                    relations=relations,
                    traversal_depth=depth,
                    confidence_score=confidence_score
                )

                self.logger.debug(f"[SUCCESS] Graph traversal: {len(related_nodes)} nodes, {len(relations)} relations")
                return graph_context

        except Exception as e:
            self.logger.error(f"[ERROR] Error traversing graph from {start_node_id}: {e}")
            return GraphContext(None, [], [], 0, 0.0)

    async def execute_cypher(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Выполнение произвольного Cypher запроса"""
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")

        try:
            with self.driver.session() as session:
                result = session.run(cypher, parameters or {})
                records = []
                for record in result:
                    records.append(dict(record))

                self.logger.debug(f"[SUCCESS] Cypher executed: {len(records)} records returned")
                return records

        except Exception as e:
            self.logger.error(f"[ERROR] Cypher execution error: {e}")
            raise

    async def get_graph_statistics(self) -> Dict[str, Any]:
        """Получение статистики графа"""
        if not self.driver:
            return {"error": "Not connected to Neo4j"}

        try:
            with self.driver.session() as session:
                stats = {}

                # Общая статистика узлов
                node_stats = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as node_type, count(n) as count
                ORDER BY count DESC
                """)

                stats["nodes_by_type"] = {}
                total_nodes = 0
                for record in node_stats:
                    node_type = record["node_type"] or "Unknown"
                    count = record["count"]
                    stats["nodes_by_type"][node_type] = count
                    total_nodes += count

                stats["total_nodes"] = total_nodes

                # Статистика связей
                rel_stats = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as relation_type, count(r) as count
                ORDER BY count DESC
                """)

                stats["relations_by_type"] = {}
                total_relations = 0
                for record in rel_stats:
                    rel_type = record["relation_type"]
                    count = record["count"]
                    stats["relations_by_type"][rel_type] = count
                    total_relations += count

                stats["total_relations"] = total_relations

                return stats

        except Exception as e:
            self.logger.error(f"[ERROR] Error getting graph statistics: {e}")
            return {"error": str(e)}

    async def clear_graph(self) -> bool:
        """Очистка всего графа (осторожно!)"""
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")

        try:
            with self.driver.session() as session:
                # Удаляем все связи и узлы
                session.run("MATCH (n) DETACH DELETE n")
                self.logger.warning("[WARNING] Graph cleared completely")
                return True

        except Exception as e:
            self.logger.error(f"[ERROR] Error clearing graph: {e}")
            return False

    async def close(self):
        """Закрытие соединения с Neo4j"""
        if self.driver:
            self.driver.close()
            self.logger.info("[DISCONNECT] Neo4j connection closed")


# Глобальная инстанция Neo4j соединения
_neo4j_connection = None

async def get_neo4j_connection() -> Neo4jRealConnection:
    """Получение глобального подключения к Neo4j"""
    global _neo4j_connection
    if _neo4j_connection is None:
        _neo4j_connection = Neo4jRealConnection()
        connected = await _neo4j_connection.connect()
        if not connected:
            raise RuntimeError("Failed to connect to Neo4j")
    return _neo4j_connection


if __name__ == "__main__":
    # Тестирование Neo4j соединения
    async def test_neo4j_connection():
        print("[GRAPH] Testing Real Neo4j Connection")

        try:
            # Подключаемся
            connection = Neo4jRealConnection()
            connected = await connection.connect()

            if not connected:
                print("[ERROR] Failed to connect to Neo4j")
                return

            # Тестовый узел
            test_node = GraphNode(
                id="test_law_neo4j",
                type="Law",
                properties={
                    "number": "TEST-ФЗ",
                    "title": "Тестовый закон для Neo4j"
                }
            )

            # Создаем узел
            created_id = await connection.create_node(test_node)
            print(f"[SUCCESS] Created test node: {created_id}")

            # Ищем узел
            found_nodes = await connection.find_nodes("Law", {"number": "TEST-ФЗ"})
            print(f"[SUCCESS] Found {len(found_nodes)} nodes")

            # Статистика
            stats = await connection.get_graph_statistics()
            print(f"[SUCCESS] Graph stats: {stats}")

            # Очищаем тестовые данные
            await connection.execute_cypher("MATCH (n:Law {number: 'TEST-ФЗ'}) DELETE n")
            print("[SUCCESS] Cleaned up test data")

            # Закрываем соединение
            await connection.close()

        except Exception as e:
            print(f"[ERROR] Test failed: {e}")

    asyncio.run(test_neo4j_connection())