"""Boundary selection utilities for the context-aware chunker."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Tuple

from .definitions import ChunkBoundary, ProtectedZone


def default_boundary_patterns() -> List[Tuple[str, float]]:
    """Return the default set of regex patterns used for boundary detection."""

    return [
        (r"\n\n+", 1.0),
        (r"\.[\s\n]+(?=[А-ЯЁ])", 0.95),
        (r";\s*\n", 0.9),
        (r"\.[\s]+(?=\d+\.)", 0.8),
        (r"\.\s*(?=[а-я]\))", 0.75),
        (r":\s*\n", 0.7),
        (r",\s+(?=[А-ЯЁ])", 0.6),
        (r"(?<=\.)\s+(?=[А-ЯЁ])", 0.55),
        (r"\s+(?=Статья|Глава|Раздел)", 0.8),
        (r"\s+", 0.3),
    ]


class BoundaryOptimizer:
    """Calculates safe chunk boundaries while preserving legal context."""

    def __init__(
        self,
        base_chunk_size: int,
        min_chunk_size: int,
        max_chunk_size: int,
        natural_boundaries: Optional[Sequence[Tuple[str, float]]] = None,
    ) -> None:
        self.base_chunk_size = base_chunk_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.natural_boundaries: Sequence[Tuple[str, float]] = (
            natural_boundaries if natural_boundaries is not None else default_boundary_patterns()
        )

    def find_optimal_boundaries(
        self,
        text: str,
        protected_zones: Iterable[ProtectedZone],
    ) -> List[ChunkBoundary]:
        protected = list(protected_zones)
        boundaries = [
            ChunkBoundary(
                position=0,
                boundary_type="document_start",
                quality_score=1.0,
                nearby_entities=[],
            )
        ]

        current_pos = 0
        text_length = len(text)

        while current_pos < text_length:
            target_pos = min(current_pos + self.base_chunk_size, text_length)
            boundary_pos = self._find_safe_boundary_near(text, target_pos, protected)

            if boundary_pos is None or boundary_pos <= current_pos:
                boundary_pos = self._force_boundary(text, target_pos, protected)

            if boundary_pos <= current_pos or boundary_pos >= text_length:
                break

            boundaries.append(
                ChunkBoundary(
                    position=boundary_pos,
                    boundary_type="natural"
                    if self._is_natural_boundary(text, boundary_pos)
                    else "forced",
                    quality_score=self._calculate_boundary_quality(text, boundary_pos, protected),
                    nearby_entities=[],
                )
            )
            current_pos = boundary_pos

        if boundaries[-1].position < text_length:
            boundaries.append(
                ChunkBoundary(
                    position=text_length,
                    boundary_type="document_end",
                    quality_score=1.0,
                    nearby_entities=[],
                )
            )

        return boundaries

    def _find_safe_boundary_near(
        self,
        text: str,
        target_pos: int,
        protected_zones: Sequence[ProtectedZone],
    ) -> Optional[int]:
        search_window = 200
        start_search = max(target_pos - search_window, 0)
        end_search = min(target_pos + search_window, len(text))

        candidate_boundaries: List[Tuple[int, float]] = []
        fragment = text[start_search:end_search]

        for pattern, quality in self.natural_boundaries:
            for match in re.finditer(pattern, fragment):
                abs_pos = start_search + match.end()
                if self._is_in_protected_zone(abs_pos, protected_zones):
                    continue
                if abs_pos - target_pos <= -self.min_chunk_size:
                    continue
                candidate_boundaries.append((abs_pos, quality))

        if not candidate_boundaries:
            return None

        def boundary_score(candidate: Tuple[int, float]) -> float:
            pos, quality = candidate
            distance_penalty = abs(pos - target_pos) / search_window
            return quality - distance_penalty * 0.5

        best_position, _ = max(candidate_boundaries, key=boundary_score)
        return best_position

    def _force_boundary(
        self,
        text: str,
        target_pos: int,
        protected_zones: Sequence[ProtectedZone],
    ) -> int:
        text_length = len(text)
        for zone in protected_zones:
            if zone.start_pos <= target_pos <= zone.end_pos:
                return min(zone.end_pos + 1, text_length)

        for i in range(target_pos, min(target_pos + 100, text_length)):
            if text[i] in {" ", "\n"}:
                return i + 1

        return min(target_pos, text_length)

    def _is_in_protected_zone(
        self,
        position: int,
        protected_zones: Sequence[ProtectedZone],
    ) -> bool:
        return any(zone.start_pos <= position <= zone.end_pos for zone in protected_zones)

    def _is_natural_boundary(self, text: str, position: int) -> bool:
        if position <= 0 or position >= len(text):
            return True

        context_before = text[max(0, position - 5) : position]
        context_after = text[position : min(len(text), position + 5)]
        context = context_before + context_after

        return any(re.search(pattern, context) for pattern, _ in self.natural_boundaries)

    def _calculate_boundary_quality(
        self,
        text: str,
        position: int,
        protected_zones: Sequence[ProtectedZone],
    ) -> float:
        quality = 0.5

        if self._is_natural_boundary(text, position):
            quality += 0.3

        min_distance = min(
            (min(abs(position - zone.start_pos), abs(position - zone.end_pos)) for zone in protected_zones),
            default=float("inf"),
        )
        if min_distance < 50:
            quality -= 0.2

        context = text[max(0, position - 20) : min(len(text), position + 20)]
        if re.search(r"(Статья|Глава|Раздел|Пункт)", context, re.IGNORECASE):
            quality += 0.2

        return max(0.0, min(1.0, quality))
