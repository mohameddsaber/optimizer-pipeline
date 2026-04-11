"""Deterministic semantic classification for normalized CV blocks."""

import re
from typing import List

from extraction.models import NormalizedBlock, SemanticBlock
from extraction.normalize import normalize_text

_DATE_RE = re.compile(
    r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|present|current|\d{4})\b"
)
_LOCATION_RE = re.compile(
    r"(?i)\b(?:remote|hybrid|onsite|cairo|giza|alexandria|egypt|ksa|saudi|dubai|uae|riyadh|jeddah)\b"
)
_EMAIL_RE = re.compile(r"[\w.\-+%]+@[\w.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_URL_RE = re.compile(r"(?i)\b(?:linkedin|github|portfolio|www\.|https?://)")
_HEADING_LOOKUP = {
    "summary",
    "profile",
    "objective",
    "experience",
    "work experience",
    "employment",
    "professional experience",
    "education",
    "projects",
    "technical skills",
    "skills",
    "certifications",
    "languages",
    "training",
    "courses",
    "activities",
    "achievements",
}


def classify_blocks(normalized_blocks: List[NormalizedBlock]) -> List[SemanticBlock]:
    """Assign deterministic semantic labels to normalized blocks."""

    semantic_blocks: List[SemanticBlock] = []
    for index, block in enumerate(normalized_blocks):
        label, hints = _classify_block(block, index, normalized_blocks)
        semantic_blocks.append(
            SemanticBlock(
                block_id=block.block_id,
                page_number=block.page_number,
                bbox=block.bbox,
                text=block.text,
                original_text=block.original_text,
                source_block_ids=block.source_block_ids,
                label=label,
                hints=hints,
            )
        )
    return semantic_blocks


def _classify_block(
    block: NormalizedBlock, index: int, blocks: List[NormalizedBlock]
) -> tuple:
    text = normalize_text(block.text)
    lowered = text.rstrip(":").lower()
    hints: List[str] = []

    if not text:
        return ("other", hints)
    if _is_section_heading(text):
        hints.append("known_section_heading")
        return ("section_heading", hints)
    if _looks_like_skills_line(text):
        hints.append("skills_delimiter_pattern")
        return ("skills_line", hints)
    if _is_contact_line(text, block, index):
        hints.append("contact_pattern")
        return ("contact_line", hints)
    if _is_bullet(text):
        hints.append("bullet_marker")
        return ("bullet", hints)
    if _looks_like_date(text):
        hints.append("date_pattern")
        return ("date", hints)
    if _looks_like_location(text):
        hints.append("location_pattern")
        return ("location", hints)
    if _looks_like_heading(text, lowered, block, blocks):
        hints.append("visual_heading")
        return ("heading", hints)
    if len(text.split()) >= 4:
        hints.append("paragraph_length")
        return ("paragraph", hints)
    return ("other", hints)


def _is_section_heading(text: str) -> bool:
    normalized = normalize_text(text).rstrip(":").lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized in _HEADING_LOOKUP


def _is_contact_line(text: str, block: NormalizedBlock, index: int) -> bool:
    has_contact_token = bool(_EMAIL_RE.search(text) or _PHONE_RE.search(text) or _URL_RE.search(text))
    near_top = block.bbox is not None and block.bbox[1] < 160
    return has_contact_token and (near_top or index <= 2)


def _is_bullet(text: str) -> bool:
    return text[:1] in {"•", "-", "*", "▪", "◦", "–"}


def _looks_like_date(text: str) -> bool:
    return bool(_DATE_RE.search(text)) and len(text.split()) <= 8


def _looks_like_location(text: str) -> bool:
    return bool(_LOCATION_RE.search(text)) and len(text.split()) <= 6


def _looks_like_skills_line(text: str) -> bool:
    if _EMAIL_RE.search(text) or _PHONE_RE.search(text) or _URL_RE.search(text):
        return False
    delimiters = text.count("|") + text.count("•") + text.count(",")
    return delimiters >= 2 and len(text.split()) <= 20


def _looks_like_heading(
    text: str, lowered: str, block: NormalizedBlock, blocks: List[NormalizedBlock]
) -> bool:
    words = text.split()
    if len(words) > 8:
        return False
    if text == text.upper() and len(words) <= 6:
        return True
    if text == text.title() and len(words) <= 4:
        return True
    if block.bbox is not None and block.bbox[0] < 120 and len(words) <= 4 and text.endswith(":"):
        return True
    return lowered in _HEADING_LOOKUP
