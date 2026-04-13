"""Typed models for phase-1 CV PDF extraction."""

from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

BBox = Tuple[float, float, float, float]
RawBlockKind = Literal["paragraph", "heading", "bullet", "table", "other"]
SemanticLabel = Literal[
    "section_heading",
    "heading",
    "contact_line",
    "bullet",
    "paragraph",
    "date",
    "location",
    "skills_line",
    "other",
]


class RawTextBlock(BaseModel):
    """A low-level text block emitted directly by a PDF extractor."""

    model_config = ConfigDict(extra="forbid")

    block_id: str
    text: str
    page_number: int
    bbox: Optional[BBox] = None
    kind: RawBlockKind = "other"


class NormalizedBlock(BaseModel):
    """A logical block created by merging related raw blocks."""

    model_config = ConfigDict(extra="forbid")

    block_id: str
    page_number: int
    bbox: Optional[BBox] = None
    text: str
    original_text: str
    source_block_ids: List[str] = Field(default_factory=list)
    source_texts: List[str] = Field(default_factory=list)
    inferred_kind: RawBlockKind = "other"


class SemanticBlock(BaseModel):
    """A normalized block with a lightweight semantic label."""

    model_config = ConfigDict(extra="forbid")

    block_id: str
    page_number: int
    bbox: Optional[BBox] = None
    text: str
    original_text: str
    source_block_ids: List[str] = Field(default_factory=list)
    label: SemanticLabel
    hints: List[str] = Field(default_factory=list)


class RawPageExtraction(BaseModel):
    """Per-page extraction output and derived blocks."""

    model_config = ConfigDict(extra="forbid")

    page_number: int
    text: str
    blocks: List[RawTextBlock] = Field(default_factory=list)
    raw_blocks: List[RawTextBlock] = Field(default_factory=list)
    normalized_blocks: List[NormalizedBlock] = Field(default_factory=list)
    semantic_blocks: List[SemanticBlock] = Field(default_factory=list)


class RawSection(BaseModel):
    """Best-effort section constructed from sequential semantic blocks."""

    model_config = ConfigDict(extra="forbid")

    heading: str
    content: str
    source_pages: List[int] = Field(default_factory=list)
    block_ids: List[str] = Field(default_factory=list)


class SuspiciousBlock(BaseModel):
    """A diagnostic entry describing why a block looks suspicious."""

    model_config = ConfigDict(extra="forbid")

    block_id: str
    page_number: int
    reason: str
    text: str


class ExtractionDiagnostics(BaseModel):
    """Deterministic diagnostics for downstream validation and triage."""

    model_config = ConfigDict(extra="forbid")

    merged_block_count: int = 0
    unassigned_blocks: List[str] = Field(default_factory=list)
    suspicious_blocks: List[SuspiciousBlock] = Field(default_factory=list)
    section_count: int = 0
    general_block_ratio: float = 0.0
    possible_errors: List[str] = Field(default_factory=list)
    recovered_section_splits: int = 0
    fallback_used: bool = False


class RawPdfExtraction(BaseModel):
    """Top-level phase-1 extraction payload."""

    model_config = ConfigDict(extra="forbid")

    full_text: str
    pages: List[RawPageExtraction] = Field(default_factory=list)
    sections: List[RawSection] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_blocks: List[RawTextBlock] = Field(default_factory=list)
    normalized_blocks: List[NormalizedBlock] = Field(default_factory=list)
    semantic_blocks: List[SemanticBlock] = Field(default_factory=list)
    diagnostics: ExtractionDiagnostics = Field(default_factory=ExtractionDiagnostics)
