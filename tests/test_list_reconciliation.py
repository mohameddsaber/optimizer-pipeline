"""Tests for list reconciliation."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.lists import (
    reconcile_certifications,
    reconcile_languages,
    reconcile_technical_skills,
)


def test_parser_and_phase2_skills_merge_correctly() -> None:
    phase2 = _build_phase2_input(skill_candidates=["Python", "SQL"])

    reconciled = reconcile_technical_skills(
        phase2, {"technical_skills": ["Docker"]}, {"technical_skills": []}
    )

    assert reconciled.value == ["Python", "SQL", "Docker"]
    assert reconciled.source == "merged"


def test_duplicate_skills_collapse_after_normalization() -> None:
    phase2 = _build_phase2_input(skill_candidates=["Node.js", "React"])

    reconciled = reconcile_technical_skills(
        phase2,
        {"technical_skills": ["React", "Node.js"]},
        {"technical_skills": ["react"]},
    )

    assert reconciled.value == ["Node.js", "React"]


def test_unsupported_optimizer_only_skill_is_not_silently_accepted() -> None:
    phase2 = _build_phase2_input(skill_candidates=["Python"])

    reconciled = reconcile_technical_skills(
        phase2, {"technical_skills": []}, {"technical_skills": ["Cobol"]}
    )

    assert reconciled.value == ["Python"]
    assert any("Cobol" in note for note in reconciled.notes)


def test_languages_merge_cleanly() -> None:
    phase2 = _build_phase2_input(language_candidates=["English"])

    reconciled = reconcile_languages(
        phase2, {"languages": ["Arabic"]}, {"languages": ["English"]}
    )

    assert reconciled.value == ["English", "Arabic"]


def test_certifications_merge_grounded_values_only() -> None:
    phase2 = _build_phase2_input(
        full_text="AWS Solutions Architect Associate",
        certification_candidates=["AWS Solutions Architect Associate"],
    )

    reconciled = reconcile_certifications(
        phase2,
        {"certifications": ["CCNA"]},
        {"certifications": ["AWS Solutions Architect Associate", "Kubernetes Guru"]},
    )

    assert reconciled.value == ["AWS Solutions Architect Associate", "CCNA"]
    assert any("Kubernetes Guru" in note for note in reconciled.notes)


def _build_phase2_input(**overrides) -> Phase2Input:
    payload = {
        "full_text": "",
        "canonical_sections": {},
        "uncategorized_text": "",
        "contact_candidates": {
            "name": [],
            "email": [],
            "phone": [],
            "location": [],
            "linkedin": [],
            "github": [],
        },
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
