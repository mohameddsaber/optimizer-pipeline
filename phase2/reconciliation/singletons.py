"""Deterministic singleton reconciliation functions."""

import re
from typing import Any, Dict, List, Optional

from contracts.phase2_input import Phase2Input
from phase2.contracts.validated_cv import ReconciledField
from phase2.reconciliation.grounding import find_grounding_sources, is_value_grounded
from phase2.reconciliation.normalize import (
    dedupe_preserve_order,
    normalize_location_string,
    normalize_phone,
    normalize_text,
    normalize_url,
)

_EMAIL_RE = re.compile(r"^[\w.\-+%]+@[\w.\-]+\.[A-Za-z]{2,}$")


def reconcile_name(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[str]:
    """Reconcile a name field conservatively."""

    notes: List[str] = []
    parser_name = _get_string(parser_payload, "name")
    phase2_names = phase2_input.contact_candidates.get("name", [])
    optimizer_name = _get_string(optimizer_payload, "name")

    if parser_name:
        grounded = is_value_grounded(parser_name, phase2_input, parser_payload, "name")
        return ReconciledField[str](
            value=parser_name,
            source="parser",
            confidence=0.9,
            grounded=grounded,
            notes=["accepted parser name"],
        )

    if phase2_names:
        value = phase2_names[0]
        return ReconciledField[str](
            value=value,
            source="phase2_input",
            confidence=0.88,
            grounded=True,
            notes=["accepted top Phase2Input name candidate"],
        )

    if optimizer_name and is_value_grounded(optimizer_name, phase2_input, parser_payload, "name"):
        return ReconciledField[str](
            value=optimizer_name,
            source="optimizer",
            confidence=0.7,
            grounded=True,
            notes=["accepted grounded optimizer name"],
        )

    if optimizer_name:
        notes.append("rejected ungrounded optimizer name")
    return ReconciledField[str](value=None, source="unresolved", confidence=0.0, grounded=False, notes=notes)


def reconcile_email(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[str]:
    """Reconcile email with Phase2Input contact candidates first."""

    return _reconcile_contact_like_field(
        "email",
        phase2_input,
        phase2_input.contact_candidates.get("email", []),
        parser_payload,
        optimizer_payload,
        validator=_is_valid_email,
        normalizer=normalize_text,
        field_kind="email",
    )


def reconcile_phone_number(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[str]:
    """Reconcile phone numbers, preferring Phase2Input evidence."""

    return _reconcile_contact_like_field(
        "phone_number",
        phase2_input,
        phase2_input.contact_candidates.get("phone", []),
        parser_payload,
        optimizer_payload,
        validator=_is_valid_phone,
        normalizer=normalize_phone,
        field_kind="phone",
    )


def reconcile_location(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[str]:
    """Reconcile location conservatively, rejecting unsupported specificity."""

    notes: List[str] = []
    phase2_candidates = [
        normalize_location_string(value) for value in phase2_input.contact_candidates.get("location", [])
    ]
    parser_value = _get_string(parser_payload, "location")
    parser_value = normalize_location_string(parser_value) if parser_value else None
    optimizer_value = _get_string(optimizer_payload, "location")
    optimizer_value = normalize_location_string(optimizer_value) if optimizer_value else None

    if parser_value and is_value_grounded(parser_value, phase2_input, parser_payload, "location"):
        return ReconciledField[str](
            value=parser_value,
            source="parser",
            confidence=0.86,
            grounded=True,
            notes=["accepted grounded parser location"],
        )

    if phase2_candidates:
        return ReconciledField[str](
            value=phase2_candidates[0],
            source="phase2_input",
            confidence=0.84,
            grounded=True,
            notes=["accepted Phase2Input location candidate"],
        )

    if optimizer_value and is_value_grounded(optimizer_value, phase2_input, parser_payload, "location"):
        return ReconciledField[str](
            value=optimizer_value,
            source="optimizer",
            confidence=0.72,
            grounded=True,
            notes=["accepted grounded optimizer location"],
        )

    if optimizer_value:
        notes.append("rejected ungrounded or over-specific optimizer location")
    return ReconciledField[str](value=None, source="unresolved", confidence=0.0, grounded=False, notes=notes)


def reconcile_linkedin(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[str]:
    """Reconcile LinkedIn URL candidates."""

    return _reconcile_contact_like_field(
        "linkedin",
        phase2_input,
        phase2_input.contact_candidates.get("linkedin", []),
        parser_payload,
        optimizer_payload,
        validator=lambda value: "linkedin" in normalize_url(value),
        normalizer=normalize_url,
        field_kind="url",
    )


def reconcile_github(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[str]:
    """Reconcile GitHub URL candidates."""

    return _reconcile_contact_like_field(
        "github",
        phase2_input,
        phase2_input.contact_candidates.get("github", []),
        parser_payload,
        optimizer_payload,
        validator=lambda value: "github" in normalize_url(value),
        normalizer=normalize_url,
        field_kind="url",
    )


def _reconcile_contact_like_field(
    field_name: str,
    phase2_input: Phase2Input,
    phase2_candidates: List[str],
    parser_payload: Dict[str, Any],
    optimizer_payload: Dict[str, Any],
    validator,
    normalizer,
    field_kind: str,
) -> ReconciledField[str]:
    notes: List[str] = []
    deduped_phase2 = dedupe_preserve_order(
        [candidate for candidate in phase2_candidates if validator(candidate)],
        key_fn=normalizer,
    )
    if deduped_phase2:
        return ReconciledField[str](
            value=deduped_phase2[0],
            source="phase2_input",
            confidence=0.94,
            grounded=True,
            notes=["accepted Phase2Input candidate for {0}".format(field_name)],
        )

    parser_value = _get_string(parser_payload, field_name)
    if parser_value and validator(parser_value):
        grounded = is_value_grounded(parser_value, phase2_input, parser_payload, field_kind)
        return ReconciledField[str](
            value=parser_value,
            source="parser",
            confidence=0.89,
            grounded=grounded,
            notes=["accepted parser value for {0}".format(field_name)],
        )

    if parser_value:
        notes.append("ignored malformed parser {0}".format(field_name))

    optimizer_value = _get_string(optimizer_payload, field_name)
    if optimizer_value and validator(optimizer_value):
        grounded_sources = find_grounding_sources(optimizer_value, phase2_input, parser_payload, field_kind)
        if grounded_sources:
            return ReconciledField[str](
                value=optimizer_value,
                source="optimizer",
                confidence=0.74,
                grounded=True,
                notes=["accepted grounded optimizer {0}".format(field_name)] + grounded_sources,
            )
        notes.append("rejected ungrounded optimizer {0}".format(field_name))

    return ReconciledField[str](value=None, source="unresolved", confidence=0.0, grounded=False, notes=notes)


def _get_string(payload: Dict[str, Any], key: str) -> Optional[str]:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = normalize_text(value)
    return value or None


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(normalize_text(value)))


def _is_valid_phone(value: str) -> bool:
    digits = normalize_phone(value)
    digit_count = len([char for char in digits if char.isdigit()])
    return digit_count >= 8
