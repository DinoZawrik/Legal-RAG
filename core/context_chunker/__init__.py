"""Utility components for the Context-Aware chunker."""

from .definitions import ChunkPriority, ChunkBoundary, ProtectedZone, SmartChunk
from .protected_zones import ProtectedZoneAnalyzer
from .boundary_optimizer import BoundaryOptimizer, default_boundary_patterns
from .chunk_builder import SmartChunkBuilder

__all__ = [
    "ChunkPriority",
    "ChunkBoundary",
    "ProtectedZone",
    "SmartChunk",
    "ProtectedZoneAnalyzer",
    "BoundaryOptimizer",
    "default_boundary_patterns",
    "SmartChunkBuilder",
]
