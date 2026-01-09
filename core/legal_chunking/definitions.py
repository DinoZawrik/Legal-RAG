"""Core dataclasses and enumerations for legal chunking."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from ..legal_ontology import DocumentType, LegalDomain


class StructureLevel(Enum):
    """Hierarchy levels recognised in Russian legal documents."""

    DOCUMENT = "document"
    CHAPTER = "chapter"
    SECTION = "section"
    ARTICLE = "article"
    PARAGRAPH = "paragraph"
    SUBPARAGRAPH = "subparagraph"
    ITEM = "item"


@dataclass
class LegalStructureMetadata:
    """Metadata describing the structural context of a chunk."""

    structure_level: StructureLevel
    article_number: Optional[str] = None
    paragraph_number: Optional[str] = None
    subparagraph_number: Optional[str] = None
    item_number: Optional[str] = None
    chapter_title: Optional[str] = None
    section_title: Optional[str] = None
    parent_context: Optional[str] = None
    children_count: int = 0
    hierarchy_path: List[str] = field(default_factory=list)


@dataclass
class LegalChunk:
    """Rich chunk representation with legal metadata."""

    content: str
    structure_metadata: LegalStructureMetadata
    document_type: DocumentType
    legal_domain: LegalDomain
    references: List[str]
    key_terms: List[str]
    start_position: int
    end_position: int
    chunk_id: str
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: List[str] = field(default_factory=list)
