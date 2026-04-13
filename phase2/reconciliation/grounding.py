"""Grounding helpers for deterministic Phase 2 reconciliation."""

from typing import Any, Dict, List, Optional

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.normalize import (
    normalize_location_string,
    normalize_phone,
    normalize_skill,
    normalize_text,
    normalize_url,
)


def build_evidence_text(phase2_input: Phase2Input) -> str:
    """Build a combined evidence text from stable Phase 2 input only."""

    parts: List[str] = [phase2_input.full_text, phase2_input.uncategorized_text]
    parts.extend(phase2_input.canonical_sections.values())
    for values in phase2_input.contact_candidates.values():
        parts.extend(values)
    parts.extend(phase2_input.skill_candidates)
    parts.extend(phase2_input.language_candidates)
    parts.extend(phase2_input.certification_candidates)
    return "\n".join(part for part in parts if part)


def find_grounding_sources(
    value: str,
    phase2_input: Phase2Input,
    parser_payload: Optional[Dict[str, Any]] = None,
    field_kind: str = "text",
) -> List[str]:
    """Return grounded evidence sources for a candidate value."""

    if not value:
        return []

    sources: List[str] = []
    normalized_value = _normalize_for_grounding(value, field_kind)
    evidence_text = build_evidence_text(phase2_input)

    if _value_in_phase2_input(value, normalized_value, phase2_input, field_kind):
        sources.append("phase2_input")
    if _value_in_text(normalized_value, evidence_text, field_kind):
        sources.append("full_text")

    if parser_payload:
        for key, payload_value in parser_payload.items():
            if isinstance(payload_value, list):
                if any(
                    _normalize_for_grounding(str(item), field_kind) == normalized_value
                    for item in payload_value
                ):
                    sources.append("parser:{0}".format(key))
            elif payload_value is not None:
                if _normalize_for_grounding(str(payload_value), field_kind) == normalized_value:
                    sources.append("parser:{0}".format(key))

    return list(dict.fromkeys(sources))


def is_value_grounded(
    value: str,
    phase2_input: Phase2Input,
    parser_payload: Optional[Dict[str, Any]] = None,
    field_kind: str = "text",
) -> bool:
    """Return whether a value is grounded in Phase 2 evidence or parser output."""

    return bool(find_grounding_sources(value, phase2_input, parser_payload, field_kind))


def _value_in_phase2_input(
    value: str, normalized_value: str, phase2_input: Phase2Input, field_kind: str
) -> bool:
    if field_kind in {"email", "phone", "url", "location", "name"}:
        for candidate_list in phase2_input.contact_candidates.values():
            if any(
                _normalize_for_grounding(candidate, field_kind) == normalized_value
                for candidate in candidate_list
            ):
                return True
    if field_kind == "skill":
        return any(
            _normalize_for_grounding(candidate, field_kind) == normalized_value
            for candidate in phase2_input.skill_candidates
        )
    if field_kind == "language":
        return any(
            _normalize_for_grounding(candidate, field_kind) == normalized_value
            for candidate in phase2_input.language_candidates
        )
    if field_kind == "certification":
        return any(
            _normalize_for_grounding(candidate, field_kind) == normalized_value
            for candidate in phase2_input.certification_candidates
        )
    return False


def _value_in_text(normalized_value: str, evidence_text: str, field_kind: str) -> bool:
    normalized_evidence = _normalize_for_grounding(evidence_text, field_kind if field_kind != "skill" else "text")
    if field_kind == "phone":
        return normalized_value and normalized_value in normalize_phone(evidence_text)
    if field_kind == "url":
        return normalized_value and normalized_value in normalize_url(evidence_text)
    if field_kind in {"skill", "language", "certification", "location", "name"}:
        return normalized_value and normalized_value in normalized_evidence
    return normalized_value and normalized_value in normalized_evidence


def _normalize_for_grounding(value: str, field_kind: str) -> str:
    if field_kind == "phone":
        return normalize_phone(value)
    if field_kind == "url":
        return normalize_url(value)
    if field_kind == "location":
        return normalize_location_string(value).lower()
    if field_kind in {"skill", "language", "certification"}:
        return normalize_skill(value).lower()
    return normalize_text(value).lower()
