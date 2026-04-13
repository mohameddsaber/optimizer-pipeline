"""Adapter from Phase 1 extraction output to stable Phase 2 input."""

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from contracts.common import CANONICAL_SECTION_NAMES, CONTRACT_VERSION
from contracts.phase1_output import Phase1Output, RawSection, SemanticBlock
from contracts.phase2_input import Phase2Input
from extractor.normalize import normalize_text

_EMAIL_RE = re.compile(r"[\w.\-+%]+@[\w.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_LINKEDIN_RE = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?linkedin\.com/[^\s|,]+")
_GITHUB_RE = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?github\.com/[^\s|,]+")
_URL_GITHUB_WORD_RE = re.compile(r"(?i)\bgithub\b")
_URL_LINKEDIN_WORD_RE = re.compile(r"(?i)\blinkedin\b")
_DATE_HINT_RE = re.compile(
    r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|\d{1,2}/\d{4}|\d{4}|present|current)\b"
)
_LANGUAGE_WORDS = {
    "english",
    "arabic",
    "french",
    "german",
    "spanish",
    "italian",
    "turkish",
    "chinese",
    "japanese",
    "russian",
}
_SECTION_NAME_ALIASES = {
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
    "courses": "Courses",
    "training": "Courses",
    "trainings": "Courses",
    "workshops": "Courses",
    "certifications & courses": "Courses",
    "certifications and courses": "Courses",
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


def build_phase2_input(phase1_output: Phase1Output) -> Phase2Input:
    """Build a stable Phase 2 input payload from Phase 1 output."""

    phase1 = _coerce_phase1_output(phase1_output)
    canonical_sections, uncategorized_text, section_block_map = merge_section_texts(phase1)
    contact_candidates = extract_contact_candidates(phase1, canonical_sections, uncategorized_text)
    skill_candidates = extract_skill_candidates(phase1, canonical_sections, section_block_map)
    language_candidates = extract_language_candidates(phase1, canonical_sections)
    experience_candidates = build_lightweight_entry_candidates(
        "Experience", canonical_sections, section_block_map
    )
    project_candidates = build_lightweight_entry_candidates(
        "Projects", canonical_sections, section_block_map
    )
    education_candidates = build_lightweight_entry_candidates(
        "Education", canonical_sections, section_block_map
    )
    training_candidates = extract_training_candidates(canonical_sections, section_block_map)
    certification_candidates = _extract_certification_candidates(canonical_sections)
    diagnostics_flags = _map_diagnostics_flags(phase1, uncategorized_text, canonical_sections)
    source_metadata = _build_source_metadata(phase1)

    return Phase2Input(
        contract_version=CONTRACT_VERSION,
        full_text=phase1.full_text,
        canonical_sections=canonical_sections,
        uncategorized_text=uncategorized_text,
        contact_candidates=contact_candidates,
        skill_candidates=skill_candidates,
        language_candidates=language_candidates,
        experience_candidates=experience_candidates,
        project_candidates=project_candidates,
        education_candidates=education_candidates,
        certification_candidates=certification_candidates,
        training_candidates=training_candidates,
        diagnostics_flags=diagnostics_flags,
        source_metadata=source_metadata,
    )


def canonicalize_section_name(name: str) -> Optional[str]:
    """Map a Phase 1 section name to a stable canonical Phase 2 section name."""

    normalized = normalize_text(name).strip().rstrip(":").lower()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized or normalized == "general":
        return None
    return _SECTION_NAME_ALIASES.get(normalized)


def merge_section_texts(
    phase1_output: Phase1Output,
) -> Tuple[Dict[str, str], str, Dict[str, List[SemanticBlock]]]:
    """Merge repeated canonical sections and isolate uncategorized content."""

    canonical_order: List[str] = []
    section_text_parts: Dict[str, List[str]] = {}
    section_block_map: Dict[str, List[SemanticBlock]] = {}
    uncategorized_parts: List[str] = []
    semantic_by_id = {block.block_id: block for block in phase1_output.semantic_blocks}

    for section in phase1_output.sections:
        canonical_name = canonicalize_section_name(section.heading)
        if canonical_name is None:
            if normalize_text(section.content):
                uncategorized_parts.append(normalize_text(section.content))
            continue

        if canonical_name not in section_text_parts:
            canonical_order.append(canonical_name)
            section_text_parts[canonical_name] = []
            section_block_map[canonical_name] = []
        content = normalize_text(section.content)
        if content:
            section_text_parts[canonical_name].append(content)
        section_block_map[canonical_name].extend(
            semantic_by_id[block_id]
            for block_id in section.block_ids
            if block_id in semantic_by_id and semantic_by_id[block_id].label != "section_heading"
        )

    canonical_sections = {
        name: normalize_text("\n\n".join(parts))
        for name, parts in ((name, section_text_parts[name]) for name in canonical_order)
        if any(parts)
    }
    uncategorized_text = normalize_text("\n\n".join(uncategorized_parts))
    return canonical_sections, uncategorized_text, section_block_map


def extract_contact_candidates(
    phase1_output: Phase1Output,
    canonical_sections: Dict[str, str],
    uncategorized_text: str,
) -> Dict[str, List[str]]:
    """Extract deterministic contact candidate pools."""

    candidate_pool: List[str] = []
    header_text = canonical_sections.get("Header", "")
    if header_text:
        candidate_pool.append(header_text)
    if uncategorized_text:
        candidate_pool.append(uncategorized_text)
    candidate_pool.extend(
        block.text for block in phase1_output.semantic_blocks[:6] if block.label in {"contact_line", "heading"}
    )
    candidate_pool.extend(block.text for block in phase1_output.semantic_blocks if block.label == "contact_line")
    candidate_pool.append(phase1_output.full_text[:1200])

    names: List[str] = []
    emails: List[str] = []
    phones: List[str] = []
    locations: List[str] = []
    linkedins: List[str] = []
    githubs: List[str] = []

    for text in candidate_pool:
        normalized = normalize_text(text)
        emails.extend(_EMAIL_RE.findall(normalized))
        phones.extend(match.strip() for match in _PHONE_RE.findall(normalized))
        linkedins.extend(_LINKEDIN_RE.findall(normalized))
        githubs.extend(_GITHUB_RE.findall(normalized))
        locations.extend(_extract_location_candidates_from_text(normalized))
        names.extend(_extract_name_candidates_from_text(normalized))
        if _URL_LINKEDIN_WORD_RE.search(normalized) and not _LINKEDIN_RE.search(normalized):
            linkedins.append(normalized)
        if _URL_GITHUB_WORD_RE.search(normalized) and not _GITHUB_RE.search(normalized):
            githubs.append(normalized)

    return {
        "name": _dedupe_preserve_order(names),
        "email": _dedupe_preserve_order(emails),
        "phone": _dedupe_preserve_order(phones),
        "location": _dedupe_preserve_order(locations),
        "linkedin": _dedupe_preserve_order(linkedins),
        "github": _dedupe_preserve_order(githubs),
    }


def extract_skill_candidates(
    phase1_output: Phase1Output,
    canonical_sections: Dict[str, str],
    section_block_map: Dict[str, List[SemanticBlock]],
) -> List[str]:
    """Extract deterministic skill candidates from Skills content and skill-like blocks."""

    texts: List[str] = []
    if "Skills" in canonical_sections:
        texts.append(canonical_sections["Skills"])
    skill_blocks = section_block_map.get("Skills", [])
    texts.extend(block.text for block in skill_blocks if block.label == "skills_line")
    texts.extend(block.text for block in skill_blocks if block.label == "paragraph" and _looks_like_skill_dense_block(block.text))

    candidates: List[str] = []
    for text in texts:
        for candidate in _split_candidate_text(text):
            if _looks_like_skill_candidate(candidate):
                candidates.append(candidate)
    return _dedupe_preserve_order(candidates)


def extract_language_candidates(
    phase1_output: Phase1Output, canonical_sections: Dict[str, str]
) -> List[str]:
    """Extract deterministic language candidates."""

    texts: List[str] = []
    if "Languages" in canonical_sections:
        texts.append(canonical_sections["Languages"])
    if "Additional Information" in canonical_sections:
        texts.append(canonical_sections["Additional Information"])
    texts.extend(
        block.text
        for block in phase1_output.semantic_blocks
        if "language" in normalize_text(block.text).lower()
    )

    candidates: List[str] = []
    for text in texts:
        for candidate in _split_candidate_text(text):
            normalized = normalize_text(candidate)
            if normalized.lower().split(":", 1)[0] == "languages":
                remainder = normalized.split(":", 1)[1] if ":" in normalized else normalized
                candidates.extend(_split_candidate_text(remainder))
                continue
            if normalized.lower() in _LANGUAGE_WORDS:
                candidates.append(normalized)
    return _dedupe_preserve_order(candidates)


def build_lightweight_entry_candidates(
    source_section: str,
    canonical_sections: Dict[str, str],
    section_block_map: Dict[str, List[SemanticBlock]],
) -> List[Dict[str, Any]]:
    """Build lightweight entry candidates from canonical section content."""

    section_text = canonical_sections.get(source_section, "")
    source_blocks = section_block_map.get(source_section, [])
    candidates: List[Dict[str, Any]] = []

    if source_blocks:
        current_parts: List[str] = []
        current_hints: Dict[str, Any] = {"dates": [], "header_lines": []}
        for block in source_blocks:
            text = normalize_text(block.text)
            if not text:
                continue
            if block.label in {"heading", "date"} and current_parts:
                candidate = _make_entry_candidate(current_parts, source_section, current_hints)
                if _is_valid_entry_candidate(candidate):
                    candidates.append(candidate)
                current_parts = []
                current_hints = {"dates": [], "header_lines": []}
            current_parts.append(text)
            if block.label == "date":
                current_hints["dates"].append(text)
            if block.label == "heading":
                current_hints["header_lines"].append(text)
        if current_parts:
            candidate = _make_entry_candidate(current_parts, source_section, current_hints)
            if _is_valid_entry_candidate(candidate):
                candidates.append(candidate)

    if not candidates and section_text:
        for chunk in _split_entry_chunks(section_text):
            candidate = {
                "text": chunk,
                "source_section": source_section,
                "hints": {"detected_dates": _DATE_HINT_RE.findall(chunk)},
            }
            if _is_valid_entry_candidate(candidate):
                candidates.append(candidate)
    return candidates


def extract_training_candidates(
    canonical_sections: Dict[str, str],
    section_block_map: Dict[str, List[SemanticBlock]],
) -> List[Dict[str, Any]]:
    """Extract course/training candidates from course sections and additional information."""

    candidates = build_lightweight_entry_candidates("Courses", canonical_sections, section_block_map)
    additional_information = canonical_sections.get("Additional Information", "")
    if not additional_information:
        return candidates

    pending_provider: Optional[str] = None
    for line in additional_information.splitlines():
        normalized_line = normalize_text(line)
        if not normalized_line:
            continue
        lowered = normalized_line.lower()
        if pending_provider and _looks_like_training_candidate(normalized_line):
            for chunk in _split_candidate_text(normalized_line):
                if _looks_like_training_candidate(chunk):
                    combined = chunk
                    if not chunk.lower().startswith(pending_provider.lower()):
                        combined = normalize_text("{0} {1}".format(pending_provider, chunk))
                    candidates.append(
                        {
                            "text": combined,
                            "source_section": "Courses",
                            "hints": {"detected_dates": _DATE_HINT_RE.findall(chunk), "possible_header_lines": []},
                        }
                    )
            pending_provider = None
            continue
        if not lowered.startswith(("certifications:", "courses:", "training:", "trainings:", "workshops:")):
            continue
        label, _, remainder = normalized_line.partition(":")
        if not remainder:
            continue
        if label.strip().lower().startswith("certification"):
            split_candidates = _split_candidate_text(remainder)
            if split_candidates:
                tail = split_candidates[-1]
                if tail.lower() == "udemy":
                    pending_provider = tail
            continue
        for chunk in _split_candidate_text(remainder):
            if _looks_like_training_candidate(chunk):
                candidates.append(
                    {
                        "text": chunk,
                        "source_section": "Courses",
                        "hints": {"detected_dates": _DATE_HINT_RE.findall(chunk), "possible_header_lines": []},
                    }
                )

    return _dedupe_entry_candidates(candidates)


def _coerce_phase1_output(phase1_output: Any) -> Phase1Output:
    if isinstance(phase1_output, Phase1Output):
        return phase1_output
    if isinstance(phase1_output, dict):
        return Phase1Output.model_validate(phase1_output)
    return Phase1Output.model_validate(phase1_output.model_dump())


def _extract_certification_candidates(canonical_sections: Dict[str, str]) -> List[str]:
    candidates: List[str] = []
    for section_name in ("Certifications",):
        if section_name not in canonical_sections:
            continue
        for candidate in _split_candidate_text(canonical_sections[section_name]):
            if candidate:
                candidates.append(candidate)
    additional_information = canonical_sections.get("Additional Information", "")
    for line in additional_information.splitlines():
        normalized_line = normalize_text(line)
        if not normalized_line.lower().startswith("certifications:"):
            continue
        _, _, remainder = normalized_line.partition(":")
        for candidate in _split_candidate_text(remainder):
            if candidate and candidate.lower() != "udemy" and not _looks_like_training_candidate(candidate):
                candidates.append(candidate)
    return _dedupe_preserve_order(candidates)


def _map_diagnostics_flags(
    phase1_output: Phase1Output,
    uncategorized_text: str,
    canonical_sections: Dict[str, str],
) -> List[str]:
    flags: List[str] = []
    diagnostics = phase1_output.diagnostics
    if diagnostics.fallback_used:
        flags.append("fallback_used")
    for possible_error in diagnostics.possible_errors:
        flags.append(possible_error)
    if diagnostics.general_block_ratio >= 0.3:
        flags.append("high_general_block_ratio")
    if diagnostics.recovered_section_splits > 0:
        flags.append("suspicious_section_split")
    if diagnostics.merged_block_count > 0 and _contains_heading_alias(uncategorized_text):
        flags.append("normalization_overmerge_risk")
    if not canonical_sections and uncategorized_text:
        flags.append("document_collapsed_into_general")
    return _dedupe_preserve_order(flags)


def _build_source_metadata(phase1_output: Phase1Output) -> Dict[str, Any]:
    metadata = phase1_output.metadata or {}
    source_path = metadata.get("source_path")
    file_name = Path(source_path).name if source_path else None
    return {
        "file_name": file_name,
        "source_path": source_path,
        "page_count": metadata.get("page_count", len(phase1_output.pages)),
        "extractor": metadata.get("extractor"),
        "fallback_triggered": bool(metadata.get("fallback_triggered")),
    }


def _extract_location_candidates_from_text(text: str) -> List[str]:
    candidates: List[str] = []
    for part in _split_candidate_text(text):
        lowered = part.lower()
        if any(token in lowered for token in ("cairo", "giza", "egypt", "alexandria", "remote", "new cairo")):
            candidates.append(part)
    return candidates


def _extract_name_candidates_from_text(text: str) -> List[str]:
    candidates: List[str] = []
    for line in text.splitlines():
        normalized = normalize_text(line)
        if not normalized:
            continue
        if _EMAIL_RE.search(normalized) or _PHONE_RE.search(normalized):
            continue
        words = normalized.split()
        if 2 <= len(words) <= 4 and normalized == normalized.title():
            candidates.append(normalized)
        elif 2 <= len(words) <= 4 and normalized == normalized.upper():
            candidates.append(normalized.title())
    return candidates


def _split_candidate_text(text: str) -> List[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    parts: List[str] = []
    for line in normalized.splitlines():
        for chunk in re.split(r"\s*\|\s*|•|, (?=[A-Z][a-z])", line):
            candidate = normalize_text(chunk)
            if candidate:
                parts.append(candidate)
    return parts


def _looks_like_skill_candidate(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    if len(normalized) > 80:
        return False
    if _EMAIL_RE.search(normalized) or _PHONE_RE.search(normalized):
        return False
    if normalized.lower().startswith(("languages:", "certifications:")):
        return False
    lowered = normalized.lower()
    if lowered in _LANGUAGE_WORDS:
        return False
    if any(token in lowered for token in ("certification", "certificate", "course", "bootcamp", "workshop")):
        return False
    if any(token in lowered for token in ("udemy", "comptia", "ccna", "saa-c03")):
        return False
    return len(normalized.split()) <= 8


def _looks_like_skill_dense_block(text: str) -> bool:
    normalized = normalize_text(text)
    return (
        normalized.count("|") >= 2
        or normalized.lower().startswith(("programming", "frontend", "backend", "tools", "concepts", "technical skills"))
    )


def _make_entry_candidate(
    parts: List[str], source_section: str, hints: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "text": normalize_text("\n".join(parts)),
        "source_section": source_section,
        "hints": {
            "detected_dates": _dedupe_preserve_order(hints.get("dates", [])),
            "possible_header_lines": _dedupe_preserve_order(hints.get("header_lines", [])),
        },
    }


def _is_valid_entry_candidate(candidate: Dict[str, Any]) -> bool:
    text = normalize_text(str(candidate.get("text", "")))
    source_section = str(candidate.get("source_section", ""))
    if not text:
        return False
    if source_section != "Projects":
        return True

    first_line = normalize_text(text.splitlines()[0] if "\n" in text else text.split(" | ", 1)[0])
    lowered = first_line.lower().strip(":")
    if canonicalize_section_name(first_line) not in (None, "Projects"):
        return False
    if lowered in {"engineering practices", "professional highlights"}:
        return False
    if any(token in lowered for token in ("practices", "methodology", "scrum-based development")):
        return False
    return True


def _looks_like_training_candidate(text: str) -> bool:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    if not normalized:
        return False
    return any(token in lowered for token in ("bootcamp", "course", "training", "workshop"))


def _dedupe_entry_candidates(candidates: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for candidate in candidates:
        text = normalize_text(str(candidate.get("text", ""))).lower()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(candidate)
    return deduped


def _split_entry_chunks(text: str) -> List[str]:
    normalized = normalize_text(text)
    chunks = [normalize_text(chunk) for chunk in re.split(r"\n{2,}", normalized) if normalize_text(chunk)]
    return chunks or ([normalized] if normalized else [])


def _contains_heading_alias(text: str) -> bool:
    normalized = normalize_text(text).lower()
    return any(alias in normalized for alias in _SECTION_NAME_ALIASES)


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for item in items:
        normalized = normalize_text(item)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped
