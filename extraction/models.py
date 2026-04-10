"""Pydantic models for raw PDF extraction output."""

from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


BlockKind = Literal["paragraph", "heading", "bullet", "table", "other"]
BBox = Tuple[float, float, float, float]


class RawTextBlock(BaseModel):
    """A single text block extracted from a PDF page."""

    model_config = ConfigDict(extra="forbid")

    text: str
    page_number: int
    bbox: Optional[BBox] = None
    kind: BlockKind


class RawPageExtraction(BaseModel):
    """Raw text and text blocks for one PDF page."""

    model_config = ConfigDict(extra="forbid")

    page_number: int
    text: str
    blocks: List[RawTextBlock] = Field(default_factory=list)


class RawSection(BaseModel):
    """Best-effort section split derived from page content."""

    model_config = ConfigDict(extra="forbid")

    heading: str
    content: str
    source_pages: List[int] = Field(default_factory=list)


class RawPdfExtraction(BaseModel):
    """Final raw extraction payload for a PDF document."""

    model_config = ConfigDict(extra="forbid")

    full_text: str
    pages: List[RawPageExtraction] = Field(default_factory=list)
    sections: List[RawSection] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
