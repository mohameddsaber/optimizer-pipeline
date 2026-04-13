"""Stable Phase 2 input contract."""

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from contracts.common import CONTRACT_VERSION
from contracts.common import ContactCandidateMap, LightweightEntryCandidate


class Phase2Input(BaseModel):
    """Content-oriented, Phase 2-facing adapter output."""

    model_config = ConfigDict(extra="forbid")

    contract_version: str = CONTRACT_VERSION
    full_text: str
    canonical_sections: Dict[str, str] = Field(default_factory=dict)
    uncategorized_text: str = ""
    contact_candidates: Dict[str, List[str]] = Field(default_factory=dict)
    skill_candidates: List[str] = Field(default_factory=list)
    language_candidates: List[str] = Field(default_factory=list)
    experience_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    project_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    education_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    certification_candidates: List[str] = Field(default_factory=list)
    training_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    diagnostics_flags: List[str] = Field(default_factory=list)
    source_metadata: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "Phase2Input",
    "ContactCandidateMap",
    "LightweightEntryCandidate",
]
