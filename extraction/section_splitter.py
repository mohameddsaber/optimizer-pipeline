"""Heading-driven section splitting for raw CV text."""

import re
from collections import OrderedDict
from typing import List

from extraction.models import RawPageExtraction, RawSection, RawTextBlock
from extraction.normalize import normalize_text

_KNOWN_HEADING_VARIANTS = (
    "summary",
    "profile",
    "objective",
    "experience",
    "work experience",
    "employment",
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
)
_NORMALIZED_HEADING_LOOKUP = {
    re.sub(r"\s+", " ", item.strip().lower()): item for item in _KNOWN_HEADING_VARIANTS
}
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z&/\-+]*")


def normalize_heading_candidate(text: str) -> str:
    """Return a normalized representation for heading matching."""

    candidate = normalize_text(text)
    candidate = candidate.rstrip(":")
    candidate = re.sub(r"\s+", " ", candidate)
    return candidate.strip().lower()


def is_heading_text(text: str) -> bool:
    """Return whether the line looks like a known CV section heading."""

    normalized = normalize_heading_candidate(text)
    return normalized in _NORMALIZED_HEADING_LOOKUP


def canonicalize_heading(text: str) -> str:
    """Map a heading candidate to a deterministic display form."""

    normalized = normalize_heading_candidate(text)
    canonical = _NORMALIZED_HEADING_LOOKUP.get(normalized)
    if canonical:
        return canonical.title()
    return normalize_text(text).rstrip(":")


def split_into_sections(pages: List[RawPageExtraction]) -> List[RawSection]:
    """Split extracted pages into best-effort sections using heading cues."""

    sections: List[RawSection] = []
    current_heading = "General"
    current_lines: List[str] = []
    current_pages = OrderedDict()

    def flush_current() -> None:
        if not current_lines:
            return
        content = normalize_text("\n".join(current_lines))
        if not content:
            return
        sections.append(
            RawSection(
                heading=current_heading,
                content=content,
                source_pages=list(current_pages.keys()),
            )
        )

    for page in pages:
        lines = _page_lines(page)
        for line in lines:
            if is_heading_text(line):
                flush_current()
                current_heading = canonicalize_heading(line)
                current_lines = []
                current_pages = OrderedDict()
                current_pages[page.page_number] = None
                continue

            if not line.strip():
                if current_lines and current_lines[-1]:
                    current_lines.append("")
                if current_lines:
                    current_pages[page.page_number] = None
                continue

            current_lines.append(line)
            current_pages[page.page_number] = None

    flush_current()
    return sections


def _page_lines(page: RawPageExtraction) -> List[str]:
    """Prefer block text ordering when available, otherwise fall back to page text."""

    if page.blocks:
        return [normalize_text(block.text) for block in page.blocks if normalize_text(block.text)]
    return [line for line in normalize_text(page.text).splitlines()]


def classify_heading_from_text(text: str) -> str:
    """Best-effort block classification helper for extractor heuristics."""

    normalized = normalize_text(text)
    if not normalized:
        return "other"
    if _looks_like_bullet(normalized):
        return "bullet"
    if is_heading_text(normalized) or _looks_like_visual_heading(normalized):
        return "heading"
    if _looks_like_table(normalized):
        return "table"
    if len(normalized.split()) >= 4:
        return "paragraph"
    return "other"


def _looks_like_bullet(text: str) -> bool:
    return text.startswith(("-", "*", "•", "▪", "◦", "–"))


def _looks_like_table(text: str) -> bool:
    separators = text.count("|") + text.count("\t")
    return separators >= 2


def _looks_like_visual_heading(text: str) -> bool:
    if "\n" in text:
        return False
    words = _WORD_RE.findall(text)
    if not words or len(words) > 4:
        return False
    letters_only = re.sub(r"[^A-Za-z]", "", text)
    if not letters_only:
        return False
    upper_ratio = sum(1 for char in letters_only if char.isupper()) / len(letters_only)
    title_like = text == text.title() and len(words) <= 3
    return upper_ratio > 0.8 or title_like


def classify_block_kind(block: RawTextBlock) -> str:
    """Classify an extracted block into a deterministic coarse type."""

    return classify_heading_from_text(block.text)
