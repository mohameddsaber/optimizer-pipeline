"""Coverage-mode recovery helpers for supplemental CV content."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.normalize import normalize_text

_BULLET_SPLIT_RE = re.compile(r"(?:^|\n)\s*[•●▪·-]\s*", re.MULTILINE)
_SECTION_PREFIX_RE = re.compile(
    r"^(?:awards?|achievements?|accomplishments?|honors?|honours?|publications?|activities|volunteer(?:ing| work)?|awards/activities)\s*:\s*",
    re.IGNORECASE,
)
_TRAILING_SECTION_BLEED_RE = re.compile(
    r"\s+(?:EDUCATION|CERTIFICATIONS|TECHNICAL SKILLS|SKILLS|LANGUAGES|COURSES|EXPERIENCE|PROJECTS)\s*&\s*$",
    re.IGNORECASE,
)


def recover_supplemental_content(
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    optimizer_payload: Dict[str, Any],
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Recover awards, achievements, activities, and publications from source-derived sections."""

    del parser_payload  # Supplemental recovery is source-first for now.

    base = {
        "awards": _get_string_list(optimizer_payload, "awards"),
        "achievements": _get_string_list(optimizer_payload, "achievements"),
        "activities": _get_string_list(optimizer_payload, "activities"),
        "publications": _get_string_list(optimizer_payload, "publications"),
    }
    recovered = {key: list(values) for key, values in base.items()}
    seen = {
        key: {normalize_text(value).lower() for value in values if normalize_text(value)}
        for key, values in recovered.items()
    }
    audit = {"recovered_items": [], "recovered_fields": [], "notes": []}

    for chunk_payload in _extract_supplemental_chunks(phase2_input):
        raw_chunk = chunk_payload["raw"]
        chunk = chunk_payload["cleaned"]
        target_field = _classify_supplemental_chunk(raw_chunk, chunk_payload.get("source_section", ""))
        if target_field is None:
            continue
        key = normalize_text(chunk).lower()
        if not key or key in seen[target_field]:
            continue
        seen[target_field].add(key)
        recovered[target_field].append(chunk)
        audit["recovered_items"].append("{0}:{1}".format(target_field, chunk))
        audit["notes"].append(
            "Recovered {0}: {1} from source evidence".format(_singular_label(target_field), chunk)
        )

    return recovered, audit


def _extract_supplemental_chunks(phase2_input: Phase2Input) -> List[Dict[str, str]]:
    texts: List[Tuple[str, str]] = []
    direct_chunks: List[Dict[str, str]] = []
    achievements = phase2_input.canonical_sections.get("Achievements", "")
    additional_information = phase2_input.canonical_sections.get("Additional Information", "")
    education = phase2_input.canonical_sections.get("Education", "")
    skills = phase2_input.canonical_sections.get("Skills", "")
    if achievements:
        texts.append(("Achievements", achievements))
    if additional_information:
        texts.append(("Additional Information", additional_information))
    if _looks_like_supplemental_education(education):
        direct_chunks.extend(_extract_publication_chunks(education))
    direct_chunks.extend(_extract_volunteering_chunks(skills))

    chunks: List[Dict[str, str]] = []
    for source_section, text in texts:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            continue
        parts = [part.strip() for part in _BULLET_SPLIT_RE.split(normalized) if part.strip()]
        if len(parts) <= 1:
            parts = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
        for part in parts:
            cleaned = _clean_chunk(part)
            if cleaned:
                chunks.append(
                    {
                        "raw": normalize_text(part),
                        "cleaned": cleaned,
                        "source_section": source_section,
                    }
                )
    chunks.extend(direct_chunks)
    return _dedupe_chunk_payloads(chunks)


def _clean_chunk(text: str) -> str:
    normalized = normalize_text(text)
    normalized = re.sub(r"^[•●▪·-]\s*", "", normalized)
    normalized = _SECTION_PREFIX_RE.sub("", normalized).strip(" ,;|")
    normalized = re.sub(r"^publication(?:\s*\([^)]*\))?\s*:\s*", "", normalized, flags=re.IGNORECASE)
    normalized = _TRAILING_SECTION_BLEED_RE.sub("", normalized).strip(" ,;|")
    if not normalized or len(normalized.split()) < 3:
        return ""
    return normalized


def _looks_like_supplemental_education(text: str) -> bool:
    lowered = normalize_text(text).lower()
    return any(token in lowered for token in ("publication", "thesis", "bachelor thesis", "capstone"))


def _extract_publication_chunks(text: str) -> List[Dict[str, str]]:
    chunks: List[Dict[str, str]] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        normalized = normalize_text(line)
        if not normalized:
            continue
        if _classify_supplemental_chunk(normalized) != "publications":
            continue
        cleaned = _clean_chunk(normalized)
        if cleaned:
            chunks.append({"raw": normalized, "cleaned": cleaned})
    return chunks


def _extract_volunteering_chunks(text: str) -> List[Dict[str, str]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    match = re.search(r"(?is)\b(?:volunteering|volunteer(?:ing)? activities?)\b\s*(.*)$", normalized)
    if not match:
        return []

    tail = match.group(1).strip()
    lines = [normalize_text(line) for line in tail.splitlines() if normalize_text(line)]
    chunks: List[Dict[str, str]] = []
    pending_context = ""
    for line in lines:
        if re.match(r"(?i)^(?:[A-Z]+\s+\d{4}|\d{4}|[A-Z][A-Za-z]+\s+\d{4}|[A-Z][A-Za-z]+\s+\d{4}\s*,)", line):
            pending_context = line
            continue
        if not re.match(r"^[\-•●▪·]", line) and _classify_supplemental_chunk(line) != "activities":
            continue
        raw = "{0} {1}".format(pending_context, line).strip() if pending_context else line
        cleaned = _clean_chunk(line)
        if cleaned:
            chunks.append({"raw": normalize_text(raw), "cleaned": cleaned})
    return chunks


def _classify_supplemental_chunk(text: str, source_section: str = "") -> str | None:
    lowered = text.lower()

    if any(
        token in lowered
        for token in {
            "publication",
            "paper",
            "journal",
            "conference",
            "peer-reviewed",
            "accepted at",
        }
    ):
        return "publications"

    if any(
        token in lowered
        for token in {
            "award",
            "awarded",
            "honor",
            "honour",
            "scholarship",
            "finalist",
            "ranked",
            "runner-up",
            "1st",
            "2nd",
            "3rd",
            "first place",
            "second place",
            "third place",
            "competition",
            "championship",
            "hackathon",
        }
    ):
        return "awards"

    if any(
        token in lowered
        for token in {
            "activity",
            "activities",
            "extracurricular",
            "committee",
            "org team",
            "technical committee",
            "pavilion",
            "exhibition",
            "ushered",
            "member in org team",
            "member of",
            "helped lead",
            "responsible for data entry",
        }
    ):
        return "activities"

    if any(
        token in lowered
        for token in {
            "achievement",
            "accomplishment",
            "founded",
            "founded and led",
            "led a volunteer team",
            "organized",
            "represented",
            "member",
            "participated",
            "initiative",
        }
    ):
        return "achievements"

    if normalize_text(source_section).lower() == "achievements":
        return "achievements"

    return None


def _get_string_list(payload: Dict[str, Any], key: str) -> List[str]:
    value = payload.get(key)
    if value is None:
        return []
    if isinstance(value, str):
        normalized = normalize_text(value)
        return [normalized] if normalized else []
    if not isinstance(value, list):
        return []
    values: List[str] = []
    for item in value:
        normalized = normalize_text(str(item))
        if normalized:
            values.append(normalized)
    return values


def _dedupe_chunk_payloads(values: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    deduped: List[Dict[str, str]] = []
    for value in values:
        key = normalize_text(value["cleaned"]).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _singular_label(field_name: str) -> str:
    if field_name == "activities":
        return "activity"
    return field_name.rstrip("s")
