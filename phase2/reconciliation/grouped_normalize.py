"""Normalization helpers for grouped-entry reconciliation."""

import re
from typing import List

from phase2.reconciliation.normalize import normalize_text

_PUNCT_RE = re.compile(r"[^\w\s.+#/\-&]")
_DATE_SPACES_RE = re.compile(r"\s*[-–]\s*")
_TOKEN_RE = re.compile(r"[A-Za-z0-9+#/.]+")


def normalize_company_name(text: str) -> str:
    """Normalize a company or organization name conservatively."""

    return _normalize_identity_text(text)


def normalize_institution_name(text: str) -> str:
    """Normalize an institution name conservatively."""

    return _normalize_identity_text(text)


def normalize_project_name(text: str) -> str:
    """Normalize a project name conservatively."""

    return _normalize_identity_text(text)


def normalize_role_title(text: str) -> str:
    """Normalize a role title conservatively."""

    return _normalize_identity_text(text)


def normalize_date_range(text: str) -> str:
    """Normalize date range formatting for stable matching."""

    normalized = normalize_text(text).lower()
    normalized = _DATE_SPACES_RE.sub(" - ", normalized)
    return normalized


def normalize_description_text(text: str) -> str:
    """Normalize description text while preserving technical tokens."""

    return normalize_text(text)


def tokenize_identity_text(text: str) -> List[str]:
    """Tokenize identity text for deterministic overlap matching."""

    normalized = _normalize_identity_text(text)
    return [token for token in _TOKEN_RE.findall(normalized) if len(token) > 1]


def _normalize_identity_text(text: str) -> str:
    normalized = normalize_text(text).lower()
    normalized = _PUNCT_RE.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
