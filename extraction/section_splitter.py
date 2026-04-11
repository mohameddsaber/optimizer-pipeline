"""Section splitting over semantic blocks."""

import re
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from extraction.models import RawSection, SemanticBlock
from extraction.normalize import normalize_text

_SECTION_ALIASES = {
    "header": "Header",
    "contact": "Header",
    "personal information": "Header",
    "summary": "Summary",
    "profile": "Summary",
    "professional summary": "Summary",
    "objective": "Summary",
    "about me": "Summary",
    "experience": "Experience",
    "work experience": "Experience",
    "professional experience": "Experience",
    "employment": "Experience",
    "career history": "Experience",
    "skills": "Skills",
    "technical skills": "Skills",
    "core competencies": "Skills",
    "competencies": "Skills",
    "tech stack": "Skills",
    "technologies": "Skills",
    "projects": "Projects",
    "personal projects": "Projects",
    "academic projects": "Projects",
    "selected projects": "Projects",
    "relevant projects": "Projects",
    "education": "Education",
    "academic background": "Education",
    "qualifications": "Education",
    "education and training": "Education",
    "education and qualifications": "Education",
    "certifications": "Certifications",
    "certificates": "Certifications",
    "licenses": "Certifications",
    "credentials": "Certifications",
    "certifications and courses": "Courses",
    "certifications & courses": "Courses",
    "courses": "Courses",
    "training": "Courses",
    "trainings": "Courses",
    "workshops": "Courses",
    "achievements": "Achievements",
    "accomplishments": "Achievements",
    "awards": "Achievements",
    "honors": "Achievements",
    "languages": "Languages",
    "language proficiency": "Languages",
    "additional information": "Additional Information",
    "additional info": "Additional Information",
    "interests": "Additional Information",
    "activities": "Additional Information",
    "extracurricular activities": "Additional Information",
    "volunteer work": "Additional Information",
}
_PUNCT_TRAIL_RE = re.compile(r"[:\-–|]+$")
_SENTENCE_END_RE = re.compile(r"[.!?]$")
_HEADER_CANONICALS = {"Header", "General"}
_UPPERCASE_TOKEN_RE = re.compile(r"^[A-Z][A-Z\s/&-]{2,}$")


def normalize_section_heading(text: str) -> Optional[str]:
    """Map a heading alias to a canonical section name, if recognized."""

    normalized = _normalize_heading_text(text)
    if not normalized:
        return None
    if normalized in _SECTION_ALIASES:
        return _SECTION_ALIASES[normalized]
    compact = normalized.replace("&", "and")
    return _SECTION_ALIASES.get(compact)


def split_into_sections(semantic_blocks: List[SemanticBlock]) -> List[RawSection]:
    """Split semantic blocks into sequential sections."""

    sections, _ = split_into_sections_with_diagnostics(semantic_blocks)
    return sections


def split_into_sections_with_diagnostics(
    semantic_blocks: List[SemanticBlock],
) -> Tuple[List[RawSection], Dict[str, object]]:
    """Split semantic blocks into sections and expose collapse diagnostics."""

    if not semantic_blocks:
        return [], {
            "section_count": 0,
            "general_block_ratio": 0.0,
            "possible_errors": [],
            "recovered_section_splits": 0,
        }

    sections, section_blocks = _initial_split(semantic_blocks)
    recovery_count = 0
    possible_errors = _collect_section_errors(sections, semantic_blocks, section_blocks)

    if _needs_recovery(sections, semantic_blocks, possible_errors):
        recovered_sections, recovered_blocks, split_count = _recover_general_sections(sections, section_blocks)
        if split_count > 0:
            sections = recovered_sections
            section_blocks = recovered_blocks
            recovery_count = split_count
            possible_errors = _collect_section_errors(sections, semantic_blocks, section_blocks)

    general_block_ratio = _general_block_ratio(sections, semantic_blocks)
    diagnostics = {
        "section_count": len(sections),
        "general_block_ratio": general_block_ratio,
        "possible_errors": possible_errors,
        "recovered_section_splits": recovery_count,
    }
    return sections, diagnostics


def is_section_heading(block: SemanticBlock, strict: bool = False) -> bool:
    """Return whether a semantic block looks like a section heading."""

    text = normalize_text(block.text)
    canonical = normalize_section_heading(text)
    if canonical is not None:
        return True

    words = text.rstrip(":").split()
    if not words or len(words) > 4:
        return False
    if _SENTENCE_END_RE.search(text):
        return False
    if strict and text != text.upper() and not text.endswith(":"):
        return False
    if not strict and block.label not in {"section_heading", "heading"}:
        return False
    return (text == text.upper() or text.endswith(":")) and _is_heading_position(block)


def canonicalize_section_heading(text: str) -> str:
    """Return a normalized heading for section display."""

    canonical = normalize_section_heading(text)
    if canonical is not None:
        return canonical
    return normalize_text(text).rstrip(":")


def _initial_split(semantic_blocks: List[SemanticBlock]) -> Tuple[List[RawSection], Dict[str, List[SemanticBlock]]]:
    sections: List[RawSection] = []
    section_blocks: Dict[str, List[SemanticBlock]] = {}
    current_heading = "General"
    current_blocks: List[SemanticBlock] = []
    seen_real_section = False
    pending_heading: Optional[str] = None

    def flush() -> None:
        if not current_blocks:
            return
        text_blocks = [block.text for block in current_blocks if block.label != "section_heading"]
        content = normalize_text("\n".join(text_blocks))
        if not content and current_heading == "General":
            return
        pages = OrderedDict()
        for block in current_blocks:
            pages[block.page_number] = None
        sections.append(
            RawSection(
                heading=current_heading,
                content=content,
                source_pages=list(pages.keys()),
                block_ids=[block.block_id for block in current_blocks],
            )
        )
        section_blocks[_section_key(sections[-1])] = list(current_blocks)

    for block in semantic_blocks:
        leading_heading, leading_remainder = _extract_leading_embedded_heading(block.text)
        if leading_heading is not None:
            flush()
            current_heading = leading_heading
            current_blocks = []
            seen_real_section = current_heading not in _HEADER_CANONICALS
            if leading_remainder:
                current_blocks.append(_clone_block_with_text(block, leading_remainder))
            continue

        inline_before_heading, inline_heading, inline_after_heading = _extract_inline_delimited_heading(block.text)
        if inline_heading is not None:
            if inline_before_heading:
                current_blocks.append(_clone_block_with_text(block, inline_before_heading))
            flush()
            current_heading = inline_heading
            current_blocks = []
            seen_real_section = current_heading not in _HEADER_CANONICALS
            if inline_after_heading:
                current_blocks.append(_clone_block_with_text(block, inline_after_heading))
            continue

        if pending_heading is not None:
            flush()
            current_heading = pending_heading
            current_blocks = []
            seen_real_section = current_heading not in _HEADER_CANONICALS
            pending_heading = None

        if _is_initial_section_boundary(block):
            flush()
            current_heading = canonicalize_section_heading(block.text)
            current_blocks = [block]
            if current_heading not in _HEADER_CANONICALS:
                seen_real_section = True
            continue

        trailing_heading, trimmed_text = _extract_trailing_embedded_heading(block.text)
        if trailing_heading is not None:
            if trimmed_text:
                current_blocks.append(_clone_block_with_text(block, trimmed_text))
            pending_heading = trailing_heading
            continue

        if not seen_real_section and current_heading == "General":
            current_blocks.append(block)
            continue

        current_blocks.append(block)

    flush()
    sections = _dedupe_empty_sections(sections)
    filtered_blocks = { _section_key(section): section_blocks.get(_section_key(section), []) for section in sections }
    return sections, filtered_blocks


def _dedupe_empty_sections(sections: List[RawSection]) -> List[RawSection]:
    cleaned: List[RawSection] = []
    for section in sections:
        if cleaned and not section.content:
            continue
        cleaned.append(section)
    return cleaned


def _normalize_heading_text(text: str) -> str:
    normalized = normalize_text(text)
    normalized = _PUNCT_TRAIL_RE.sub("", normalized).strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _is_heading_position(block: SemanticBlock) -> bool:
    if block.bbox is None:
        return True
    return block.bbox[0] <= 140


def _is_initial_section_boundary(block: SemanticBlock) -> bool:
    canonical = normalize_section_heading(block.text)
    if block.label == "section_heading":
        return True
    if block.label == "heading" and canonical is not None:
        return True
    return False


def _needs_recovery(
    sections: List[RawSection], semantic_blocks: List[SemanticBlock], possible_errors: List[str]
) -> bool:
    if len(sections) <= 1:
        return True
    if "oversized_general_section" in possible_errors:
        return True
    if "heading_candidates_found_inside_general" in possible_errors:
        return True
    return False


def _recover_general_sections(
    sections: List[RawSection], section_blocks: Dict[str, List[SemanticBlock]]
) -> Tuple[List[RawSection], Dict[str, List[SemanticBlock]], int]:
    recovered_sections: List[RawSection] = []
    recovered_section_blocks: Dict[str, List[SemanticBlock]] = {}
    recovered_split_count = 0

    for section in sections:
        if section.heading != "General":
            recovered_sections.append(section)
            recovered_section_blocks[_section_key(section)] = section_blocks.get(_section_key(section), [])
            continue
        general_blocks = section_blocks.get(_section_key(section), [])
        if not general_blocks:
            recovered_sections.append(section)
            recovered_section_blocks[_section_key(section)] = general_blocks
            continue
        rescanned, rescanned_blocks = _split_general_by_heading_candidates(general_blocks)
        if len(rescanned) > 1:
            recovered_sections.extend(rescanned)
            recovered_section_blocks.update(rescanned_blocks)
            recovered_split_count += len(rescanned) - 1
        else:
            recovered_sections.append(section)
            recovered_section_blocks[_section_key(section)] = general_blocks

    recovered_sections = _dedupe_empty_sections(recovered_sections)
    recovered_section_blocks = {
        _section_key(section): recovered_section_blocks.get(_section_key(section), [])
        for section in recovered_sections
    }
    return recovered_sections, recovered_section_blocks, recovered_split_count


def _split_general_by_heading_candidates(
    general_blocks: List[SemanticBlock],
) -> Tuple[List[RawSection], Dict[str, List[SemanticBlock]]]:
    sections: List[RawSection] = []
    section_blocks: Dict[str, List[SemanticBlock]] = {}
    current_heading = "General"
    current_blocks: List[SemanticBlock] = []

    def flush() -> None:
        if not current_blocks:
            return
        pages = OrderedDict()
        for block in current_blocks:
            pages[block.page_number] = None
        content = normalize_text(
            "\n".join(block.text for block in current_blocks if block.label != "section_heading")
        )
        sections.append(RawSection(
            heading=current_heading,
            content=content,
            source_pages=list(pages.keys()),
            block_ids=[block.block_id for block in current_blocks],
        ))
        section_blocks[_section_key(sections[-1])] = list(current_blocks)

    for block in general_blocks:
        if is_section_heading(block, strict=True):
            flush()
            current_heading = canonicalize_section_heading(block.text)
            current_blocks = [block]
            continue
        current_blocks.append(block)
    flush()
    return sections, section_blocks


def _collect_section_errors(
    sections: List[RawSection],
    semantic_blocks: List[SemanticBlock],
    section_blocks: Dict[str, List[SemanticBlock]],
) -> List[str]:
    possible_errors: List[str] = []
    general_ratio = _general_block_ratio(sections, semantic_blocks)
    heading_candidates_inside_general = _general_heading_candidates(sections, section_blocks)

    if len(sections) == 1 and sections[0].heading == "General":
        possible_errors.append("document_collapsed_into_general")
    if general_ratio > 0.7:
        possible_errors.append("oversized_general_section")
    if heading_candidates_inside_general:
        possible_errors.append("heading_candidates_found_inside_general")
    return possible_errors


def _general_block_ratio(sections: List[RawSection], semantic_blocks: List[SemanticBlock]) -> float:
    total_blocks = len(semantic_blocks)
    if total_blocks == 0:
        return 0.0
    general_blocks = 0
    for section in sections:
        if section.heading == "General":
            general_blocks += len(section.block_ids)
    return float(general_blocks) / float(total_blocks)


def _general_heading_candidates(
    sections: List[RawSection], section_blocks: Dict[str, List[SemanticBlock]]
) -> bool:
    for section in sections:
        if section.heading != "General":
            continue
        semantic_blocks = section_blocks.get(_section_key(section), [])
        for block in semantic_blocks:
            if is_section_heading(block, strict=True):
                return True
    return False


def _section_key(section: RawSection) -> str:
    return "{0}|{1}|{2}".format(section.heading, ",".join(section.block_ids), ",".join(str(page) for page in section.source_pages))


def _extract_leading_embedded_heading(text: str) -> Tuple[Optional[str], str]:
    normalized = normalize_text(text)
    if "\n" not in normalized:
        return None, normalized
    first_line, remainder = normalized.split("\n", 1)
    canonical = normalize_section_heading(first_line)
    if canonical is None:
        return None, normalized
    return canonical, normalize_text(remainder)


def _extract_trailing_embedded_heading(text: str) -> Tuple[Optional[str], str]:
    normalized = normalize_text(text)
    lines = [line for line in normalized.splitlines() if line.strip()]
    if not lines:
        return None, normalized

    last_line = lines[-1].strip()
    canonical = normalize_section_heading(last_line)
    if canonical is not None and _looks_like_embedded_heading_token(last_line):
        trimmed = normalize_text("\n".join(lines[:-1]))
        return canonical, trimmed

    for alias_text in sorted(_SECTION_ALIASES.keys(), key=len, reverse=True):
        candidate = alias_text.upper()
        if normalized.endswith(" " + candidate):
            trimmed = normalize_text(normalized[: -len(candidate)].rstrip())
            return _SECTION_ALIASES[alias_text], trimmed

    return None, normalized


def _looks_like_embedded_heading_token(text: str) -> bool:
    return bool(_UPPERCASE_TOKEN_RE.match(text.strip())) or text.strip().endswith(":")


def _clone_block_with_text(block: SemanticBlock, text: str) -> SemanticBlock:
    return block.model_copy(update={"text": normalize_text(text), "original_text": block.original_text})


def _extract_inline_delimited_heading(text: str) -> Tuple[str, Optional[str], str]:
    normalized = normalize_text(text)
    parts = [part.strip() for part in normalized.split("|")]
    if len(parts) < 2:
        return normalized, None, ""

    for index, part in enumerate(parts):
        canonical, before_inside, after_inside = _extract_heading_from_segment(part)
        if canonical is None:
            continue
        before_parts = [item for item in parts[:index] if item]
        after_parts = [item for item in parts[index + 1 :] if item]
        if before_inside:
            before_parts.append(before_inside)
        if after_inside:
            after_parts.insert(0, after_inside)
        before = normalize_text(" | ".join(before_parts))
        after = normalize_text(" | ".join(after_parts))
        return before, canonical, after

    return normalized, None, ""


def _extract_heading_from_segment(segment: str) -> Tuple[Optional[str], str, str]:
    normalized_segment = normalize_text(segment)
    canonical = normalize_section_heading(normalized_segment)
    if canonical is not None:
        return canonical, "", ""

    lowered = _normalize_heading_text(normalized_segment)
    for alias_text in sorted(_SECTION_ALIASES.keys(), key=len, reverse=True):
        if lowered == alias_text:
            return _SECTION_ALIASES[alias_text], "", ""
        if lowered.startswith(alias_text + " "):
            original_words = normalized_segment.split()
            alias_words = len(alias_text.split())
            before = ""
            after = normalize_text(" ".join(original_words[alias_words:]))
            return _SECTION_ALIASES[alias_text], before, after
        if lowered.endswith(" " + alias_text):
            alias_words = len(alias_text.split())
            original_words = normalized_segment.split()
            before = normalize_text(" ".join(original_words[:-alias_words]))
            return _SECTION_ALIASES[alias_text], before, ""

    return None, "", ""
