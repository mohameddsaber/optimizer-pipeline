"""Deterministic list reconciliation functions."""

from typing import Any, Dict, Iterable, List, Tuple

from contracts.phase2_input import Phase2Input
from phase2.contracts.validated_cv import ReconciledField
from phase2.reconciliation.grounding import find_grounding_sources, is_value_grounded
from phase2.reconciliation.normalize import dedupe_preserve_order, normalize_skill, normalize_text


def reconcile_technical_skills(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[List[str]]:
    """Merge deterministic technical skill candidates."""

    return _reconcile_list_field(
        phase2_values=phase2_input.skill_candidates,
        parser_values=_get_string_list(parser_payload, "technical_skills"),
        optimizer_values=_get_string_list(optimizer_payload, "technical_skills"),
        phase2_input=phase2_input,
        parser_payload=parser_payload,
        field_kind="skill",
        normalizer=normalize_skill,
    )


def reconcile_languages(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[List[str]]:
    """Merge deterministic language candidates."""

    return _reconcile_list_field(
        phase2_values=phase2_input.language_candidates,
        parser_values=_get_string_list(parser_payload, "languages"),
        optimizer_values=_get_string_list(optimizer_payload, "languages"),
        phase2_input=phase2_input,
        parser_payload=parser_payload,
        field_kind="language",
        normalizer=normalize_skill,
    )


def reconcile_certifications(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> ReconciledField[List[str]]:
    """Merge deterministic certification candidates."""

    return _reconcile_list_field(
        phase2_values=phase2_input.certification_candidates,
        parser_values=_get_string_list(parser_payload, "certifications"),
        optimizer_values=_get_string_list(optimizer_payload, "certifications"),
        phase2_input=phase2_input,
        parser_payload=parser_payload,
        field_kind="certification",
        normalizer=normalize_skill,
    )


def _reconcile_list_field(
    phase2_values: List[str],
    parser_values: List[str],
    optimizer_values: List[str],
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    field_kind: str,
    normalizer,
) -> ReconciledField[List[str]]:
    notes: List[str] = []
    values_with_source: List[Tuple[str, str]] = []
    contributing_sources = set()

    for value in phase2_values:
        values_with_source.append((value, "phase2_input"))
        contributing_sources.add("phase2_input")
    for value in parser_values:
        values_with_source.append((value, "parser"))
        contributing_sources.add("parser")

    for value in optimizer_values:
        if is_value_grounded(value, phase2_input, parser_payload, field_kind):
            values_with_source.append((value, "optimizer"))
            contributing_sources.add("optimizer")
        else:
            notes.append("rejected ungrounded optimizer value: {0}".format(value))

    deduped: List[str] = []
    seen = set()
    used_sources = set()
    for value, source in values_with_source:
        normalized = normalizer(value)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
        used_sources.add(source)

    if not deduped:
        return ReconciledField[List[str]](
            value=[],
            source="unresolved",
            confidence=0.0,
            grounded=False,
            notes=notes,
        )

    effective_sources = contributing_sources if len(contributing_sources) > 1 else used_sources
    source = "merged" if len(effective_sources) > 1 else list(effective_sources)[0]
    grounded = all(
        is_value_grounded(value, phase2_input, parser_payload, field_kind) or source_name == "parser"
        for value, source_name in values_with_source
        if normalizer(value).lower() in {item.lower() for item in deduped}
    )
    confidence = 0.9 if "phase2_input" in used_sources else 0.84 if "parser" in used_sources else 0.72
    if "optimizer" in used_sources and source == "merged":
        notes.append("accepted grounded optimizer additions")

    return ReconciledField[List[str]](
        value=deduped,
        source=source,
        confidence=confidence,
        grounded=grounded,
        notes=notes,
    )


def _get_string_list(payload: Dict[str, Any], key: str) -> List[str]:
    value = payload.get(key)
    if value is None:
        return []
    if isinstance(value, str):
        return [normalize_text(value)] if normalize_text(value) else []
    if not isinstance(value, list):
        return []
    values = [normalize_text(str(item)) for item in value if normalize_text(str(item))]
    return dedupe_preserve_order(values, key_fn=lambda item: item.lower())
