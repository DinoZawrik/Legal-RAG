#!/usr/bin/env python3
"""Extract structured article data from PDF versions of Russian federal laws.

The script reads one or more PDF files (typically 115-ФЗ и 224-ФЗ),
parses article headers of the form ``Статья N. Название`` and emits a
JSON dataset with law metadata plus article bodies.  The resulting JSON is
used later for seeding Neo4j and for aligning retrieval answers with
ground-truth citations.

Usage::

    python scripts/graph/build_law_dataset.py --output-dir data/laws \
        "файлы_для_теста/Федеральный закон от 21.07.2005 N 115-ФЗ (ред. от 23.07.2025).pdf" \
        "файлы_для_теста/Федеральный закон от 13.07.2015 N 224-ФЗ (ред. от 31.07.2025 (1)).pdf"

The script is idempotent and can be re-run whenever updated PDF versions are
added.  Article text is trimmed of extra whitespace but otherwise kept intact
to preserve legal wording for downstream QA checks.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

import PyPDF2
from pdfminer.high_level import extract_text
import pdfplumber


logger = logging.getLogger(__name__)


ARTICLE_HEADER_PATTERN = re.compile(r"Статья\s+(\d+[\.\d]*)\.\s*(.*)")
SECTION_HEADER_PATTERN = re.compile(r"Глава\s+(\d+[\.\d]*)\.?\s*(.*)", re.IGNORECASE)
PART_HEADER_PATTERN = re.compile(r"Часть\s+(\d+[\.\d]*)\.?\s*(.*)")
ARTICLE_START_PATTERN = re.compile(r"Статья\s+(\d+[\.\d]*)\.\s*(.*)", re.IGNORECASE)


@dataclass
class ArticleRecord:
    """Structured representation of a single law article."""

    number: str
    title: str
    text: str
    chapter: Optional[str] = None
    chapter_title: Optional[str] = None


@dataclass
class LawDataset:
    """Resulting dataset for a law."""

    law_number: str
    law_title: str
    adoption_date: Optional[str]
    source_pdf: str
    articles: List[ArticleRecord]


def _extract_text(pdf_path: Path) -> str:
    """Extract plain text from PDF using pdfplumber for Cyrillic support."""
    logger.info("Reading PDF: %s", pdf_path)
    lines = []
    with pdf_path.open('rb') as fh:
        with pdfplumber.open(fh) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ''
                lines.append(text)
    normalized = '\n'.join(line.strip() for line in lines if line)
    logger.info("Extracted %s characters", len(normalized))
    return normalized


def _guess_law_number(filename: str) -> Optional[str]:
    match = re.search(r"(\d{3})-ФЗ", filename)
    if match:
        return f"{match.group(1)}-ФЗ"
    return None


def _guess_law_title(filename: str) -> Optional[str]:
    # crude heuristic: take substring after law number marker
    marker = "Федеральный закон"
    if marker in filename:
        trailing = filename.split(marker, 1)[-1]
        return (marker + trailing).replace(".pdf", "").strip()
    return None


def _split_articles(full_text: str) -> List[ArticleRecord]:
    records: List[ArticleRecord] = []

    matches = list(ARTICLE_START_PATTERN.finditer(full_text))
    if not matches:
        logger.warning("No article headers detected in text")
        return records

    for idx, match in enumerate(matches):
        number = match.group(1)
        title = match.group(2).strip()

        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()

        # Determine chapter context prior to this article header
        preceding_text = full_text[:match.start()]
        chapter_matches = list(SECTION_HEADER_PATTERN.finditer(preceding_text))
        chapter_number = chapter_matches[-1].group(1) if chapter_matches else None
        chapter_title = chapter_matches[-1].group(2).strip() if chapter_matches and chapter_matches[-1].group(2) else None

        records.append(
            ArticleRecord(
                number=number,
                title=title,
                text=body,
                chapter=chapter_number,
                chapter_title=chapter_title,
            )
        )

    return records


def build_dataset(pdf_path: Path) -> LawDataset:
    text = _extract_text(pdf_path)
    articles = _split_articles(text)

    law_number = _guess_law_number(pdf_path.name) or "unknown"
    law_title = _guess_law_title(pdf_path.name) or pdf_path.stem

    # Attempt to detect adoption date pattern YYYY-MM-DD
    adoption_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", pdf_path.name)
    adoption_date = None
    if adoption_match:
        parts = adoption_match.group(1).split(".")
        adoption_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

    logger.info(
        "Parsed dataset: law=%s, articles=%s", law_number, len(articles)
    )

    return LawDataset(
        law_number=law_number,
        law_title=law_title,
        adoption_date=adoption_date,
        source_pdf=str(pdf_path),
        articles=articles,
    )


def save_dataset(dataset: LawDataset, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = dataset.law_number.replace("/", "-") if dataset.law_number != "unknown" else Path(dataset.source_pdf).stem
    output_path = output_dir / f"{filename.lower()}_articles.json"

    payload = asdict(dataset)
    payload["articles"] = [asdict(article) for article in dataset.articles]

    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)

    logger.info("Saved dataset to %s", output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract articles from law PDFs")
    parser.add_argument("pdfs", nargs="*", type=Path, help="Paths to law PDFs")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/laws"),
        help="Directory to store JSON datasets",
    )
    parser.add_argument(
        "--pdf",
        dest="single_pdf",
        type=Path,
        help="Single PDF path (alternative to positional list)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    pdf_list = list(args.pdfs)
    if args.single_pdf:
        pdf_list.append(args.single_pdf)
    if not pdf_list:
        logger.error("No PDF files provided")
        return

    generated_paths: List[Path] = []
    for pdf in pdf_list:
        if not pdf.exists():
            logger.error("PDF not found: %s", pdf)
            continue

        dataset = build_dataset(pdf)
        output_path = save_dataset(dataset, args.output_dir)
        generated_paths.append(output_path)

    if generated_paths:
        logger.info("Generated %d dataset(s)" % len(generated_paths))
    else:
        logger.warning("No datasets generated")


if __name__ == "__main__":
    main()


