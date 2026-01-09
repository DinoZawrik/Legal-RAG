"""Logic for detecting protected spans inside legal documents."""

from __future__ import annotations

import logging
from typing import Iterable, List, Sequence

from ..universal_legal_ner import EntityType, UniversalLegalEntities
from .definitions import ProtectedZone

logger = logging.getLogger(__name__)


class ProtectedZoneAnalyzer:
    """Builds collections of spans that must not be split during chunking."""

    def __init__(self, protection_margin: int) -> None:
        self.protection_margin = protection_margin

    def identify_protected_zones(
        self,
        text: str,
        entities: UniversalLegalEntities,
    ) -> List[ProtectedZone]:
        protected_zones: List[ProtectedZone] = []

        for constraint in entities.numerical_constraints:
            start = max(0, constraint.start_pos - self.protection_margin)
            end = min(len(text), constraint.end_pos + self.protection_margin)
            protected_zones.append(
                ProtectedZone(
                    start_pos=start,
                    end_pos=end,
                    reason=f"Числовое ограничение: {constraint.value} {constraint.unit}",
                    entity_types=[EntityType.NUMERICAL_CONSTRAINT.value],
                    criticality=1.0,
                )
            )

        for definition in entities.definitions:
            start = max(0, definition.start_pos - 50)
            end = min(len(text), definition.end_pos + 50)
            protected_zones.append(
                ProtectedZone(
                    start_pos=start,
                    end_pos=end,
                    reason="Определение правового термина",
                    entity_types=[EntityType.DEFINITION_BLOCK.value],
                    criticality=0.9,
                )
            )

        for group in self._group_sequential_procedures(entities.procedure_steps):
            if len(group) <= 1:
                continue
            start = max(0, min(step.start_pos for step in group) - 30)
            end = min(len(text), max(step.end_pos for step in group) + 30)
            protected_zones.append(
                ProtectedZone(
                    start_pos=start,
                    end_pos=end,
                    reason=f"Процедурная последовательность ({len(group)} шагов)",
                    entity_types=[EntityType.PROCEDURE_STEP.value],
                    criticality=0.8,
                )
            )

        for group in self._group_related_authorities(entities.authority_modals):
            if len(group) <= 1:
                continue
            start = max(0, min(modal.start_pos for modal in group) - 30)
            end = min(len(text), max(modal.end_pos for modal in group) + 30)
            protected_zones.append(
                ProtectedZone(
                    start_pos=start,
                    end_pos=end,
                    reason=f"Связанные полномочия ({len(group)} элементов)",
                    entity_types=[EntityType.AUTHORITY_MODAL.value],
                    criticality=0.7,
                )
            )

        merged = self._merge_protected_zones(protected_zones)
        logger.debug("Protected zones detected: %s", len(merged))
        return merged

    def _group_sequential_procedures(self, procedure_steps: Sequence) -> List[List]:
        if not procedure_steps:
            return []

        sorted_steps = sorted(procedure_steps, key=lambda step: step.start_pos)
        groups: List[List] = []
        current_group: List = [sorted_steps[0]]

        for step in sorted_steps[1:]:
            if step.start_pos - current_group[-1].end_pos < 200:
                current_group.append(step)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [step]

        if current_group:
            groups.append(current_group)

        return groups

    def _group_related_authorities(self, authority_modals: Sequence) -> List[List]:
        if not authority_modals:
            return []

        groups: List[List] = []
        used: set[int] = set()

        for modal in authority_modals:
            modal_id = id(modal)
            if modal_id in used:
                continue

            related = [modal]
            used.add(modal_id)

            for other in authority_modals:
                other_id = id(other)
                if other_id in used:
                    continue
                if self._are_authorities_related(modal, other):
                    related.append(other)
                    used.add(other_id)

            if len(related) > 1:
                groups.append(related)

        return groups

    def _are_authorities_related(self, modal1, modal2) -> bool:
        similarity = self._calculate_text_similarity(modal1.subject, modal2.subject)
        distance = abs(modal1.start_pos - modal2.start_pos)
        return similarity > 0.7 and distance < 300

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union else 0.0

    def _merge_protected_zones(self, zones: Iterable[ProtectedZone]) -> List[ProtectedZone]:
        zone_list = list(zones)
        if not zone_list:
            return []

        sorted_zones = sorted(zone_list, key=lambda zone: zone.start_pos)
        merged: List[ProtectedZone] = [sorted_zones[0]]

        for current in sorted_zones[1:]:
            last = merged[-1]
            if current.start_pos <= last.end_pos + 50:
                merged[-1] = ProtectedZone(
                    start_pos=last.start_pos,
                    end_pos=max(last.end_pos, current.end_pos),
                    reason=f"{last.reason}; {current.reason}",
                    entity_types=list({*last.entity_types, *current.entity_types}),
                    criticality=max(last.criticality, current.criticality),
                )
            else:
                merged.append(current)

        return merged
