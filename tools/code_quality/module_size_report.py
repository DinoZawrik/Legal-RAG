"""Утилита для контроля размера Python-файлов.

Запуск:

```
python -m tools.code_quality.module_size_report --threshold 350
```

Выводит таблицу файлов, превышающих заданный порог по количеству строк.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Tuple


def iter_python_files(base: Path) -> Iterable[Path]:
    for path in base.rglob("*.py"):
        if any(part.startswith(".") for part in path.relative_to(base).parts):
            continue
        yield path


def count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as file:
            return sum(1 for _ in file)
    except OSError:
        return 0


def collect(base: Path, threshold: int) -> Iterable[Tuple[int, Path]]:
    for path in iter_python_files(base):
        lines = count_lines(path)
        if lines >= threshold:
            yield lines, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Report python modules exceeding line threshold")
    parser.add_argument(
        "--threshold",
        type=int,
        default=350,
        help="Максимальное допустимое количество строк в модуле (по умолчанию 350)",
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=Path.cwd(),
        help="Корень проекта (по умолчанию текущая директория)",
    )
    args = parser.parse_args()

    records = sorted(collect(args.base, args.threshold), reverse=True)

    if not records:
        print(f"All python files are shorter than {args.threshold} lines")
        return

    print(f"Files longer than {args.threshold} lines:")
    for lines, path in records:
        print(f"{lines:5d} {path.relative_to(args.base)}")


if __name__ == "__main__":
    main()
