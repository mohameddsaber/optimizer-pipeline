"""Tests for coverage-mode grouped recovery preserving optimizer schema."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.grouped import (
    recover_education,
    recover_experience,
    recover_projects,
    recover_trainings_courses,
)


def test_education_patch_fills_missing_gpa_and_project_grade_in_validated_output() -> None:
    phase2 = _phase2(
        education_candidates=[
            {
                "text": "BSc Computer Science | Ain Shams University | 2022 - 2026\nGPA: 3.4\nGraduation Project Grade (A+)",
                "source_section": "Education",
                "hints": {"dates": ["2022", "2026"]},
            }
        ]
    )
    optimizer_payload = {
        "education": [
            {
                "university_name": "Ain Shams University",
                "degree": "BSc Computer Science",
                "specialization": "",
                "graduation_date": "2022 - 2026",
                "graduation_status": "",
                "GPA": "",
                "coursework": [],
            }
        ]
    }

    values, audit = recover_education(phase2, {}, optimizer_payload)

    assert list(values[0].keys()) == list(optimizer_payload["education"][0].keys()) + ["graduation_project_grade"]
    assert values[0]["GPA"] == "3.4"
    assert values[0]["graduation_project_grade"] == "A+"
    assert "education.GPA" in audit["recovered_fields"]
    assert "education.graduation_project_grade" in audit["recovered_fields"]


def test_project_recovery_appends_missing_project_in_optimizer_schema() -> None:
    phase2 = _phase2(
        project_candidates=[
            {"text": "Tellix | CV platform | 2024", "source_section": "Projects", "hints": {"dates": ["2024"]}},
            {"text": "Portfolio Builder | React app | 2025", "source_section": "Projects", "hints": {"dates": ["2025"]}},
        ]
    )
    optimizer_payload = {
        "projects": [
            {"project_name": "Tellix", "description": "CV platform", "tools": [], "duration": "2024", "link": ""}
        ]
    }

    values, _ = recover_projects(phase2, {}, optimizer_payload)

    assert len(values) == 2
    assert set(values[1].keys()) == set(optimizer_payload["projects"][0].keys())


def test_experience_recovery_appends_missing_entry_and_keeps_existing() -> None:
    phase2 = _phase2(
        experience_candidates=[
            {"text": "Backend Engineer | Acme | 2023 - 2024", "source_section": "Experience", "hints": {"dates": ["2023", "2024"]}},
            {"text": "Software Intern | Beta | 2022", "source_section": "Experience", "hints": {"dates": ["2022"]}},
        ]
    )
    optimizer_payload = {
        "experience": [
            {"company_name": "Acme", "title": "Backend Engineer", "duration": "2023 - 2024", "description": ""}
        ]
    }

    values, _ = recover_experience(phase2, {}, optimizer_payload)

    assert len(values) == 2
    assert values[0]["company_name"] == "Acme"
    assert values[1]["company_name"] == "Beta"


def test_trainings_courses_keep_schema_when_recovering() -> None:
    phase2 = _phase2(
        training_candidates=[{"text": "Udemy Spring Boot Course", "source_section": "Courses", "hints": {}}]
    )
    optimizer_payload = {"trainings_courses": [{"institution": "Udemy", "title": "Udemy Web Developer Bootcamp", "description": ""}]}

    values, _ = recover_trainings_courses(phase2, {}, optimizer_payload)

    assert len(values) == 2
    assert set(values[1].keys()) == set(optimizer_payload["trainings_courses"][0].keys())


def test_trainings_courses_are_not_recovered_when_present_under_certifications() -> None:
    phase2 = _phase2(
        training_candidates=[{"text": "Udemy Spring Boot Course", "source_section": "Courses", "hints": {}}]
    )
    optimizer_payload = {
        "trainings_courses": [],
        "certifications": ["Udemy Spring Boot Course"],
    }

    values, _ = recover_trainings_courses(phase2, {}, optimizer_payload)

    assert values == []


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
