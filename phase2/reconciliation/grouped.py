"""Coverage-mode grouped recovery helpers preserving optimizer schema."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Dict, List, Sequence, Tuple

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.grouped_match import (
    ComparableGroupedEntry,
    match_education_entries,
    match_experience_entries,
    match_project_entries,
    match_training_entries,
)
from phase2.reconciliation.grouped_normalize import (
    normalize_company_name,
    normalize_date_range,
    normalize_description_text,
    normalize_institution_name,
    normalize_project_name,
    normalize_role_title,
)
from phase2.reconciliation.normalize import normalize_text

_DATE_RE = re.compile(
    r"(?i)(?:\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b[^,\n|]{0,20}\d{4}|\b\d{1,2}/\d{4}\b(?:\s*[-–]\s*(?:present|\d{1,2}/\d{4}))?|\b\d{4}\b(?:\s*[-–]\s*(?:present|\d{4}))?)"
)


def recover_experience(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """Preserve optimizer experience and recover missing source-backed entries."""

    return _recover_grouped_field(
        field_name="experience",
        phase2_candidates=phase2_input.experience_candidates,
        parser_entries=_get_list(parser_payload, "experience"),
        optimizer_entries=_get_list(optimizer_payload, "experience"),
        matcher=match_experience_entries,
    )


def recover_projects(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """Preserve optimizer projects and recover missing source-backed entries."""

    return _recover_grouped_field(
        field_name="projects",
        phase2_candidates=phase2_input.project_candidates,
        parser_entries=_get_list(parser_payload, "projects"),
        optimizer_entries=_get_list(optimizer_payload, "projects"),
        matcher=match_project_entries,
    )


def recover_education(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """Preserve optimizer education and recover missing source-backed entries."""

    return _recover_grouped_field(
        field_name="education",
        phase2_candidates=phase2_input.education_candidates,
        parser_entries=_get_list(parser_payload, "education"),
        optimizer_entries=_get_list(optimizer_payload, "education"),
        matcher=match_education_entries,
    )


def recover_trainings_courses(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """Preserve optimizer trainings/courses and recover missing source-backed entries."""

    return _recover_grouped_field(
        field_name="trainings_courses",
        phase2_candidates=phase2_input.training_candidates,
        parser_entries=_get_list(parser_payload, "trainings_courses"),
        optimizer_entries=_get_list(optimizer_payload, "trainings_courses"),
        matcher=match_training_entries,
        skip_titles=_build_cross_section_skip_titles(parser_payload, optimizer_payload, "certifications"),
    )


def reconcile_experience(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """Backward-compatible alias for coverage-mode experience recovery."""

    return recover_experience(phase2_input, parser_payload, optimizer_payload)


def reconcile_projects(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """Backward-compatible alias for coverage-mode project recovery."""

    return recover_projects(phase2_input, parser_payload, optimizer_payload)


def reconcile_education(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """Backward-compatible alias for coverage-mode education recovery."""

    return recover_education(phase2_input, parser_payload, optimizer_payload)


def reconcile_trainings_courses(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """Backward-compatible alias for coverage-mode training recovery."""

    return recover_trainings_courses(phase2_input, parser_payload, optimizer_payload)


def _recover_grouped_field(
    field_name: str,
    phase2_candidates: Sequence[Dict[str, Any]],
    parser_entries: Sequence[Any],
    optimizer_entries: Sequence[Any],
    matcher,
    skip_titles: Sequence[str] | None = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    schema_keys = _infer_schema_keys(field_name, optimizer_entries, parser_entries)
    final_entries = [_initialize_schema_entry(entry, schema_keys) for entry in optimizer_entries]
    audit = {"recovered_items": [], "recovered_fields": [], "notes": []}

    base_comparables = [_to_comparable(field_name, entry, "optimizer") for entry in final_entries]

    for parser_entry in parser_entries:
        if not isinstance(parser_entry, dict):
            continue
        parser_comparable = _to_comparable(field_name, parser_entry, "parser")
        match_index = _find_best_match(base_comparables, parser_comparable, matcher)
        if match_index is None:
            patched = _convert_to_schema(field_name, parser_entry, schema_keys)
            final_entries.append(patched)
            base_comparables.append(_to_comparable(field_name, patched, "optimizer"))
            audit["recovered_items"].append("{0}:appended_from_parser".format(field_name))
            audit["notes"].append("Recovered missing {0} from parser evidence".format(field_name.rstrip("s")))
        else:
            recovered = _patch_missing_fields(final_entries[match_index], _convert_to_schema(field_name, parser_entry, schema_keys))
            for field_key in recovered:
                audit["recovered_fields"].append("{0}.{1}".format(field_name, field_key))
                audit["notes"].append("Filled missing {0} from parser".format(field_key))

    for candidate in phase2_candidates:
        candidate_entry = _candidate_to_schema(field_name, candidate, schema_keys)
        candidate_title = normalize_text(
            _first(candidate_entry, "title", "name", "course_name", "training_name", "project_name")
        ).lower()
        if skip_titles and candidate_title and candidate_title in skip_titles:
            continue
        candidate_comparable = _to_comparable(field_name, candidate_entry, "phase2_input")
        match_index = _find_best_match(base_comparables, candidate_comparable, matcher)
        if match_index is None:
            final_entries.append(candidate_entry)
            base_comparables.append(_to_comparable(field_name, candidate_entry, "optimizer"))
            audit["recovered_items"].append("{0}:appended_from_source".format(field_name))
            audit["notes"].append("Recovered missing {0} from source evidence".format(field_name.rstrip("s")))
        else:
            recovered = _patch_missing_fields(final_entries[match_index], candidate_entry)
            for field_key in recovered:
                audit["recovered_fields"].append("{0}.{1}".format(field_name, field_key))
                audit["notes"].append("Filled missing {0} from source".format(field_key))

    return final_entries, audit


def _find_best_match(
    existing: Sequence[ComparableGroupedEntry], candidate: ComparableGroupedEntry, matcher
) -> int | None:
    best_index = None
    best_score = 0.0
    for index, entry in enumerate(existing):
        result = matcher(entry, candidate)
        if result.matched and result.score > best_score:
            best_index = index
            best_score = result.score
    return best_index


def _patch_missing_fields(target: Dict[str, Any], source: Dict[str, Any]) -> List[str]:
    recovered: List[str] = []
    for key, source_value in source.items():
        if key not in target:
            continue
        if _is_empty(target.get(key)) and not _is_empty(source_value):
            target[key] = deepcopy(source_value)
            recovered.append(key)
        elif isinstance(target.get(key), list) and isinstance(source_value, list):
            merged = list(target[key])
            seen = {normalize_text(str(item)).lower() for item in merged if normalize_text(str(item))}
            for item in source_value:
                normalized = normalize_text(str(item)).lower()
                if normalized and normalized not in seen:
                    merged.append(item)
                    seen.add(normalized)
                    recovered.append(key)
            target[key] = merged
    return list(dict.fromkeys(recovered))


def _candidate_to_schema(field_name: str, candidate: Dict[str, Any], schema_keys: Sequence[str]) -> Dict[str, Any]:
    text = normalize_text(str(candidate.get("text", "")))
    parts = [normalize_text(part) for part in text.split("|")] if "|" in text else [line for line in text.splitlines() if normalize_text(line)]
    parts = [part for part in parts if part]
    entry = {key: _default_value_for_key(key) for key in schema_keys}

    if field_name == "experience":
        _set_first(entry, ("title", "job_title", "role", "position"), parts[0] if parts else "")
        _set_first(entry, ("company_name", "company", "organization", "employer"), parts[1] if len(parts) > 1 else "")
        _set_first(entry, ("duration", "date_range", "dates"), _extract_date(text))
        _set_first(entry, ("description", "summary", "details"), text)
        return entry

    if field_name == "projects":
        _set_first(entry, ("project_name", "name", "title"), parts[0] if parts else "")
        _set_first(entry, ("duration", "date_range", "dates"), _extract_date(text))
        _set_first(entry, ("description", "summary", "details"), text)
        return entry

    if field_name == "education":
        _set_first(entry, ("degree", "qualification"), _extract_degree(text))
        _set_first(entry, ("university_name", "institution", "school", "college"), _extract_institution(text))
        _set_first(entry, ("graduation_date", "date_range", "duration"), _extract_date(text))
        _set_first(entry, ("GPA", "gpa"), _extract_gpa(text))
        _set_first(entry, ("graduation_project_grade",), _extract_graduation_project_grade(text))
        _set_first(entry, ("specialization", "major"), _extract_specialization(text))
        return entry

    _set_first(entry, ("title", "name", "course_name", "training_name"), parts[0] if parts else text)
    _set_first(entry, ("institution", "provider", "issuer"), parts[1] if len(parts) > 1 else "")
    _set_first(entry, ("duration", "date_range", "dates"), _extract_date(text))
    _set_first(entry, ("description", "summary", "details"), text)
    return entry


def _convert_to_schema(field_name: str, entry: Dict[str, Any], schema_keys: Sequence[str]) -> Dict[str, Any]:
    converted = {key: _default_value_for_key(key) for key in schema_keys}
    for key in schema_keys:
        if key in entry:
            converted[key] = deepcopy(entry[key])
    if any(not _is_empty(value) for value in converted.values()):
        return converted
    return _candidate_to_schema(field_name, {"text": normalize_description_text(" | ".join(str(value) for value in entry.values() if value))}, schema_keys)


def _infer_schema_keys(field_name: str, optimizer_entries: Sequence[Dict[str, Any]], parser_entries: Sequence[Any]) -> List[str]:
    extra_keys = _validated_only_schema_keys(field_name)
    for entry in optimizer_entries:
        if isinstance(entry, dict) and entry:
            return _merge_schema_keys(list(entry.keys()), extra_keys)
    for entry in parser_entries:
        if isinstance(entry, dict) and entry:
            return _merge_schema_keys(list(entry.keys()), extra_keys)
    defaults = {
        "experience": ["company_name", "title", "duration", "description"],
        "projects": ["project_name", "description", "tools", "duration", "link"],
        "education": ["university_name", "degree", "specialization", "graduation_date", "graduation_status", "GPA", "coursework"],
        "trainings_courses": ["institution", "title", "description"],
    }
    return _merge_schema_keys(defaults[field_name], extra_keys)


def _validated_only_schema_keys(field_name: str) -> List[str]:
    if field_name == "education":
        return ["graduation_project_grade"]
    return []


def _merge_schema_keys(base_keys: Sequence[str], extra_keys: Sequence[str]) -> List[str]:
    merged = list(base_keys)
    for key in extra_keys:
        if key not in merged:
            merged.append(key)
    return merged


def _initialize_schema_entry(entry: Any, schema_keys: Sequence[str]) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        return {"value": entry}
    initialized = {key: _default_value_for_key(key) for key in schema_keys}
    for key, value in entry.items():
        initialized[key] = deepcopy(value)
    return initialized


def _to_comparable(field_name: str, entry: Dict[str, Any], source: str) -> ComparableGroupedEntry:
    text = normalize_description_text(" ".join(str(value) for value in entry.values() if value))
    if field_name == "experience":
        return ComparableGroupedEntry(
            kind=field_name,
            source=source,
            raw_text=text,
            primary_name=normalize_role_title(_first(entry, "title", "job_title", "role", "position")),
            secondary_name=normalize_company_name(_first(entry, "company_name", "company", "organization", "employer")),
            date_range=normalize_date_range(_first(entry, "duration", "date_range", "dates")),
            description=normalize_text(_first(entry, "description", "summary", "details")),
        )
    if field_name == "projects":
        return ComparableGroupedEntry(
            kind=field_name,
            source=source,
            raw_text=text,
            primary_name=normalize_project_name(_first(entry, "project_name", "name", "title")),
            date_range=normalize_date_range(_first(entry, "duration", "date_range", "dates")),
            description=normalize_text(_first(entry, "description", "summary", "details")),
            technologies=[normalize_text(str(item)) for item in _list_value(entry, "tools", "technologies", "tech_stack")],
        )
    if field_name == "education":
        return ComparableGroupedEntry(
            kind=field_name,
            source=source,
            raw_text=text,
            primary_name=normalize_role_title(_first(entry, "degree", "qualification")),
            secondary_name=normalize_institution_name(_first(entry, "university_name", "institution", "school", "college")),
            date_range=normalize_date_range(_first(entry, "graduation_date", "date_range", "duration")),
            description=text,
        )
    return ComparableGroupedEntry(
        kind=field_name,
        source=source,
        raw_text=text,
        primary_name=normalize_project_name(_first(entry, "title", "name", "course_name", "training_name")),
        secondary_name=normalize_company_name(_first(entry, "institution", "provider", "issuer")),
        date_range=normalize_date_range(_first(entry, "duration", "date_range", "dates")),
        description=text,
    )


def _extract_date(text: str) -> str:
    match = _DATE_RE.search(text)
    return normalize_text(match.group(0)) if match else ""


def _extract_degree(text: str) -> str:
    match = re.search(r"(?i)\b(?:bachelor|master|bsc|msc|phd|diploma|associate)[^|\n.]*", text)
    return normalize_text(match.group(0)) if match else (normalize_text(text.split("|", 1)[0]) if "|" in text else "")


def _extract_institution(text: str) -> str:
    match = re.search(r"(?i)\b([A-Z][A-Za-z&.'\- ]{2,}(?:University|College|Institute|School))\b", text)
    return normalize_text(match.group(1)) if match else ""


def _extract_gpa(text: str) -> str:
    match = re.search(r"(?i)\bGPA[:\s]+([0-9.]+)", text)
    return normalize_text(match.group(1)) if match else ""


def _extract_graduation_project_grade(text: str) -> str:
    match = re.search(
        r"(?i)\b(?:graduation\s+project|capstone\s+project|final\s+project)\s+grade\b[:\s-]*\(?([A-F][+-]?)\)?",
        text,
    )
    if match:
        return normalize_text(match.group(1).upper())
    match = re.search(r"(?i)\bproject\s+grade\b[:\s-]*\(?([A-F][+-]?)\)?", text)
    return normalize_text(match.group(1).upper()) if match else ""


def _extract_specialization(text: str) -> str:
    match = re.search(r"(?i)\bSpecialization(?: in)?[:\s]+([^|.\n]+)", text)
    return normalize_text(match.group(1)) if match else ""


def _first(entry: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = entry.get(key)
        if value:
            return str(value)
    return ""


def _list_value(entry: Dict[str, Any], *keys: str) -> List[Any]:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, list):
            return value
    return []


def _set_first(entry: Dict[str, Any], keys: Sequence[str], value: Any) -> None:
    for key in keys:
        if key in entry:
            entry[key] = value
            return


def _default_value_for_key(key: str) -> Any:
    return [] if key in {"tools", "coursework"} else ""


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not normalize_text(value)
    if isinstance(value, list):
        return len(value) == 0
    return False


def _get_list(payload: Dict[str, Any], key: str) -> List[Any]:
    value = payload.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _build_cross_section_skip_titles(
    parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any], key: str
) -> List[str]:
    titles: List[str] = []
    for payload in (optimizer_payload, parser_payload):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                normalized = normalize_text(str(item)).lower()
                if normalized:
                    titles.append(normalized)
    return titles
