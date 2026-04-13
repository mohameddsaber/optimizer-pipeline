"""Shared contract primitives for the Phase 1 -> Phase 2 boundary."""

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "phase2-input-v1"
CANONICAL_SECTION_NAMES = (
    "Header",
    "Summary",
    "Experience",
    "Skills",
    "Projects",
    "Education",
    "Certifications",
    "Courses",
    "Achievements",
    "Languages",
    "Additional Information",
)


class LightweightEntryCandidate(BaseModel):
    """Stable lightweight candidate unit for downstream reconciliation."""

    model_config = ConfigDict(extra="forbid")

    text: str
    source_section: str
    hints: Dict[str, Any] = Field(default_factory=dict)


class ContactCandidateMap(BaseModel):
    """Structured candidate pools for likely contact fields."""

    model_config = ConfigDict(extra="forbid")

    name: List[str] = Field(default_factory=list)
    email: List[str] = Field(default_factory=list)
    phone: List[str] = Field(default_factory=list)
    location: List[str] = Field(default_factory=list)
    linkedin: List[str] = Field(default_factory=list)
    github: List[str] = Field(default_factory=list)
