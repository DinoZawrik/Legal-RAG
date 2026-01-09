#!/usr/bin/env python3
"""Convenience wrapper to build law datasets for bundled test PDFs."""

from __future__ import annotations

import sys
import logging
from pathlib import Path
import os

import click

from scripts.graph.build_law_dataset import build_dataset, save_dataset


logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_FILES_DIR = PROJECT_ROOT / "файлы_для_теста"
DEFAULT_PDF_PATTERNS = [
    "Федеральный закон от *115-ФЗ*.pdf",
    "Федеральный закон от *224-ФЗ*.pdf",
]


@click.command()
@click.option("--output-dir", default="data/laws", type=click.Path(path_type=Path))
@click.option("--pdf", "pdfs", multiple=True, type=click.Path(path_type=Path))
def main(output_dir: Path, pdfs: tuple[Path, ...]) -> None:
    logging.basicConfig(level=logging.INFO)
    if sys.platform.startswith('win'):
        os.system('chcp 65001 >NUL')
    output_dir = output_dir if output_dir.is_absolute() else PROJECT_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if pdfs:
        targets = [path if path.is_absolute() else PROJECT_ROOT / path for path in pdfs]
    else:
        targets = []
        for pattern in DEFAULT_PDF_PATTERNS:
            matches = list(TEST_FILES_DIR.glob(pattern)) if TEST_FILES_DIR.exists() else []
            if not matches:
                logger.warning("No files matched pattern '%s' in %s", pattern, TEST_FILES_DIR)
            targets.extend(matches)

    normalized_targets: list[Path] = []
    for candidate in targets:
        if candidate.exists():
            normalized_targets.append(candidate)
            continue
        # Try resolving relative to project root if not already absolute
        alt_candidate = PROJECT_ROOT / candidate
        if alt_candidate.exists():
            normalized_targets.append(alt_candidate)
            continue
        logger.warning("PDF not found, skipping: %s", candidate)

    if not normalized_targets:
        logger.error("No PDF files to process")
        return

    for pdf_path in normalized_targets:
        logger.info("Processing %s", pdf_path.resolve())
        dataset = build_dataset(pdf_path)
        save_dataset(dataset, output_dir)


if __name__ == "__main__":
    main()


