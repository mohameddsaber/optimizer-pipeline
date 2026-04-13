"""Public grouped reconciliation functions for Phase 2 Milestone 2."""

import re
from typing import Any, Dict, List, Sequence, Tuple

from contracts.phase2_input import Phase2Input
from phase2.contracts.validated_cv import (
    ReconciledField,
    ValidatedEducationEntry,
    ValidatedExperienceEntry,
    ValidatedProjectEntry,
    ValidatedTrainingEntry,
)
from phase2.reconciliation.grounding import is_value_grounded
from phase2.reconciliation.grouped_match import (
    ComparableGroupedEntry,
    MatchResult,
    match_education_entries,
    match_experience_entries,
    match_project_entries,
    match_training_entries,
)
from phase2.reconciliation.grouped_merge import (
    merge_education_group,
    merge_experience_group,
    merge_project_group,
    merge_training_group,
)
from phase2.reconciliation.grouped_normalize import (
    normalize_company_name,
    normalize_date_range,
    normalize_description_text,
    normalize_institution_name,
    normalize_project_name,
    normalize_role_title,
)

_DATE_RE = re.compile(
    r"(?i)(?:\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b[^,\n|]{0,20}\d{4}|\b\d{1,2}/\d{4}\b(?:\s*[-–]\s*(?:present|\d{1,2}/\d{4}))?|\b\d{4}\b(?:\s*[-–]\s*(?:present|\d{4}))?)"
)


def reconcile_experience(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[List[ValidatedExperienceEntry]]:
    """Reconcile grouped experience entries deterministically."""

    return _reconcile_grouped_field(
        phase2_input,
        parser_payload,
        optimizer_payload,
        "experience",
        phase2_input.experience_candidates,
        match_experience_entries,
        merge_experience_group,
    )


def reconcile_projects(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[List[ValidatedProjectEntry]]:
    """Reconcile grouped project entries deterministically."""

    return _reconcile_grouped_field(
        phase2_input,
        parser_payload,
        optimizer_payload,
        "projects",
        phase2_input.project_candidates,
        match_project_entries,
        merge_project_group,
    )


def reconcile_education(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[List[ValidatedEducationEntry]]:
    """Reconcile grouped education entries deterministically."""

    return _reconcile_grouped_field(
        phase2_input,
        parser_payload,
        optimizer_payload,
        "education",
        phase2_input.education_candidates,
        match_education_entries,
        merge_education_group,
    )


def reconcile_trainings_courses(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[List[ValidatedTrainingEntry]]:
    """Reconcile grouped training/course entries deterministically."""

    return _reconcile_grouped_field(
        phase2_input,
        parser_payload,
        optimizer_payload,
        "trainings_courses",
        phase2_input.training_candidates,
        match_training_entries,
        merge_training_group,
    )


def _reconcile_grouped_field(
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    optimizer_payload: Dict[str, Any],
    field_name: str,
    phase2_candidates: Sequence[Dict[str, Any]],
    matcher,
    merger,
) -> ReconciledField[List[Any]]:
    phase2_entries = [_coerce_grouped_candidate(item, field_name) for item in phase2_candidates]
    parser_entries = [_coerce_structured_entry(item, field_name, "parser") for item in _get_list(parser_payload, field_name)]
    optimizer_entries = [_coerce_structured_entry(item, field_name, "optimizer") for item in _get_list(optimizer_payload, field_name)]

    groups: List[List[ComparableGroupedEntry]] = []
    field_notes: List[str] = []

    for parser_entry in parser_entries:
        _append_to_matching_or_new(groups, parser_entry, matcher)

    for phase2_entry in phase2_entries:
        matched = _append_to_matching_or_new(groups, phase2_entry, matcher)
        if not matched:
            field_notes.append("recovered candidate-backed {0} entry".format(field_name))

    for optimizer_entry in optimizer_entries:
        if not _is_group_entry_grounded(optimizer_entry, phase2_input, parser_payload, field_name):
            field_notes.append("rejected optimizer-only {0} entry: {1}".format(field_name, optimizer_entry.raw_text))
            continue
        matched = _append_to_matching_or_new(groups, optimizer_entry, matcher)
        if not matched:
            field_notes.append("recovered grounded optimizer {0} entry".format(field_name))

    merged_entries = [merger(group) for group in groups if group]
    if not merged_entries:
        return ReconciledField[List[Any]](
            value=[],
            source="unresolved",
            confidence=0.0,
            grounded=False,
            notes=field_notes,
        )

    source = _field_source_from_groups(groups)
    grounded = all(entry.grounded for entry in merged_entries)
    confidence = 0.9 if any(any(item.source == "parser" for item in group) for group in groups) else 0.82
    if any(len(group) > 1 for group in groups):
        field_notes.append("merged matched {0} entries".format(field_name))

    return ReconciledField[List[Any]](
        value=merged_entries,
        source=source,
        confidence=confidence,
        grounded=grounded,
        notes=field_notes,
    )


def _find_matching_group(
    groups: List[List[ComparableGroupedEntry]], candidate: ComparableGroupedEntry, matcher
) -> int:
    best_index = None
    best_score = 0.0
    for index, group in enumerate(groups):
        for existing in group:
            result = matcher(existing, candidate)
            if result.matched and result.score > best_score:
                best_index = index
                best_score = result.score
    return best_index


def _append_to_matching_or_new(
    groups: List[List[ComparableGroupedEntry]], candidate: ComparableGroupedEntry, matcher
) -> bool:
    matched_group_index = _find_matching_group(groups, candidate, matcher)
    if matched_group_index is not None:
        groups[matched_group_index].append(candidate)
        return True
    groups.append([candidate])
    return False


def _coerce_grouped_candidate(item: Dict[str, Any], field_name: str) -> ComparableGroupedEntry:
    text = str(item.get("text", "")).strip()
    hints = dict(item.get("hints", {}))
    if field_name == "experience":
        return ComparableGroupedEntry(
            kind=field_name,
            source="phase2_input",
            raw_text=text,
            primary_name=_extract_primary_from_text(text),
            secondary_name=_extract_secondary_from_text(text),
            date_range=_extract_date_range(text, hints),
            description="",
            hints=hints,
        )
    if field_name == "projects":
        return ComparableGroupedEntry(
            kind=field_name,
            source="phase2_input",
            raw_text=text,
            primary_name=_extract_primary_from_text(text),
            date_range=_extract_date_range(text, hints),
            description="",
            technologies=_extract_technologies(text),
            hints=hints,
        )
    if field_name == "education":
        return ComparableGroupedEntry(
            kind=field_name,
            source="phase2_input",
            raw_text=text,
            primary_name=_extract_degree_from_text(text),
            secondary_name=_extract_institution_from_text(text),
            date_range=_extract_date_range(text, hints),
            description="",
            hints=hints,
        )
    return ComparableGroupedEntry(
        kind=field_name,
        source="phase2_input",
        raw_text=text,
        primary_name=_extract_primary_from_text(text),
        secondary_name=_extract_secondary_from_text(text),
        date_range=_extract_date_range(text, hints),
        description="",
        hints=hints,
    )


def _coerce_structured_entry(item: Any, field_name: str, source: str) -> ComparableGroupedEntry:
    if isinstance(item, str):
        item = {"text": item}
    if not isinstance(item, dict):
        item = {"text": str(item)}

    text = normalize_description_text(
        " ".join(
            str(item.get(key, ""))
            for key in ("text", "description", "summary", "details")
            if item.get(key)
        )
    )

    if field_name == "experience":
        return ComparableGroupedEntry(
            kind=field_name,
            source=source,
            raw_text=text or normalize_description_text(
                " | ".join(
                    part for part in [
                        _pick(item, "title", "job_title", "role", "position"),
                        _pick(item, "company", "organization", "employer"),
                        _compose_date(item),
                    ] if part
                )
            ),
            primary_name=normalize_role_title(_pick(item, "job_title", "title", "role", "position")),
            secondary_name=normalize_company_name(_pick(item, "company", "organization", "employer")),
            date_range=normalize_date_range(_compose_date(item)),
            description=text,
            hints=dict(item),
        )
    if field_name == "projects":
        return ComparableGroupedEntry(
            kind=field_name,
            source=source,
            raw_text=text or normalize_description_text(
                " | ".join(part for part in [_pick(item, "name", "project_name", "title"), _compose_date(item)] if part)
            ),
            primary_name=normalize_project_name(_pick(item, "name", "project_name", "title")),
            date_range=normalize_date_range(_compose_date(item)),
            description=text,
            technologies=_coerce_list(item.get("technologies") or item.get("tech_stack") or []),
            hints=dict(item),
        )
    if field_name == "education":
        return ComparableGroupedEntry(
            kind=field_name,
            source=source,
            raw_text=text or normalize_description_text(
                " | ".join(
                    part for part in [
                        _pick(item, "degree", "qualification", "field_of_study"),
                        _pick(item, "institution", "school", "university"),
                        _compose_date(item),
                    ] if part
                )
            ),
            primary_name=normalize_role_title(_pick(item, "degree", "qualification", "field_of_study")),
            secondary_name=normalize_institution_name(_pick(item, "institution", "school", "university")),
            date_range=normalize_date_range(_compose_date(item)),
            description=text,
            hints=dict(item),
        )
    return ComparableGroupedEntry(
        kind=field_name,
        source=source,
        raw_text=text or normalize_description_text(
            " | ".join(
                part for part in [
                    _pick(item, "name", "course_name", "title", "training_name"),
                    _pick(item, "provider", "institution", "issuer"),
                    _compose_date(item),
                ] if part
            )
        ),
        primary_name=normalize_project_name(_pick(item, "name", "course_name", "title", "training_name")),
        secondary_name=normalize_company_name(_pick(item, "provider", "institution", "issuer")),
        date_range=normalize_date_range(_compose_date(item)),
        description=text,
        hints=dict(item),
    )


def _is_group_entry_grounded(
    entry: ComparableGroupedEntry,
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    field_name: str,
) -> bool:
    evidence_values = [
        entry.primary_name,
        entry.secondary_name,
        entry.date_range,
        entry.raw_text[:160],
    ]
    kinds = {
        "experience": "text",
        "projects": "text",
        "education": "text",
        "trainings_courses": "text",
    }
    field_kind = kinds[field_name]
    return any(
        value and is_value_grounded(value, phase2_input, parser_payload, field_kind)
        for value in evidence_values
    )


def _field_source_from_groups(groups: List[List[ComparableGroupedEntry]]) -> str:
    sources = {entry.source for group in groups for entry in group}
    if len(sources) > 1:
        return "merged"
    return list(sources)[0]


def _extract_primary_from_text(text: str) -> str:
    first_line = normalize_description_text(text).split("\n", 1)[0]
    return normalize_project_name(first_line.split("|", 1)[0].strip())


def _extract_secondary_from_text(text: str) -> str:
    parts = [part.strip() for part in normalize_description_text(text).split("|") if part.strip()]
    if len(parts) >= 2:
        return normalize_company_name(parts[1])
    return ""


def _extract_degree_from_text(text: str) -> str:
    parts = [part.strip() for part in normalize_description_text(text).split("|") if part.strip()]
    return normalize_role_title(parts[0]) if parts else ""


def _extract_institution_from_text(text: str) -> str:
    parts = [part.strip() for part in normalize_description_text(text).split("|") if part.strip()]
    if len(parts) >= 2:
        return normalize_institution_name(parts[1])
    return ""


def _extract_date_range(text: str, hints: Dict[str, Any]) -> str:
    hint_dates = hints.get("detected_dates") or hints.get("dates") or []
    if isinstance(hint_dates, list) and hint_dates:
        return normalize_date_range(" ".join(str(item) for item in hint_dates))
    match = _DATE_RE.search(text)
    return normalize_date_range(match.group(0)) if match else ""


def _extract_technologies(text: str) -> List[str]:
    if "|" in text:
        parts = [part.strip() for part in text.split("|") if part.strip()]
        return parts[1:] if len(parts) > 1 else []
    return []


def _pick(item: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _compose_date(item: Dict[str, Any]) -> str:
    explicit = _pick(item, "date_range", "dates", "duration")
    if explicit:
        return explicit
    start = _pick(item, "start_date")
    end = _pick(item, "end_date")
    if start and end:
        return "{0} - {1}".format(start, end)
    return start or end


def _coerce_list(values: Any) -> List[str]:
    if isinstance(values, list):
        return [normalize_description_text(str(value)) for value in values if normalize_description_text(str(value))]
    if isinstance(values, str):
        return [normalize_description_text(values)] if normalize_description_text(values) else []
    return []


def _get_list(payload: Dict[str, Any], key: str) -> List[Any]:
    value = payload.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
