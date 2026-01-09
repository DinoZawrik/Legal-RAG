"""Segmentation utilities for legal documents."""

import re
from typing import Dict, List


class LegalSegmenter:
    """Splits legal documents into manageable segments preserving structure."""

    def __init__(self, base_chunk_size: int, min_chunk_size: int, max_chunk_size: int) -> None:
        self.base_chunk_size = base_chunk_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def split_by_structure(self, text: str, structure_map: Dict[int, Dict]) -> List[str]:
        lines = text.split("\n")
        segments: List[str] = []
        current_segment: List[str] = []

        structure_points = sorted(structure_map.keys())
        current_idx = 0

        for line_num, line in enumerate(lines):
            if current_idx < len(structure_points) and line_num == structure_points[current_idx]:
                if current_segment:
                    segment_text = "\n".join(current_segment).strip()
                    if len(segment_text) > self.min_chunk_size:
                        segments.append(segment_text)
                    current_segment = []
                current_idx += 1

            current_segment.append(line)

            current_text = "\n".join(current_segment)
            if len(current_text) > self.max_chunk_size:
                segments.extend(self._split_large_segment(current_text))
                current_segment = []

        if current_segment:
            segment_text = "\n".join(current_segment).strip()
            if len(segment_text) > self.min_chunk_size:
                segments.append(segment_text)

        return segments

    def split_by_sentences(self, text: str) -> List[str]:
        sentence_endings = r"[.!?]\s+(?=[А-ЯЁ])"
        sentences = re.split(sentence_endings, text)

        segments: List[str] = []
        current_segment = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            potential = f"{current_segment} {sentence}".strip() if current_segment else sentence

            if len(potential) <= self.base_chunk_size:
                current_segment = potential
                continue

            if current_segment:
                segments.append(current_segment.strip())

            if len(sentence) > self.max_chunk_size:
                segments.extend(self._split_large_segment(sentence))
                current_segment = ""
            else:
                current_segment = sentence

        if current_segment:
            segments.append(current_segment.strip())

        return segments

    def _split_large_segment(self, text: str) -> List[str]:
        parts = re.split(r"[;,]\s+", text)

        segments: List[str] = []
        current_segment = ""

        for part in parts:
            potential = f"{current_segment}, {part}" if current_segment else part

            if len(potential) <= self.base_chunk_size:
                current_segment = potential
                continue

            if current_segment:
                segments.append(current_segment.strip())

            if len(part) > self.max_chunk_size:
                segments.extend(self._split_by_words(part))
                current_segment = ""
            else:
                current_segment = part

        if current_segment:
            segments.append(current_segment.strip())

        return segments

    def _split_by_words(self, text: str) -> List[str]:
        words = text.split()
        segments: List[str] = []
        current_words: List[str] = []
        current_length = 0

        for word in words:
            word_length = len(word) + 1

            if current_length + word_length <= self.base_chunk_size:
                current_words.append(word)
                current_length += word_length
                continue

            if current_words:
                segments.append(" ".join(current_words))

            current_words = [word]
            current_length = len(word)

        if current_words:
            segments.append(" ".join(current_words))

        return segments
