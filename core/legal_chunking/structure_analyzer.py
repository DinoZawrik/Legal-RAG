"""Document structure analysis utilities for legal chunking."""

import re
from typing import Any, Dict, List, Optional

from .definitions import LegalStructureMetadata, StructureLevel


class DocumentStructureAnalyzer:
    """Detects hierarchical elements and produces structural metadata."""

    def __init__(self, structure_patterns: Dict[StructureLevel, List[str]]) -> None:
        self.structure_patterns = structure_patterns

    def analyze(self, text: str) -> Dict[int, Dict[str, Any]]:
        """Build a map of structural elements indexed by line number."""

        structure_map: Dict[int, Dict[str, Any]] = {}
        lines = text.split("\n")

        current_chapter: Optional[Dict[str, Any]] = None
        current_section: Optional[Dict[str, Any]] = None
        current_article: Optional[Dict[str, Any]] = None

        for line_num, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line:
                continue

            for level, patterns in self.structure_patterns.items():
                match = self._match_any(patterns, line)
                if not match:
                    continue

                groups = match.groups()
                structure_info: Dict[str, Any] = {
                    "level": level,
                    "line_number": line_num,
                    "text": line,
                    "number": groups[0] if groups else None,
                    "title": groups[1] if len(groups) > 1 else None,
                }

                if level == StructureLevel.CHAPTER:
                    current_chapter = structure_info
                    current_section = None
                    current_article = None
                elif level == StructureLevel.SECTION:
                    current_section = structure_info
                    current_article = None
                elif level == StructureLevel.ARTICLE:
                    current_article = structure_info

                structure_info["parent_chapter"] = current_chapter
                structure_info["parent_section"] = current_section
                structure_info["parent_article"] = current_article

                structure_map[line_num] = structure_info
                break

        return structure_map

    def extract_metadata(
        self,
        segment: str,
        position: int,
        structure_map: Dict[int, Dict[str, Any]],
    ) -> LegalStructureMetadata:
        """Create structural metadata for the given segment."""

        closest_structure: Optional[Dict[str, Any]] = None
        min_distance = float("inf")

        for line_num, info in structure_map.items():
            distance = abs(position - line_num * 50)
            if distance < min_distance:
                min_distance = distance
                closest_structure = info

        if closest_structure:
            level: StructureLevel = closest_structure["level"]
            hierarchy_path = self._build_hierarchy_path(closest_structure)

            return LegalStructureMetadata(
                structure_level=level,
                article_number=closest_structure.get("number")
                if level == StructureLevel.ARTICLE
                else None,
                chapter_title=closest_structure.get("title")
                if level == StructureLevel.CHAPTER
                else None,
                section_title=closest_structure.get("title")
                if level == StructureLevel.SECTION
                else None,
                hierarchy_path=hierarchy_path,
            )

        return self._infer_structure_from_content(segment)

    def _match_any(self, patterns: List[str], line: str) -> Optional[re.Match[str]]:
        for pattern in patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                return match
        return None

    def _build_hierarchy_path(self, structure_info: Dict[str, Any]) -> List[str]:
        path: List[str] = []

        chapter = structure_info.get("parent_chapter")
        if chapter:
            path.append(
                f"Глава {chapter.get('number', '')}: {chapter.get('title', '')}"
            )

        section = structure_info.get("parent_section")
        if section:
            path.append(
                f"Раздел {section.get('number', '')}: {section.get('title', '')}"
            )

        article = structure_info.get("parent_article")
        if article:
            path.append(f"Статья {article.get('number', '')}")

        return path

    def _infer_structure_from_content(self, segment: str) -> LegalStructureMetadata:
        lines = segment.split("\n")
        first_line = lines[0].strip() if lines else ""

        for level, patterns in self.structure_patterns.items():
            for pattern in patterns:
                match = re.match(pattern, first_line, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    article_number = (
                        groups[0]
                        if level == StructureLevel.ARTICLE and groups
                        else None
                    )
                    return LegalStructureMetadata(
                        structure_level=level,
                        article_number=article_number,
                    )

        return LegalStructureMetadata(structure_level=StructureLevel.PARAGRAPH)
