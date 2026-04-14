"""Coverage-mode Phase 2 assembly."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from contracts.phase2_input import Phase2Input
from phase2.contracts.validated_cv import CoverageAudit, ValidatedCv
from phase2.reconciliation.grouped import (
    recover_education,
    recover_experience,
    recover_projects,
    recover_trainings_courses,
)
from phase2.reconciliation.lists import (
    recover_certifications,
    recover_languages,
    recover_soft_skills,
    recover_technical_skills,
)
from phase2.reconciliation.supplemental import recover_supplemental_content


def reconcile_phase2_coverage_mode(
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    optimizer_payload: Dict[str, Any],
) -> ValidatedCv:
    """Patch optimizer output with missing source-backed content without changing schema."""

    data = deepcopy(optimizer_payload)
    audit = CoverageAudit()

    data["technical_skills"], technical_audit = recover_technical_skills(phase2_input, parser_payload, optimizer_payload)
    data["soft_skills"], soft_skills_audit = recover_soft_skills(phase2_input, parser_payload, optimizer_payload)
    data["languages"], languages_audit = recover_languages(phase2_input, parser_payload, optimizer_payload)
    data["certifications"], certifications_audit = recover_certifications(phase2_input, parser_payload, optimizer_payload)
    data["experience"], experience_audit = recover_experience(phase2_input, parser_payload, optimizer_payload)
    data["projects"], projects_audit = recover_projects(phase2_input, parser_payload, optimizer_payload)
    data["education"], education_audit = recover_education(phase2_input, parser_payload, optimizer_payload)
    data["trainings_courses"], trainings_audit = recover_trainings_courses(phase2_input, parser_payload, optimizer_payload)
    supplemental_data, supplemental_audit = recover_supplemental_content(
        phase2_input,
        parser_payload,
        optimizer_payload,
    )
    data["awards"] = supplemental_data["awards"]
    data["achievements"] = supplemental_data["achievements"]
    data["activities"] = supplemental_data["activities"]
    data["publications"] = supplemental_data["publications"]

    _merge_audit(audit, technical_audit)
    _merge_audit(audit, soft_skills_audit)
    _merge_audit(audit, languages_audit)
    _merge_audit(audit, certifications_audit)
    _merge_audit(audit, experience_audit)
    _merge_audit(audit, projects_audit)
    _merge_audit(audit, education_audit)
    _merge_audit(audit, trainings_audit)
    _merge_audit(audit, supplemental_audit)

    _recover_trivial_singletons(data, phase2_input, parser_payload, audit)

    return ValidatedCv(data=data, audit=audit, mode="coverage")


def reconcile_phase2_milestone1(
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    optimizer_payload: Dict[str, Any],
) -> ValidatedCv:
    """Backward-compatible wrapper now using coverage mode."""

    return reconcile_phase2_coverage_mode(phase2_input, parser_payload, optimizer_payload)


def reconcile_phase2_milestone2(
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    optimizer_payload: Dict[str, Any],
) -> ValidatedCv:
    """Backward-compatible wrapper now using coverage mode."""

    return reconcile_phase2_coverage_mode(phase2_input, parser_payload, optimizer_payload)


def _merge_audit(audit: CoverageAudit, patch: Dict[str, Any]) -> None:
    audit.recovered_items.extend(patch.get("recovered_items", []))
    audit.recovered_fields.extend(patch.get("recovered_fields", []))
    audit.notes.extend(patch.get("notes", []))


def _recover_trivial_singletons(
    data: Dict[str, Any],
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    audit: CoverageAudit,
) -> None:
    for field_name, candidate_key in (("linkedin", "linkedin"), ("github", "github")):
        if normalize_value(data.get(field_name)):
            continue
        candidates = phase2_input.contact_candidates.get(candidate_key, [])
        valid_candidates = [candidate for candidate in candidates if _is_valid_social_candidate(field_name, candidate)]
        if valid_candidates:
            data[field_name] = valid_candidates[0]
            audit.recovered_fields.append(field_name)
            audit.notes.append("Recovered missing {0} from source evidence".format(field_name))
            continue
        parser_value = parser_payload.get(field_name)
        if isinstance(parser_value, str) and _is_valid_social_candidate(field_name, parser_value):
            data[field_name] = parser_value.strip()
            audit.recovered_fields.append(field_name)
            audit.notes.append("Recovered missing {0} from parser evidence".format(field_name))


def normalize_value(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _is_valid_social_candidate(field_name: str, value: str) -> bool:
    normalized = normalize_value(value)
    if not normalized or "\n" in normalized or " " in normalized:
        return False
    lowered = normalized.lower()
    if field_name == "linkedin":
        return "linkedin.com/" in lowered or lowered.startswith("linkedin/")
    if field_name == "github":
        return "github.com/" in lowered or lowered.startswith("github/")
    return False
