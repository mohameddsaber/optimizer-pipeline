"""Deterministic matching helpers for grouped entries."""

from typing import List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from phase2.reconciliation.grouped_normalize import (
    normalize_company_name,
    normalize_date_range,
    normalize_institution_name,
    normalize_project_name,
    normalize_role_title,
    tokenize_identity_text,
)


class ComparableGroupedEntry(BaseModel):
    """Comparable grouped entry representation used during matching."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    source: str
    raw_text: str
    primary_name: str = ""
    secondary_name: str = ""
    date_range: str = ""
    description: str = ""
    technologies: List[str] = Field(default_factory=list)
    hints: dict = Field(default_factory=dict)


class MatchResult(BaseModel):
    """Explicit grouped-entry match result."""

    model_config = ConfigDict(extra="forbid")

    matched: bool
    score: float
    reasons: List[str] = Field(default_factory=list)


def match_experience_entries(left: ComparableGroupedEntry, right: ComparableGroupedEntry) -> MatchResult:
    """Match two experience entries using conservative deterministic signals."""

    score, reasons = _base_match_score(
        normalize_company_name(left.secondary_name),
        normalize_company_name(right.secondary_name),
        normalize_role_title(left.primary_name),
        normalize_role_title(right.primary_name),
        left.date_range,
        right.date_range,
        left.raw_text,
        right.raw_text,
    )
    matched = score >= 5.0 and any(reason.startswith(("organization", "title", "token")) for reason in reasons)
    return MatchResult(matched=matched, score=score, reasons=reasons)


def match_project_entries(left: ComparableGroupedEntry, right: ComparableGroupedEntry) -> MatchResult:
    """Match two project entries."""

    score, reasons = _base_match_score(
        normalize_project_name(left.primary_name),
        normalize_project_name(right.primary_name),
        "",
        "",
        left.date_range,
        right.date_range,
        left.raw_text,
        right.raw_text,
    )
    tech_overlap = _token_overlap(left.technologies, right.technologies)
    if tech_overlap >= 0.5 and tech_overlap > 0:
        score += 1.0
        reasons.append("technology_overlap")
    matched = score >= 4.0 and any(reason.startswith(("name", "token")) for reason in reasons)
    return MatchResult(matched=matched, score=score, reasons=reasons)


def match_education_entries(left: ComparableGroupedEntry, right: ComparableGroupedEntry) -> MatchResult:
    """Match two education entries."""

    score, reasons = _base_match_score(
        normalize_institution_name(left.secondary_name),
        normalize_institution_name(right.secondary_name),
        normalize_role_title(left.primary_name),
        normalize_role_title(right.primary_name),
        left.date_range,
        right.date_range,
        left.raw_text,
        right.raw_text,
    )
    matched = score >= 5.0 and any(reason.startswith(("organization", "title", "token")) for reason in reasons)
    return MatchResult(matched=matched, score=score, reasons=reasons)


def match_training_entries(left: ComparableGroupedEntry, right: ComparableGroupedEntry) -> MatchResult:
    """Match two training/course entries."""

    score, reasons = _base_match_score(
        normalize_project_name(left.primary_name),
        normalize_project_name(right.primary_name),
        normalize_company_name(left.secondary_name),
        normalize_company_name(right.secondary_name),
        left.date_range,
        right.date_range,
        left.raw_text,
        right.raw_text,
    )
    matched = score >= 4.0 and any(reason.startswith(("name", "organization", "token")) for reason in reasons)
    return MatchResult(matched=matched, score=score, reasons=reasons)


def _base_match_score(
    primary_left: str,
    primary_right: str,
    secondary_left: str,
    secondary_right: str,
    date_left: str,
    date_right: str,
    raw_left: str,
    raw_right: str,
) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []

    if primary_left and primary_right and primary_left == primary_right:
        score += 4.0
        reasons.append("name_exact")
    elif _token_overlap(tokenize_identity_text(primary_left), tokenize_identity_text(primary_right)) >= 0.6:
        score += 2.5
        reasons.append("name_token_overlap")

    if secondary_left and secondary_right and secondary_left == secondary_right:
        score += 3.0
        reasons.append("organization_exact")
    elif _token_overlap(tokenize_identity_text(secondary_left), tokenize_identity_text(secondary_right)) >= 0.6:
        score += 2.0
        reasons.append("organization_token_overlap")

    date_overlap = _date_overlap(date_left, date_right)
    if date_overlap == 1.0:
        score += 2.0
        reasons.append("date_exact")
    elif date_overlap > 0.0:
        score += 1.0
        reasons.append("date_overlap")

    text_overlap = _token_overlap(tokenize_identity_text(raw_left), tokenize_identity_text(raw_right))
    if text_overlap >= 0.5:
        score += 1.5
        reasons.append("token_overlap")

    return score, reasons


def _date_overlap(left: str, right: str) -> float:
    normalized_left = normalize_date_range(left)
    normalized_right = normalize_date_range(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0
    left_tokens = set(tokenize_identity_text(normalized_left))
    right_tokens = set(tokenize_identity_text(normalized_right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / float(max(1, min(len(left_tokens), len(right_tokens))))


def _token_overlap(left: List[str], right: List[str]) -> float:
    if not left or not right:
        return 0.0
    left_set = set(left)
    right_set = set(right)
    return len(left_set & right_set) / float(max(1, min(len(left_set), len(right_set))))
