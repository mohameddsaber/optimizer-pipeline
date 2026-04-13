"""Normalization helpers for extracted CV blocks and text."""

import re
from typing import List, Optional

from extractor.models import BBox, NormalizedBlock, RawTextBlock

_LINE_ENDINGS_RE = re.compile(r"\r\n?|\u2028|\u2029")
_SPACE_RE = re.compile(r"[^\S\n]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_BULLET_MARKERS = ("•", "-", "*", "▪", "◦", "–")
_SECTION_HEADINGS = {
    "header",
    "contact",
    "personal information",
    "summary",
    "profile",
    "professional summary",
    "objective",
    "about me",
    "experience",
    "work experience",
    "employment",
    "professional experience",
    "career history",
    "education",
    "academic background",
    "qualifications",
    "education and training",
    "education and qualifications",
    "projects",
    "technical skills",
    "skills",
    "core competencies",
    "competencies",
    "tech stack",
    "technologies",
    "certifications",
    "certificates",
    "licenses",
    "credentials",
    "languages",
    "training",
    "trainings",
    "courses",
    "activities",
    "achievements",
    "additional information",
    "additional info",
    "interests",
    "extracurricular activities",
    "volunteer work",
}


def normalize_text(text: str) -> str:
    """Normalize whitespace while preserving meaningful CV line structure."""

    if not text:
        return ""

    normalized = _LINE_ENDINGS_RE.sub("\n", text)
    lines: List[str] = []
    for raw_line in normalized.split("\n"):
        line = _SPACE_RE.sub(" ", raw_line).strip()
        if not line:
            lines.append("")
            continue
        for marker in _BULLET_MARKERS:
            if line.startswith(marker):
                remainder = line[len(marker) :].strip()
                line = marker if not remainder else "{0} {1}".format(marker, remainder)
                break
        lines.append(line)

    normalized = "\n".join(lines)
    normalized = _BLANK_LINES_RE.sub("\n\n", normalized)
    return normalized.strip()


def normalize_blocks(raw_blocks: List[RawTextBlock]) -> List[NormalizedBlock]:
    """Merge fragmented raw blocks into logical blocks without dropping text."""

    normalized_blocks: List[NormalizedBlock] = []
    current_group: List[RawTextBlock] = []
    merged_index = 0

    for block in sorted(raw_blocks, key=_sort_key):
        if not current_group:
            current_group = [block]
            continue

        if _should_merge(current_group, block):
            current_group.append(block)
            continue

        normalized_blocks.append(_build_normalized_block(current_group, merged_index))
        merged_index += 1
        current_group = [block]

    if current_group:
        normalized_blocks.append(_build_normalized_block(current_group, merged_index))

    return normalized_blocks


def _sort_key(block: RawTextBlock) -> tuple:
    x0, y0 = _bbox_origin(block.bbox)
    return (block.page_number, round(y0, 2), round(x0, 2), block.block_id)


def _should_merge(group: List[RawTextBlock], next_block: RawTextBlock) -> bool:
    previous = group[-1]
    if previous.page_number != next_block.page_number:
        return False
    if _looks_like_standalone_section_heading(next_block.text):
        return False
    if previous.bbox is None or next_block.bbox is None:
        return _is_textual_continuation(previous.text, next_block.text)

    prev_x0, prev_y0, prev_x1, prev_y1 = previous.bbox
    next_x0, next_y0, next_x1, next_y1 = next_block.bbox
    vertical_gap = next_y0 - prev_y1
    same_column = abs(next_x0 - prev_x0) <= 8
    similar_width = abs((next_x1 - next_x0) - (prev_x1 - prev_x0)) <= 80
    indented_continuation = next_x0 >= prev_x0 and (next_x0 - prev_x0) <= 28

    if _is_bullet_start(previous.text):
        return vertical_gap <= 20 and (same_column or indented_continuation)

    if _looks_like_section_heading(previous.text):
        return False

    if _looks_like_header_line(group):
        return vertical_gap <= 10 and same_column

    if vertical_gap > 18:
        return False

    if _ends_with_hard_stop(previous.text):
        return False

    return (same_column and similar_width) or indented_continuation or _is_textual_continuation(
        previous.text, next_block.text
    )


def _build_normalized_block(group: List[RawTextBlock], merged_index: int) -> NormalizedBlock:
    source_texts = [block.text for block in group]
    normalized_pieces: List[str] = []

    for index, block in enumerate(group):
        text = normalize_text(block.text)
        if index == 0:
            normalized_pieces.append(text)
            continue

        previous_text = normalized_pieces[-1]
        joiner = " "
        if _is_bullet_start(group[0].text):
            joiner = " "
        elif _looks_like_header_line(group):
            joiner = " | "
        elif _starts_like_sentence(text):
            joiner = " "
        normalized_pieces[-1] = previous_text + joiner + text

    text = normalize_text("".join(normalized_pieces))
    bbox = _merge_bbox([block.bbox for block in group if block.bbox is not None])
    block_id = "norm-{0}-{1}".format(group[0].page_number, merged_index)
    inferred_kind = _infer_kind(text)
    return NormalizedBlock(
        block_id=block_id,
        page_number=group[0].page_number,
        bbox=bbox,
        text=text,
        original_text="\n".join(source_texts),
        source_block_ids=[block.block_id for block in group],
        source_texts=source_texts,
        inferred_kind=inferred_kind,
    )


def _infer_kind(text: str) -> str:
    if _is_bullet_start(text):
        return "bullet"
    if "|" in text and len(text.split("|")) >= 2:
        return "table"
    if len(text.split()) >= 4:
        return "paragraph"
    return "heading" if text.isupper() else "other"


def _bbox_origin(bbox: Optional[BBox]) -> tuple:
    if bbox is None:
        return (0.0, 0.0)
    return (bbox[0], bbox[1])


def _merge_bbox(boxes: List[BBox]) -> Optional[BBox]:
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _is_bullet_start(text: str) -> bool:
    normalized = normalize_text(text)
    return bool(normalized) and normalized[0] in _BULLET_MARKERS


def _is_textual_continuation(previous_text: str, next_text: str) -> bool:
    previous = normalize_text(previous_text)
    current = normalize_text(next_text)
    if not previous or not current:
        return False
    if _is_bullet_start(previous):
        return True
    return not _ends_with_hard_stop(previous) and current[:1].islower()


def _ends_with_hard_stop(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized.endswith((".", "!", "?", ";", ":"))


def _starts_like_sentence(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    return normalized[:1].isalnum()


def _looks_like_header_line(group: List[RawTextBlock]) -> bool:
    if not group:
        return False
    first_text = normalize_text(group[0].text)
    return bool(first_text) and len(first_text.split()) <= 5 and not _is_bullet_start(first_text)


def _looks_like_section_heading(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", normalize_text(text).rstrip(":").lower())
    return normalized in _SECTION_HEADINGS


def _looks_like_standalone_section_heading(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized or "\n" in normalized:
        return False
    candidate = re.sub(r"\s+", " ", normalized.rstrip(":").lower())
    if candidate in _SECTION_HEADINGS:
        return True
    word_count = len(candidate.split())
    return word_count <= 4 and normalized == normalized.upper() and candidate not in {"gpa", "nti"}
