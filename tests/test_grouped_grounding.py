"""Tests for grouped grounding behavior."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.grouped import (
    reconcile_experience,
    reconcile_projects,
    reconcile_education,
)


def test_grounded_optimizer_project_augmentation_is_accepted() -> None:
    phase2 = _phase2(
        project_candidates=[{"text": "Tellix | CV optimizer platform | 2024", "source_section": "Projects", "hints": {"dates": ["2024"]}}],
        full_text="Tellix CV optimizer platform 2024",
    )
    parser_payload = {"projects": [{"name": "Tellix", "description": "CV optimizer platform", "date_range": "2024"}]}
    optimizer_payload = {"projects": [{"name": "Tellix", "description": "CV optimizer platform with FastAPI backend", "date_range": "2024"}]}

    reconciled = reconcile_projects(phase2, parser_payload, optimizer_payload)

    assert reconciled.value[0].description.endswith("FastAPI backend")
    assert any("accepted grounded optimizer augmentation" in note for note in reconciled.value[0].notes)


def test_optimizer_only_fake_project_is_rejected() -> None:
    phase2 = _phase2(project_candidates=[], full_text="")

    reconciled = reconcile_projects(phase2, {}, {"projects": [{"name": "Secret Project", "description": "Top secret"}]})

    assert reconciled.value == []
    assert any("rejected optimizer-only projects entry" in note for note in reconciled.notes)


def test_parser_missed_but_candidate_grounded_experience_is_recoverable() -> None:
    phase2 = _phase2(
        experience_candidates=[{"text": "Backend Engineer | Acme | 2023 - 2024", "source_section": "Experience", "hints": {"dates": ["2023", "2024"]}}],
        full_text="Backend Engineer Acme 2023 2024",
    )

    reconciled = reconcile_experience(phase2, {}, {})

    assert len(reconciled.value) == 1
    assert reconciled.value[0].organization == "acme"


def test_over_specific_ungrounded_education_detail_is_not_accepted_blindly() -> None:
    phase2 = _phase2(
        education_candidates=[{"text": "BSc Computer Science | Ain Shams University | 2022 - 2026", "source_section": "Education", "hints": {"dates": ["2022", "2026"]}}],
        full_text="Ain Shams University 2022 2026",
    )
    optimizer_payload = {"education": [{"degree": "BSc Computer Science", "institution": "Ain Shams University, Faculty of Engineering, Department X", "date_range": "2022 - 2026"}]}

    reconciled = reconcile_education(phase2, {}, optimizer_payload)

    assert len(reconciled.value) == 1
    assert "department x" not in (reconciled.value[0].institution or "").lower()


def _phase2(**overrides) -> Phase2Input:
    payload = {
        "full_text": "",
        "canonical_sections": {},
        "uncategorized_text": "",
        "contact_candidates": {"name": [], "email": [], "phone": [], "location": [], "linkedin": [], "github": []},
        "skill_candidates": [],
        "language_candidates": [],
        "experience_candidates": [],
        "project_candidates": [],
        "education_candidates": [],
        "certification_candidates": [],
        "training_candidates": [],
        "diagnostics_flags": [],
        "source_metadata": {},
    }
    payload.update(overrides)
    return Phase2Input.model_validate(payload)
