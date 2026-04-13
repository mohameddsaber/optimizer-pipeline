"""Validated CV contracts for Phase 2."""

from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

FieldSource = Literal["phase2_input", "parser", "optimizer", "merged", "unresolved"]


class ReconciledField(BaseModel, Generic[T]):
    """A deterministic reconciliation result for one field."""

    model_config = ConfigDict(extra="forbid")

    value: Optional[T] = None
    source: FieldSource = "unresolved"
    confidence: float = 0.0
    notes: List[str] = Field(default_factory=list)
    grounded: bool = False


class ValidatedExperienceEntry(BaseModel):
    """Deterministic validated experience entry."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    organization: Optional[str] = None
    date_range: Optional[str] = None
    description: str = ""
    source: FieldSource = "unresolved"
    grounded: bool = False
    notes: List[str] = Field(default_factory=list)


class ValidatedProjectEntry(BaseModel):
    """Deterministic validated project entry."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    date_range: Optional[str] = None
    description: str = ""
    technologies: List[str] = Field(default_factory=list)
    source: FieldSource = "unresolved"
    grounded: bool = False
    notes: List[str] = Field(default_factory=list)


class ValidatedEducationEntry(BaseModel):
    """Deterministic validated education entry."""

    model_config = ConfigDict(extra="forbid")

    institution: Optional[str] = None
    degree: Optional[str] = None
    date_range: Optional[str] = None
    description: str = ""
    source: FieldSource = "unresolved"
    grounded: bool = False
    notes: List[str] = Field(default_factory=list)


class ValidatedTrainingEntry(BaseModel):
    """Deterministic validated training/course entry."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    provider: Optional[str] = None
    date_range: Optional[str] = None
    description: str = ""
    source: FieldSource = "unresolved"
    grounded: bool = False
    notes: List[str] = Field(default_factory=list)


class ValidatedCv(BaseModel):
    """Stable validated CV artifact for the current Phase 2 milestone."""

    model_config = ConfigDict(extra="forbid")

    name: ReconciledField[str]
    email: ReconciledField[str]
    phone_number: ReconciledField[str]
    location: ReconciledField[str]
    linkedin: ReconciledField[str]
    github: ReconciledField[str]
    technical_skills: ReconciledField[List[str]]
    languages: ReconciledField[List[str]]
    certifications: ReconciledField[List[str]]
    experience: ReconciledField[List[ValidatedExperienceEntry]]
    projects: ReconciledField[List[ValidatedProjectEntry]]
    education: ReconciledField[List[ValidatedEducationEntry]]
    trainings_courses: ReconciledField[List[ValidatedTrainingEntry]]
