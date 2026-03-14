#!/usr/bin/env python3
"""Атомарный сброс стораджей и загрузка тестовых документов.

Скрипт объединяет очистку PostgreSQL, Redis и ChromaDB с дальнейшей
загрузкой правовых документов из каталога `файлы_для_теста` при помощи
`ProperDocumentLoader`. Позволяет быстро подготовить среду перед регрессионными
проверками и запуском e2e-тестов.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Добавляем корневую директорию проекта для корректных импортов
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Импорты из внутренних скриптов (асинхронные функции уже доступны)
from scripts.clear_all_databases import ( # noqa: E402
    clear_chromadb,
    clear_postgresql,
    clear_redis,
)
from scripts.data_loaders.load_proper_test_documents import ( # noqa: E402
    ProperDocumentLoader,
)


@dataclass
class IngestionSummary:
    """Результат выполнения скрипта."""

    cleared_items: Dict[str, int]
    chunks_loaded: int
    documents_path: str
    duration_seconds: float


def configure_logging(verbose: bool) -> None:
    """Базовая настройка логирования."""

    from core.logging_config import configure_logging as configure_app_logging

    level = "DEBUG" if verbose else os.getenv("LOG_LEVEL", "INFO")
    configure_app_logging(level)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Парсинг аргументов командной строки."""

    parser = argparse.ArgumentParser(
        description="Сброс стораджей и загрузка правовых документов",
    )
    parser.add_argument(
        "--skip-clear",
        action="store_true",
        help="Пропустить очистку PostgreSQL/Redis/ChromaDB.",
    )
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="Пропустить загрузку документов после очистки.",
    )
    parser.add_argument(
        "--documents-path",
        type=str,
        help="Явно указать каталог с тестовыми документами (переопределяет TEST_DOCUMENTS_PATH).",
    )
    parser.add_argument(
        "--verify",
        dest="verify",
        action="store_true",
        default=True,
        help="Выполнить проверку загруженных документов (включено по умолчанию).",
    )
    parser.add_argument(
        "--no-verify",
        dest="verify",
        action="store_false",
        help="Отключить проверку загруженных документов.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Расширенный вывод логов.",
    )

    return parser.parse_args(argv)


async def reset_datastores() -> Dict[str, int]:
    """Очищает PostgreSQL, Redis и ChromaDB."""

    logging.info(" Запускаю полную очистку стораджей")
    cleared: Dict[str, int] = {}

    cleared["postgres"] = await clear_postgresql()
    cleared["redis"] = await clear_redis()
    cleared["chromadb"] = await clear_chromadb()

    logging.info(
        " Очистка завершена: postgres=%s, redis=%s, chromadb=%s",
        cleared["postgres"],
        cleared["redis"],
        cleared["chromadb"],
    )
    return cleared


async def ingest_documents(documents_path: Optional[str], verify: bool) -> tuple[int, str]:
    """Запускает `ProperDocumentLoader` с опциональной верификацией."""

    if documents_path:
        path_obj = Path(documents_path).expanduser().resolve()
        if not path_obj.exists() or not path_obj.is_dir():
            raise FileNotFoundError(f"Каталог с документами не найден: {path_obj}")
        os.environ["TEST_DOCUMENTS_PATH"] = str(path_obj)
        logging.info(" Использую каталог документов: %s", path_obj)

    loader = ProperDocumentLoader()

    logging.info(" Инициализация UnifiedStorageManager")
    initialized = await loader.initialize_storage()
    if not initialized:
        raise RuntimeError("Не удалось инициализировать хранилище")

    logging.info(" Начинаю загрузку документов")
    chunks = await loader.load_all_test_documents()

    if verify:
        logging.info(" Запускаю верификацию загруженных документов")
        await loader.verify_loaded_documents()

    # Уточняем реальный путь, который использовал loader (на случай автоопределения)
    resolved_path = loader.documents_path
    logging.info(" Загрузка завершена: всего чанков=%s", len(chunks))
    return len(chunks), resolved_path


async def orchestrate(args: argparse.Namespace) -> IngestionSummary:
    """Основной сценарий скрипта."""

    start_ts = datetime.now()
    cleared_items: Dict[str, int] = {"postgres": 0, "redis": 0, "chromadb": 0}

    if args.skip_clear:
        logging.info(" Очистка стораджей пропущена по флагу --skip-clear")
    else:
        cleared_items = await reset_datastores()

    chunks_loaded = 0
    documents_root = args.documents_path or "(auto-detect)"

    if args.skip_load:
        logging.info(" Загрузка документов пропущена по флагу --skip-load")
    else:
        chunks_loaded, documents_root = await ingest_documents(
            documents_path=args.documents_path,
            verify=args.verify,
        )

    duration = (datetime.now() - start_ts).total_seconds()

    return IngestionSummary(
        cleared_items=cleared_items,
        chunks_loaded=chunks_loaded,
        documents_path=documents_root,
        duration_seconds=duration,
    )


def print_summary(summary: IngestionSummary, args: argparse.Namespace) -> None:
    """Вывод финального отчёта по шагам скрипта."""

    logging.info("\n%s", "=" * 72)
    logging.info(" Итоги автоматизированного сброса и загрузки")
    logging.info("Время выполнения: %.2f c", summary.duration_seconds)
    logging.info(
        "Очистка: postgres=%s, redis=%s, chromadb=%s",
        summary.cleared_items.get("postgres", 0),
        summary.cleared_items.get("redis", 0),
        summary.cleared_items.get("chromadb", 0),
    )
    if args.skip_load:
        logging.info("Загрузка документов: пропущена")
    else:
        logging.info("Загружено чанков: %s", summary.chunks_loaded)
        logging.info("Каталог документов: %s", summary.documents_path)
        logging.info("Верификация: %s", "включена" if args.verify else "пропущена")
    logging.info("%s\n", "=" * 72)


def main(argv: Optional[list[str]] = None) -> None:
    """Точка входа в сценарий."""

    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        summary = asyncio.run(orchestrate(args))
        print_summary(summary, args)
    except KeyboardInterrupt:
        logging.warning(" Операция прервана пользователем")
        raise SystemExit(130)
    except Exception as exc: # pylint: disable=broad-except
        logging.exception(" Не удалось выполнить сценарий: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
