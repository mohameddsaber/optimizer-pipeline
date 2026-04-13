"""Phase 2 coverage-mode output contract."""

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field


class CoverageAudit(BaseModel):
    """Audit payload describing what coverage mode recovered or patched."""

    model_config = ConfigDict(extra="forbid")

    recovered_items: List[str] = Field(default_factory=list)
    recovered_fields: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class ValidatedCv(BaseModel):
    """Coverage-mode Phase 2 output preserving optimizer schema plus coverage fields."""

    model_config = ConfigDict(extra="forbid")

    data: Dict[str, Any] = Field(default_factory=dict)
    audit: CoverageAudit = Field(default_factory=CoverageAudit)
    mode: Literal["coverage"] = "coverage"
