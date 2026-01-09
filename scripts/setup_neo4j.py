#!/usr/bin/env python3
"""
[Neo4j] Setup Script для Neo4j Graph Database
Автоматическая установка и настройка Neo4j для Legal Intelligence System
"""

import asyncio
import subprocess
import sys
import time
import requests
import logging
import os
from typing import Dict, Any

from core.logging_config import configure_logging

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


class Neo4jSetup:
    """Установщик и настройщик Neo4j"""

    def __init__(self):
        self.neo4j_url = "http://localhost:7474"
        self.bolt_url = "bolt://localhost:7687"
        self.username = "neo4j"
        self.password = os.getenv("NEO4J_PASSWORD", "change_me_in_env")

    async def setup_complete_neo4j(self) -> bool:
        """Полная установка и настройка Neo4j"""

        print("[Neo4j] SETTING UP NEO4J FOR LEGAL INTELLIGENCE SYSTEM")
        print("=" * 60)

        try:
            # 1. Установка Neo4j драйвера Python
            print("\n[STEP 1] Installing Neo4j Python driver...")
            if not await self._install_neo4j_driver():
                return False

            # 2. Запуск Neo4j через Docker
            print("\n[STEP 2] Starting Neo4j with Docker...")
            if not await self._start_neo4j_docker():
                return False

            # 3. Ожидание готовности Neo4j
            print("\n[STEP 3] Waiting for Neo4j to be ready...")
            if not await self._wait_for_neo4j_ready():
                return False

            # 4. Проверка подключения
            print("\n[STEP 4] Testing Neo4j connection...")
            if not await self._test_neo4j_connection():
                return False

            # 5. Создание тестовых данных
            print("\n[STEP 5] Creating test legal graph structure...")
            if not await self._create_test_legal_graph():
                return False

            print("\n[SUCCESS] NEO4J SETUP COMPLETED SUCCESSFULLY!")
            print("[INFO] Neo4j Web Interface: http://localhost:7474")
            print(f"[INFO] Username: {self.username}")
            print(f"[INFO] Password: {self.password}")

            return True

        except Exception as e:
            print(f"\n[ERROR] Neo4j setup failed: {e}")
            return False

    async def _install_neo4j_driver(self) -> bool:
        """Установка Neo4j Python драйвера"""
        try:
            # Проверяем, установлен ли уже драйвер
            try:
                import neo4j
                print("[OK] Neo4j driver already installed")
                return True
            except ImportError:
                pass

            # Устанавливаем драйвер
            print("[INSTALL] Installing neo4j driver...")
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "neo4j"
            ], capture_output=True, text=True)

            if result.returncode == 0:
                print("[OK] Neo4j driver installed successfully")
                return True
            else:
                print(f"[ERROR] Failed to install neo4j driver: {result.stderr}")
                return False

        except Exception as e:
            print(f"[ERROR] Error installing neo4j driver: {e}")
            return False

    async def _start_neo4j_docker(self) -> bool:
        """Запуск Neo4j через Docker Compose"""
        try:
            # Проверяем, запущен ли уже Neo4j
            if await self._is_neo4j_running():
                print("[OK] Neo4j is already running")
                return True

            # Создаем сеть если её нет
            print("[NETWORK] Creating Docker network...")
            subprocess.run([
                "docker", "network", "create", "legalrag_network"
            ], capture_output=True)

            # Запускаем Neo4j
            print("[START] Starting Neo4j container...")
            result = subprocess.run([
                "docker-compose", "-f", "docker-compose.neo4j.yml", "up", "-d"
            ], capture_output=True, text=True)

            if result.returncode == 0:
                print("[OK] Neo4j container started successfully")
                return True
            else:
                print(f"[ERROR] Failed to start Neo4j: {result.stderr}")
                return False

        except Exception as e:
            print(f"[ERROR] Error starting Neo4j: {e}")
            return False

    async def _is_neo4j_running(self) -> bool:
        """Проверка, запущен ли Neo4j"""
        try:
            response = requests.get(self.neo4j_url, timeout=5)
            return response.status_code == 200
        except:
            return False

    async def _wait_for_neo4j_ready(self, timeout: int = 120) -> bool:
        """Ожидание готовности Neo4j"""
        print(f"[WAIT] Waiting up to {timeout} seconds for Neo4j to be ready...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(self.neo4j_url, timeout=5)
                if response.status_code == 200:
                    print("[OK] Neo4j is ready!")
                    return True
            except:
                pass

            print(".", end="", flush=True)
            await asyncio.sleep(2)

        print(f"\n[ERROR] Neo4j did not become ready within {timeout} seconds")
        return False

    async def _test_neo4j_connection(self) -> bool:
        """Тестирование подключения к Neo4j"""
        try:
            # Импортируем наш connection модуль
            from core.neo4j_real_connection import Neo4jRealConnection

            # Создаем подключение
            connection = Neo4jRealConnection()
            connected = await connection.connect()

            if connected:
                print("[OK] Neo4j connection test successful")

                # Получаем статистику
                stats = await connection.get_graph_statistics()
                print(f"[STATS] Graph stats: {stats}")

                await connection.close()
                return True
            else:
                print("[ERROR] Neo4j connection test failed")
                return False

        except Exception as e:
            print(f"[ERROR] Neo4j connection test error: {e}")
            return False

    async def _create_test_legal_graph(self) -> bool:
        """Создание тестовой структуры правового графа"""
        try:
            from core.neo4j_real_connection import Neo4jRealConnection
            from core.graph_legal_engine import GraphNode, GraphRelation

            # Подключаемся к Neo4j
            connection = Neo4jRealConnection()
            await connection.connect()

            print("[CREATE] Creating test legal document structure...")

            # Создаем тестовый закон
            law_node = GraphNode(
                id="law_115_fz_test",
                type="Law",
                properties={
                    "number": "115-ФЗ",
                    "title": "О концессионных соглашениях",
                    "adoption_date": "2005-07-21",
                    "status": "active"
                }
            )
            await connection.create_node(law_node)

            # Создаем статью 7
            article_7_node = GraphNode(
                id="article_115_fz_7",
                type="Article",
                properties={
                    "number": 7,
                    "title": "Плата концедента",
                    "law_reference": "law_115_fz_test"
                }
            )
            await connection.create_node(article_7_node)

            # Создаем численное ограничение 80%
            constraint_80_node = GraphNode(
                id="constraint_80_percent",
                type="Constraint",
                properties={
                    "value": "80%",
                    "type": "percentage",
                    "unit": "percent",
                    "description": "Максимальный размер платы концедента"
                }
            )
            await connection.create_node(constraint_80_node)

            # Создаем понятие "плата концедента"
            concept_node = GraphNode(
                id="concept_plata_concedenta",
                type="LegalConcept",
                properties={
                    "name": "плата концедента",
                    "category": "financial_obligation",
                    "definition": "Плата, вносимая концессионером концеденту"
                }
            )
            await connection.create_node(concept_node)

            # Создаем связи
            relations = [
                GraphRelation("law_115_fz_test", "article_115_fz_7", "CONTAINS"),
                GraphRelation("article_115_fz_7", "constraint_80_percent", "CONTAINS"),
                GraphRelation("article_115_fz_7", "concept_plata_concedenta", "DEFINES"),
                GraphRelation("constraint_80_percent", "concept_plata_concedenta", "APPLIES_TO")
            ]

            for relation in relations:
                await connection.create_relation(relation)

            # Проверяем созданную структуру
            final_stats = await connection.get_graph_statistics()
            print(f"[OK] Test legal graph created: {final_stats}")

            await connection.close()
            return True

        except Exception as e:
            print(f"[ERROR] Error creating test legal graph: {e}")
            return False

    async def status_check(self) -> Dict[str, Any]:
        """Проверка статуса Neo4j установки"""
        status = {
            "neo4j_driver_installed": False,
            "neo4j_running": False,
            "neo4j_accessible": False,
            "graph_populated": False,
            "ready_for_production": False
        }

        try:
            # Проверка драйвера
            try:
                import neo4j
                status["neo4j_driver_installed"] = True
            except ImportError:
                pass

            # Проверка запуска
            status["neo4j_running"] = await self._is_neo4j_running()

            # Проверка доступности
            if status["neo4j_running"]:
                try:
                    from core.neo4j_real_connection import Neo4jRealConnection
                    connection = Neo4jRealConnection()
                    connected = await connection.connect()
                    status["neo4j_accessible"] = connected

                    if connected:
                        stats = await connection.get_graph_statistics()
                        status["graph_populated"] = stats.get("total_nodes", 0) > 0
                        await connection.close()

                except Exception:
                    pass

            # Общая готовность
            status["ready_for_production"] = all([
                status["neo4j_driver_installed"],
                status["neo4j_running"],
                status["neo4j_accessible"],
                status["graph_populated"]
            ])

        except Exception as e:
            status["error"] = str(e)

        return status


async def main():
    """Основная функция установки"""

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        # Только проверка статуса
        setup = Neo4jSetup()
        status = await setup.status_check()

        print("[Neo4j] NEO4J STATUS CHECK")
        print("=" * 40)
        for key, value in status.items():
            symbol = "[OK]" if value else "[FAIL]"
            print(f"{symbol} {key}: {value}")

        if status.get("ready_for_production"):
            print("\n[SUCCESS] Neo4j is ready for production!")
        else:
            print("\n[WARNING] Neo4j setup is incomplete")

    else:
        # Полная установка
        setup = Neo4jSetup()
        success = await setup.setup_complete_neo4j()

        if success:
            print("\n[SUCCESS] Setup completed successfully!")
            print("[INFO] You can now use the Hybrid Legal Intelligence System")
        else:
            print("\n[ERROR] Setup failed. Please check the logs and try again.")


if __name__ == "__main__":
    asyncio.run(main())