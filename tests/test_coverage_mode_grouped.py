"""Additional coverage-mode grouped tests."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.finalize import reconcile_phase2_coverage_mode


def test_missing_project_is_appended_without_collapsing_distinct_entries() -> None:
    phase2 = _phase2(
        project_candidates=[
            {"text": "Tellix | CV platform | 2024", "source_section": "Projects", "hints": {"dates": ["2024"]}},
            {"text": "Portfolio Builder | React app | 2025", "source_section": "Projects", "hints": {"dates": ["2025"]}},
        ]
    )
    optimizer_payload = {"projects": [{"project_name": "Tellix", "description": "CV platform", "tools": [], "duration": "2024", "link": ""}]}

    validated = reconcile_phase2_coverage_mode(phase2, {}, optimizer_payload)

    assert len(validated.data["projects"]) == 2
    assert validated.data["projects"][0]["project_name"] == "Tellix"
    assert validated.data["projects"][1]["project_name"] == "Portfolio Builder"


def test_missing_experience_is_recovered_as_second_entry() -> None:
    phase2 = _phase2(
        experience_candidates=[
            {"text": "Backend Engineer | Acme | 2023 - 2024", "source_section": "Experience", "hints": {"dates": ["2023", "2024"]}},
            {"text": "Software Intern | Beta | 2022", "source_section": "Experience", "hints": {"dates": ["2022"]}},
        ]
    )
    optimizer_payload = {"experience": [{"company_name": "Acme", "title": "Backend Engineer", "duration": "2023 - 2024", "description": ""}]}

    validated = reconcile_phase2_coverage_mode(phase2, {}, optimizer_payload)

    assert len(validated.data["experience"]) == 2
    assert validated.data["experience"][1]["company_name"] == "Beta"


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
