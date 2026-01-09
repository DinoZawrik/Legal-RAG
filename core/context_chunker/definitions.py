"""Core dataclasses and enums shared by the context-aware chunker modules."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..universal_legal_ner import UniversalLegalEntities


class ChunkPriority(Enum):
    """Represents the relative importance of a chunk for retrieval."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class ProtectedZone:
    """Span of text that must remain intact during chunking."""

    start_pos: int
    end_pos: int
    reason: str
    entity_types: List[str]
    criticality: float


@dataclass
class ChunkBoundary:
    """Candidate boundary for building smart chunks."""

    position: int
    boundary_type: str
    quality_score: float
    nearby_entities: List[str]


@dataclass
class SmartChunk:
    """Aggregated chunk enriched with legal metadata."""

    content: str
    start_pos: int
    end_pos: int
    chunk_index: int
    entities: UniversalLegalEntities
    priority: ChunkPriority
    criticality_score: float
    protected_zones: List[ProtectedZone]
    boundary_quality: float
    previous_chunk_overlap: Optional[str] = None
    next_chunk_overlap: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
