"""Tests for grouped coverage recovery behavior."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.grouped import (
    recover_education,
    recover_experience,
    recover_projects,
)


def test_optimizer_project_base_is_preserved_while_source_can_patch_missing_fields() -> None:
    phase2 = _phase2(
        project_candidates=[{"text": "Tellix | CV optimizer platform | 2024", "source_section": "Projects", "hints": {"dates": ["2024"]}}]
    )
    optimizer_payload = {"projects": [{"project_name": "Tellix", "description": "", "tools": [], "duration": "2024", "link": ""}]}

    values, audit = recover_projects(phase2, {}, optimizer_payload)

    assert values[0]["project_name"] == "Tellix"
    assert values[0]["description"] != ""
    assert "projects.description" in audit["recovered_fields"]


def test_optimizer_only_project_is_preserved_in_coverage_mode() -> None:
    phase2 = _phase2(project_candidates=[])

    values, audit = recover_projects(phase2, {}, {"projects": [{"project_name": "Secret Project", "description": "Top secret", "tools": [], "duration": "", "link": ""}]})

    assert len(values) == 1
    assert values[0]["project_name"] == "Secret Project"
    assert audit["recovered_items"] == []


def test_candidate_backed_experience_is_recoverable() -> None:
    phase2 = _phase2(
        experience_candidates=[{"text": "Backend Engineer | Acme | 2023 - 2024", "source_section": "Experience", "hints": {"dates": ["2023", "2024"]}}]
    )

    values, _ = recover_experience(phase2, {}, {})

    assert len(values) == 1
    assert values[0]["company_name"] == "Acme"


def test_existing_education_value_is_not_overwritten_when_present() -> None:
    phase2 = _phase2(
        education_candidates=[{"text": "BSc Computer Science | Ain Shams University | 2022 - 2026\nGPA: 3.4", "source_section": "Education", "hints": {"dates": ["2022", "2026"]}}]
    )
    optimizer_payload = {
        "education": [
            {
                "university_name": "Ain Shams University",
                "degree": "BSc Computer Science",
                "specialization": "",
                "graduation_date": "2022 - 2026",
                "graduation_status": "",
                "GPA": "3.2",
                "coursework": [],
            }
        ]
    }

    values, _ = recover_education(phase2, {}, optimizer_payload)

    assert values[0]["GPA"] == "3.2"


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
