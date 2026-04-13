"""Deterministic merge helpers for grouped reconciliation."""

from typing import Callable, List, Sequence, Type

from phase2.contracts.validated_cv import (
    FieldSource,
    ValidatedEducationEntry,
    ValidatedExperienceEntry,
    ValidatedProjectEntry,
    ValidatedTrainingEntry,
)
from phase2.reconciliation.grouped_match import ComparableGroupedEntry
from phase2.reconciliation.grouped_normalize import (
    normalize_company_name,
    normalize_description_text,
    normalize_institution_name,
    normalize_project_name,
    normalize_role_title,
)
from phase2.reconciliation.normalize import dedupe_preserve_order, normalize_skill, normalize_text


def merge_experience_group(entries: Sequence[ComparableGroupedEntry]) -> ValidatedExperienceEntry:
    """Merge one matched experience group conservatively."""

    base = _choose_base_entry(entries, lambda entry: bool(entry.primary_name or entry.secondary_name))
    description = _richest_grounded_description(entries)
    source = _merged_source(entries)
    notes = _group_notes(entries)
    return ValidatedExperienceEntry(
        title=_pick_first(entries, lambda entry: entry.primary_name, normalize_role_title),
        organization=_pick_first(entries, lambda entry: entry.secondary_name, normalize_company_name),
        date_range=_pick_first(entries, lambda entry: entry.date_range, lambda value: value),
        description=description or normalize_description_text(base.raw_text),
        source=source,
        grounded=source != "optimizer",
        notes=notes,
    )


def merge_project_group(entries: Sequence[ComparableGroupedEntry]) -> ValidatedProjectEntry:
    """Merge one matched project group conservatively."""

    base = _choose_base_entry(entries, lambda entry: bool(entry.primary_name))
    description = _richest_grounded_description(entries)
    technologies = dedupe_preserve_order(
        [tech for entry in entries for tech in entry.technologies if normalize_skill(tech)],
        key_fn=lambda item: normalize_skill(item).lower(),
    )
    source = _merged_source(entries)
    return ValidatedProjectEntry(
        name=_pick_first(entries, lambda entry: entry.primary_name, normalize_project_name),
        date_range=_pick_first(entries, lambda entry: entry.date_range, lambda value: value),
        description=description or normalize_description_text(base.raw_text),
        technologies=technologies,
        source=source,
        grounded=source != "optimizer",
        notes=_group_notes(entries),
    )


def merge_education_group(entries: Sequence[ComparableGroupedEntry]) -> ValidatedEducationEntry:
    """Merge one matched education group conservatively."""

    base = _choose_base_entry(entries, lambda entry: bool(entry.secondary_name or entry.primary_name))
    source = _merged_source(entries)
    return ValidatedEducationEntry(
        institution=_pick_first(entries, lambda entry: entry.secondary_name, normalize_institution_name),
        degree=_pick_first(entries, lambda entry: entry.primary_name, normalize_role_title),
        date_range=_pick_first(entries, lambda entry: entry.date_range, lambda value: value),
        description=_richest_grounded_description(entries) or normalize_description_text(base.raw_text),
        source=source,
        grounded=source != "optimizer",
        notes=_group_notes(entries),
    )


def merge_training_group(entries: Sequence[ComparableGroupedEntry]) -> ValidatedTrainingEntry:
    """Merge one matched training/course group conservatively."""

    base = _choose_base_entry(entries, lambda entry: bool(entry.primary_name))
    source = _merged_source(entries)
    return ValidatedTrainingEntry(
        name=_pick_first(entries, lambda entry: entry.primary_name, normalize_project_name),
        provider=_pick_first(entries, lambda entry: entry.secondary_name, normalize_company_name),
        date_range=_pick_first(entries, lambda entry: entry.date_range, lambda value: value),
        description=_richest_grounded_description(entries) or normalize_description_text(base.raw_text),
        source=source,
        grounded=source != "optimizer",
        notes=_group_notes(entries),
    )


def _choose_base_entry(
    entries: Sequence[ComparableGroupedEntry], identity_predicate: Callable[[ComparableGroupedEntry], bool]
) -> ComparableGroupedEntry:
    ordered_sources = {"parser": 0, "phase2_input": 1, "optimizer": 2}
    sorted_entries = sorted(
        entries,
        key=lambda entry: (
            ordered_sources.get(entry.source, 9),
            0 if identity_predicate(entry) else 1,
            -len(normalize_description_text(entry.description or entry.raw_text)),
        ),
    )
    return sorted_entries[0]


def _pick_first(
    entries: Sequence[ComparableGroupedEntry],
    accessor: Callable[[ComparableGroupedEntry], str],
    normalizer: Callable[[str], str],
) -> str:
    for preferred_source in ("parser", "phase2_input", "optimizer"):
        for entry in entries:
            if entry.source != preferred_source:
                continue
            value = normalizer(accessor(entry))
            if value:
                return value
    return ""


def _richest_grounded_description(entries: Sequence[ComparableGroupedEntry]) -> str:
    grounded_entries = [entry for entry in entries if entry.source != "optimizer"]
    if grounded_entries:
        candidate_entries = list(entries)
    else:
        candidate_entries = list(entries)
    candidate_entries = sorted(
        candidate_entries,
        key=lambda entry: (
            1 if normalize_description_text(entry.description) else 0,
            len(normalize_description_text(entry.description or entry.raw_text)),
        ),
        reverse=True,
    )
    for entry in candidate_entries:
        description = normalize_description_text(entry.description) or normalize_description_text(entry.raw_text)
        if description:
            return description
    return ""


def _merged_source(entries: Sequence[ComparableGroupedEntry]) -> FieldSource:
    sources = {entry.source for entry in entries}
    if len(sources) > 1:
        return "merged"
    return list(sources)[0]


def _group_notes(entries: Sequence[ComparableGroupedEntry]) -> List[str]:
    notes: List[str] = []
    if any(entry.source == "phase2_input" for entry in entries) and any(entry.source == "parser" for entry in entries):
        notes.append("merged parser with phase2 candidate evidence")
    if any(entry.source == "optimizer" for entry in entries) and any(entry.source != "optimizer" for entry in entries):
        notes.append("accepted grounded optimizer augmentation")
    return notes
