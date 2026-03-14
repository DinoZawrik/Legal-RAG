#!/usr/bin/env python3
"""Запуск конвейера подготовки данных и теста на 40 вопросов."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Локальные импорты выполняются после модификации sys.path
from scripts.reset_and_ingest_documents import IngestionSummary, orchestrate # noqa: E402
from tests.manual.test_correct_40_questions import CorrectQuestionsTest # noqa: E402
from core.logging_config import configure_logging as configure_app_logging


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Очистка стораджей (опционально) и запуск теста на 40 вопросов",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Не запускать предварительную очистку и загрузку документов.",
    )
    parser.add_argument(
        "--documents-path",
        type=str,
        help="Каталог с документами для загрузки (прокидывается в reset_and_ingest_documents).",
    )
    parser.add_argument(
        "--ingest-skip-clear",
        action="store_true",
        help="Не выполнять очистку стораджей перед загрузкой документов.",
    )
    parser.add_argument(
        "--ingest-skip-load",
        action="store_true",
        help="Пропустить загрузку документов (например, если данные уже загружены).",
    )
    parser.add_argument(
        "--ingest-no-verify",
        action="store_true",
        help="Отключить проверку после загрузки документов.",
    )
    parser.add_argument(
        "--api-base-url",
        type=str,
        help="Базовый URL API (по умолчанию http://localhost:8080).",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results/qa_40_questions",
        help="Каталог для сохранения результатов теста и агрегированного отчёта.",
    )
    parser.add_argument(
        "--questions-file",
        type=str,
        help="Текстовый файл со списком вопросов (по умолчанию используется встроенный список).",
    )
    parser.add_argument(
        "--target-success-rate",
        type=float,
        default=80.0,
        help="Целевой процент успешных ответов для прохождения теста.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Включить детальный лог (DEBUG).",
    )

    return parser.parse_args(argv)


def configure_logging(verbose: bool) -> None:
    level = "DEBUG" if verbose else os.getenv("LOG_LEVEL", "INFO")
    configure_app_logging(level)


async def run_ingestion(args: argparse.Namespace) -> IngestionSummary:
    logging.info(" Стартует очистка и загрузка документов")
    ingest_args = SimpleNamespace(
        skip_clear=args.ingest_skip_clear,
        skip_load=args.ingest_skip_load,
        documents_path=args.documents_path,
        verify=not args.ingest_no_verify,
    )
    summary = await orchestrate(ingest_args)
    logging.info(
        " Очистка/загрузка завершена: chunks=%s, documents_path=%s",
        summary.chunks_loaded,
        summary.documents_path,
    )
    return summary


async def run_evaluation(args: argparse.Namespace, results_dir: Path) -> Dict[str, Any]:
    logging.info(" Запуск теста на 40 вопросов")

    questions_path = Path(args.questions_file).expanduser() if args.questions_file else None

    tester = CorrectQuestionsTest(
        api_base_url=args.api_base_url,
        results_dir=results_dir,
        questions_file=questions_path,
    )

    results = await tester.run_all_tests()
    logging.info(
        " Тест завершён: success_rate=%.1f%% (целевое значение %.1f%%)",
        results.get("success_rate", 0.0),
        args.target_success_rate,
    )
    return results


async def main_async(args: argparse.Namespace) -> Dict[str, Any]:
    results_dir = Path(args.results_dir).expanduser().resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    ingestion_summary: Optional[IngestionSummary] = None
    if not args.skip_ingest:
        ingestion_summary = await run_ingestion(args)
    else:
        logging.info(" Пропущена подготовка данных (--skip-ingest)")

    evaluation_results = await run_evaluation(args, results_dir)
    success_rate = evaluation_results.get("success_rate", 0.0)
    success = evaluation_results.get("success", success_rate >= args.target_success_rate)

    aggregated: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "target_success_rate": args.target_success_rate,
        "success": bool(success_rate >= args.target_success_rate and success),
        "evaluation": evaluation_results,
    }

    if ingestion_summary:
        aggregated["ingestion"] = {
            "cleared_items": ingestion_summary.cleared_items,
            "chunks_loaded": ingestion_summary.chunks_loaded,
            "documents_path": ingestion_summary.documents_path,
            "duration_seconds": ingestion_summary.duration_seconds,
        }

    summary_path = results_dir / f"pipeline_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(aggregated, fh, ensure_ascii=False, indent=2)

    logging.info(" Сводный отчёт сохранён: %s", summary_path)

    return aggregated


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        aggregated = asyncio.run(main_async(args))
        success = aggregated.get("success", False)
        if success:
            logging.info(" Тест пройден: достигнут целевой уровень точности")
        else:
            logging.warning(" Тест не прошёл целевую метрику")
    except KeyboardInterrupt:
        logging.warning(" Операция прервана пользователем")
        raise SystemExit(130) from None
    except Exception as exc: # pylint: disable=broad-except
        logging.exception(" Ошибка при выполнении сценария: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
