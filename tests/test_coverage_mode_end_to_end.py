"""End-to-end tests for coverage-mode output contract."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.finalize import reconcile_phase2_coverage_mode


def test_coverage_mode_returns_optimizer_schema_data_and_separate_audit() -> None:
    phase2 = _phase2(
        contact_candidates={"linkedin": ["linkedin.com/in/jane"], "github": ["github.com/jane"]},
        skill_candidates=["Python", "Docker", "SQL"],
        language_candidates=["English", "Arabic"],
        certification_candidates=["AWS SAA", "CCNA"],
        experience_candidates=[
            {"text": "Backend Engineer | Acme | 2023 - 2024", "source_section": "Experience", "hints": {"dates": ["2023", "2024"]}},
            {"text": "Software Intern | Beta | 2022", "source_section": "Experience", "hints": {"dates": ["2022"]}},
        ],
        project_candidates=[
            {"text": "Tellix | CV platform | 2024", "source_section": "Projects", "hints": {"dates": ["2024"]}},
            {"text": "Portfolio Builder | React app | 2025", "source_section": "Projects", "hints": {"dates": ["2025"]}},
        ],
        education_candidates=[
            {"text": "BSc Computer Science | Ain Shams University | 2022 - 2026\nGPA: 3.4\nGraduation Project Grade (A+)", "source_section": "Education", "hints": {"dates": ["2022", "2026"]}}
        ],
        training_candidates=[{"text": "Udemy Web Developer Bootcamp", "source_section": "Courses", "hints": {}}],
    )
    optimizer_payload = {
        "name": "Jane Doe",
        "linkedin": "",
        "github": "",
        "technical_skills": ["Python", "SQL"],
        "languages": ["English"],
        "certifications": ["AWS SAA"],
        "experience": [{"company_name": "Acme", "title": "Backend Engineer", "duration": "2023 - 2024", "description": ""}],
        "projects": [{"project_name": "Tellix", "description": "CV platform", "tools": [], "duration": "2024", "link": ""}],
        "education": [{"university_name": "Ain Shams University", "degree": "BSc Computer Science", "specialization": "", "graduation_date": "2022 - 2026", "graduation_status": "", "GPA": "", "coursework": []}],
        "trainings_courses": [],
    }

    validated = reconcile_phase2_coverage_mode(phase2, {}, optimizer_payload)

    assert validated.mode == "coverage"
    assert isinstance(validated.data, dict)
    assert isinstance(validated.audit.recovered_items, list)
    assert validated.data["technical_skills"] == ["Python", "SQL", "Docker"]
    assert validated.data["languages"] == ["English", "Arabic"]
    assert validated.data["certifications"] == ["AWS SAA", "CCNA"]
    assert validated.data["linkedin"] == "linkedin.com/in/jane"
    assert validated.data["github"] == "github.com/jane"
    assert len(validated.data["experience"]) == 2
    assert len(validated.data["projects"]) == 2
    assert validated.data["education"][0]["GPA"] == "3.4"
    assert validated.data["education"][0]["graduation_project_grade"] == "A+"
    assert len(validated.data["trainings_courses"]) == 1


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
    for key, value in overrides.items():
        if key == "contact_candidates":
            payload["contact_candidates"].update(value)
        else:
            payload[key] = value
    return Phase2Input.model_validate(payload)
