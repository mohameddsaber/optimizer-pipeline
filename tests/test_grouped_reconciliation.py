"""Tests for grouped reconciliation end-to-end behavior."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.finalize import reconcile_phase2_milestone2
from phase2.reconciliation.grouped import (
    reconcile_education,
    reconcile_experience,
    reconcile_projects,
    reconcile_trainings_courses,
)


def test_experience_reconciliation_merges_grounded_parser_optimizer_and_candidate() -> None:
    phase2 = _phase2(
        experience_candidates=[{"text": "Backend Engineer | Acme | 2023 - 2024", "source_section": "Experience", "hints": {"dates": ["2023", "2024"]}}],
        full_text="Backend Engineer Acme 2023 2024",
    )
    parser_payload = {"experience": [{"title": "Backend Engineer", "company": "Acme", "date_range": "2023 - 2024"}]}
    optimizer_payload = {"experience": [{"title": "Backend Engineer", "company": "Acme", "date_range": "2023 - 2024", "description": "Built APIs and pipelines"}]}

    reconciled = reconcile_experience(phase2, parser_payload, optimizer_payload)

    assert len(reconciled.value) == 1
    assert reconciled.value[0].source == "merged"
    assert reconciled.value[0].description == "Built APIs and pipelines"


def test_missing_project_is_recovered_from_phase2_candidate() -> None:
    phase2 = _phase2(
        project_candidates=[{"text": "Tellix | CV optimization platform | 2024", "source_section": "Projects", "hints": {"dates": ["2024"]}}],
        full_text="Tellix CV optimization platform 2024",
    )

    reconciled = reconcile_projects(phase2, {}, {})

    assert len(reconciled.value) == 1
    assert reconciled.value[0].name == "tellix"


def test_duplicate_education_entries_collapse_correctly() -> None:
    phase2 = _phase2(
        education_candidates=[{"text": "BSc Computer Science | Ain Shams University | 2022 - 2026", "source_section": "Education", "hints": {"dates": ["2022", "2026"]}}],
        full_text="Ain Shams University 2022 2026",
    )
    parser_payload = {"education": [{"degree": "BSc Computer Science", "institution": "Ain Shams University", "date_range": "2022 - 2026"}]}
    optimizer_payload = {"education": [{"degree": "Bachelor of Computer Science", "institution": "Ain Shams University", "date_range": "2022 - 2026"}]}

    reconciled = reconcile_education(phase2, parser_payload, optimizer_payload)

    assert len(reconciled.value) == 1
    assert reconciled.value[0].source == "merged"


def test_trainings_courses_reconciles_grounded_values_only() -> None:
    phase2 = _phase2(
        training_candidates=[{"text": "CCNA Training | NTI | 2024", "source_section": "Courses", "hints": {"dates": ["2024"]}}],
        full_text="CCNA Training NTI 2024",
    )
    optimizer_payload = {
        "trainings_courses": [
            {"name": "CCNA Training", "provider": "NTI", "date_range": "2024"},
            {"name": "Invisible Course", "provider": "Secret", "date_range": "2025"},
        ]
    }

    reconciled = reconcile_trainings_courses(phase2, {}, optimizer_payload)

    assert len(reconciled.value) == 1
    assert any("rejected optimizer-only trainings_courses entry" in note for note in reconciled.notes)


def test_milestone2_end_to_end_contains_grouped_fields_and_notes() -> None:
    phase2 = _phase2(
        full_text="Jane Doe\nCairo, Egypt\nPython | SQL\nAcme Backend Engineer 2023 2024\nTellix 2024",
        uncategorized_text="Jane Doe\nCairo, Egypt",
        contact_candidates={"name": ["Jane Doe"], "location": ["Cairo, Egypt"], "email": [], "phone": [], "linkedin": [], "github": []},
        skill_candidates=["Python", "SQL"],
        experience_candidates=[{"text": "Backend Engineer | Acme | 2023 - 2024", "source_section": "Experience", "hints": {"dates": ["2023", "2024"]}}],
        project_candidates=[{"text": "Tellix | CV optimization platform | 2024", "source_section": "Projects", "hints": {"dates": ["2024"]}}],
        education_candidates=[{"text": "BSc Computer Science | Ain Shams University | 2022 - 2026", "source_section": "Education", "hints": {"dates": ["2022", "2026"]}}],
        training_candidates=[{"text": "CCNA Training | NTI | 2024", "source_section": "Courses", "hints": {"dates": ["2024"]}}],
    )
    parser_payload = {
        "name": "Jane Doe",
        "location": "Cairo, Egypt",
        "technical_skills": ["Python"],
        "experience": [{"title": "Backend Engineer", "company": "Acme", "date_range": "2023 - 2024"}],
    }
    optimizer_payload = {
        "technical_skills": ["SQL", "Cobol"],
        "projects": [{"name": "Tellix", "description": "CV optimization platform", "date_range": "2024"}],
        "education": [{"degree": "BSc Computer Science", "institution": "Ain Shams University", "date_range": "2022 - 2026"}],
        "trainings_courses": [{"name": "Fake Course", "provider": "Secret", "date_range": "2025"}],
    }

    validated = reconcile_phase2_milestone2(phase2, parser_payload, optimizer_payload)

    assert validated.technical_skills.value == ["Python", "SQL"]
    assert len(validated.experience.value) == 1
    assert len(validated.projects.value) == 1
    assert len(validated.education.value) == 1
    assert len(validated.trainings_courses.value) == 1
    assert any("rejected optimizer-only trainings_courses entry" in note for note in validated.trainings_courses.notes)


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
