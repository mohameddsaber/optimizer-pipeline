"""Normalization helpers for deterministic Phase 2 reconciliation."""

import re
from typing import Callable, Iterable, List, Optional, TypeVar

T = TypeVar("T")

_SPACE_RE = re.compile(r"\s+")
_PHONE_KEEP_RE = re.compile(r"[^\d+]")
_URL_PREFIX_RE = re.compile(r"(?i)^https?://")
_WWW_PREFIX_RE = re.compile(r"(?i)^www\.")


def normalize_text(text: str) -> str:
    """Collapse whitespace for stable comparisons."""

    if not text:
        return ""
    return _SPACE_RE.sub(" ", text).strip()


def normalize_skill(text: str) -> str:
    """Normalize a skill-like token for matching and dedupe."""

    normalized = normalize_text(text)
    return normalized.strip(" ,;|")


def normalize_url(text: str) -> str:
    """Normalize a URL-like string for stable comparison."""

    normalized = normalize_text(text).strip(" ,;|/")
    normalized = _URL_PREFIX_RE.sub("", normalized)
    normalized = _WWW_PREFIX_RE.sub("", normalized)
    return normalized.lower().rstrip("/")


def normalize_phone(text: str) -> str:
    """Normalize phone strings to a canonical digit-oriented form."""

    normalized = normalize_text(text)
    normalized = _PHONE_KEEP_RE.sub("", normalized)
    if normalized.startswith("++"):
        normalized = normalized[1:]
    return normalized


def normalize_location_string(text: str) -> str:
    """Normalize location strings conservatively."""

    normalized = normalize_text(text).strip(" ,;|")
    parts = [part.strip().title() for part in normalized.split(",") if part.strip()]
    return ", ".join(parts) if parts else normalized.title()


def dedupe_preserve_order(
    values: Iterable[T], key_fn: Optional[Callable[[T], str]] = None
) -> List[T]:
    """Dedupe values while preserving the first-seen ordering."""

    seen = set()
    deduped: List[T] = []
    for value in values:
        key = key_fn(value) if key_fn is not None else str(value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped
