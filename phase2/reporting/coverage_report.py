"""Reporting helpers for identifying unrecovered source-backed content in Phase 2 results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.finalize import _is_valid_social_candidate
from phase2.reconciliation.grouped import (
    _build_cross_section_skip_titles,
    _candidate_to_schema,
    _get_list,
    _infer_schema_keys,
    _to_comparable,
)
from phase2.reconciliation.grouped_match import (
    match_education_entries,
    match_experience_entries,
    match_project_entries,
    match_training_entries,
)
from phase2.reconciliation.lists import (
    _certification_comparison_key,
    _comparison_key,
    _filter_recoverable_certification_values,
    _filter_recoverable_language_values,
    _filter_recoverable_skill_values,
    _technical_skill_comparison_key,
)
from phase2.reconciliation.normalize import normalize_text


def load_phase2_results(path: str | Path) -> List[Dict[str, Any]]:
    """Load a Phase 2 JSONL results file."""

    results_path = Path(path)
    with results_path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def analyze_phase2_results(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze Phase 2 results and report unrecovered source-backed content."""

    analyzed_rows: List[Dict[str, Any]] = []
    summary = _empty_summary()

    for row in rows:
        analyzed = analyze_phase2_result_row(row)
        if analyzed["missing"]:
            analyzed_rows.append(analyzed)
            _update_summary(summary, analyzed["missing"])

    return {
        "total_rows": len(rows),
        "rows_with_missing_source_backed_content": len(analyzed_rows),
        "summary": summary,
        "rows": analyzed_rows,
    }


def analyze_phase2_result_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze one Phase 2 result row for unrecovered source-backed content."""

    phase2_input = Phase2Input.model_validate(row.get("phase2_input", {}))
    parser_payload = row.get("parser_payload", {})
    validated_data = row.get("validated_cv", {}).get("data", {})
    missing: Dict[str, Any] = {}

    list_missing = _analyze_list_fields(phase2_input, parser_payload, validated_data)
    grouped_missing = _analyze_grouped_fields(phase2_input, parser_payload, validated_data)
    singleton_missing = _analyze_singletons(phase2_input, parser_payload, validated_data)

    missing.update({key: value for key, value in list_missing.items() if value})
    missing.update({key: value for key, value in grouped_missing.items() if value})
    missing.update({key: value for key, value in singleton_missing.items() if value})

    return {
        "cv_id": row.get("cv_id"),
        "file_path": row.get("file_path"),
        "missing": missing,
    }


def _analyze_list_fields(
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    validated_data: Dict[str, Any],
) -> Dict[str, Dict[str, List[str]]]:
    config = {
        "technical_skills": {
            "phase2_values": _filter_recoverable_skill_values(phase2_input.skill_candidates),
            "parser_values": _filter_recoverable_skill_values(_get_string_list(parser_payload, "technical_skills")),
            "comparison": _technical_skill_comparison_key,
        },
        "languages": {
            "phase2_values": _filter_recoverable_language_values(phase2_input.language_candidates),
            "parser_values": _filter_recoverable_language_values(_get_string_list(parser_payload, "languages")),
            "comparison": _comparison_key,
        },
        "certifications": {
            "phase2_values": _filter_recoverable_certification_values(phase2_input.certification_candidates),
            "parser_values": _filter_recoverable_certification_values(_get_string_list(parser_payload, "certifications")),
            "comparison": _certification_comparison_key,
        },
    }

    missing: Dict[str, Dict[str, List[str]]] = {}
    for field_name, field_config in config.items():
        comparison = field_config["comparison"]
        final_keys = {
            comparison(normalize_text(value))
            for value in _get_string_list(validated_data, field_name)
            if normalize_text(value)
        }
        phase2_missing = [
            value
            for value in field_config["phase2_values"]
            if comparison(normalize_text(value)) not in final_keys
        ]
        parser_missing = [
            value
            for value in field_config["parser_values"]
            if comparison(normalize_text(value)) not in final_keys
        ]
        if phase2_missing or parser_missing:
            missing[field_name] = {
                "phase2_input": _dedupe_strings(phase2_missing),
                "parser": _dedupe_strings(parser_missing),
            }
    return missing


def _analyze_grouped_fields(
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    validated_data: Dict[str, Any],
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    config = {
        "experience": {
            "phase2_candidates": phase2_input.experience_candidates,
            "parser_entries": _get_list(parser_payload, "experience"),
            "matcher": match_experience_entries,
        },
        "projects": {
            "phase2_candidates": phase2_input.project_candidates,
            "parser_entries": _get_list(parser_payload, "projects"),
            "matcher": match_project_entries,
        },
        "education": {
            "phase2_candidates": phase2_input.education_candidates,
            "parser_entries": _get_list(parser_payload, "education"),
            "matcher": match_education_entries,
        },
        "trainings_courses": {
            "phase2_candidates": phase2_input.training_candidates,
            "parser_entries": _get_list(parser_payload, "trainings_courses"),
            "matcher": match_training_entries,
            "skip_titles": _build_cross_section_skip_titles(parser_payload, validated_data, "certifications"),
        },
    }

    missing: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for field_name, field_config in config.items():
        final_entries = _get_list(validated_data, field_name)
        schema_keys = _infer_schema_keys(field_name, final_entries, field_config["parser_entries"])
        final_comparables = [
            _to_comparable(field_name, entry, "validated")
            for entry in final_entries
            if isinstance(entry, dict)
        ]

        phase2_missing: List[Dict[str, Any]] = []
        for candidate in field_config["phase2_candidates"]:
            candidate_entry = _candidate_to_schema(field_name, candidate, schema_keys)
            candidate_title = normalize_text(
                _first_non_empty(
                    candidate_entry,
                    "title",
                    "name",
                    "course_name",
                    "training_name",
                    "project_name",
                )
            ).lower()
            if candidate_title and candidate_title in field_config.get("skip_titles", []):
                continue
            comparable = _to_comparable(field_name, candidate_entry, "phase2_input")
            if not _has_group_match(final_comparables, comparable, field_config["matcher"]):
                phase2_missing.append(candidate)

        parser_missing: List[Dict[str, Any]] = []
        for parser_entry in field_config["parser_entries"]:
            if not isinstance(parser_entry, dict):
                continue
            comparable = _to_comparable(field_name, parser_entry, "parser")
            if not _has_group_match(final_comparables, comparable, field_config["matcher"]):
                parser_missing.append(parser_entry)

        if phase2_missing or parser_missing:
            missing[field_name] = {
                "phase2_input": phase2_missing,
                "parser": parser_missing,
            }

    return missing


def _analyze_singletons(
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    validated_data: Dict[str, Any],
) -> Dict[str, Dict[str, List[str]]]:
    missing: Dict[str, Dict[str, List[str]]] = {}
    for field_name in ("linkedin", "github"):
        final_value = normalize_text(str(validated_data.get(field_name, "")))
        if final_value:
            continue

        phase2_candidates = [
            candidate
            for candidate in phase2_input.contact_candidates.get(field_name, [])
            if _is_valid_social_candidate(field_name, candidate)
        ]
        parser_values: List[str] = []
        parser_value = parser_payload.get(field_name)
        if isinstance(parser_value, str) and _is_valid_social_candidate(field_name, parser_value):
            parser_values.append(parser_value.strip())

        if phase2_candidates or parser_values:
            missing[field_name] = {
                "phase2_input": _dedupe_strings(phase2_candidates),
                "parser": _dedupe_strings(parser_values),
            }

    return missing


def _has_group_match(final_entries: Sequence[Any], candidate: Any, matcher) -> bool:
    for final_entry in final_entries:
        result = matcher(final_entry, candidate)
        if result.matched:
            return True
    return False


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


def _dedupe_strings(values: Sequence[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        deduped.append(normalized)
    return deduped


def _first_non_empty(entry: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = entry.get(key)
        if value:
            return str(value)
    return ""


def _empty_summary() -> Dict[str, Dict[str, int]]:
    fields = [
        "technical_skills",
        "languages",
        "certifications",
        "experience",
        "projects",
        "education",
        "trainings_courses",
        "linkedin",
        "github",
    ]
    return {
        field: {
            "rows_affected": 0,
            "phase2_input_missing_count": 0,
            "parser_missing_count": 0,
        }
        for field in fields
    }


def _update_summary(summary: Dict[str, Dict[str, int]], missing: Dict[str, Any]) -> None:
    for field_name, details in missing.items():
        if field_name not in summary:
            continue
        summary[field_name]["rows_affected"] += 1
        summary[field_name]["phase2_input_missing_count"] += len(details.get("phase2_input", []))
        summary[field_name]["parser_missing_count"] += len(details.get("parser", []))
