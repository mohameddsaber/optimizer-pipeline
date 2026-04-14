"""Tests for coverage-mode list recovery."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.lists import (
    recover_certifications,
    recover_languages,
    recover_soft_skills,
    recover_technical_skills,
)


def test_skills_recovery_adds_missing_skill_without_duplicates() -> None:
    phase2 = _build_phase2_input(skill_candidates=["Python", "Docker", "SQL"])

    values, audit = recover_technical_skills(
        phase2,
        {"technical_skills": ["Python", "Docker", "SQL"]},
        {"technical_skills": ["Python", "SQL"]},
    )

    assert values == ["Python", "SQL", "Docker"]
    assert any("Recovered technical_skill: Docker" in note for note in audit["notes"])


def test_languages_preserve_optimizer_order_and_append_missing() -> None:
    phase2 = _build_phase2_input(language_candidates=["English", "Arabic"])

    values, _ = recover_languages(
        phase2,
        {"languages": ["English", "Arabic"]},
        {"languages": ["English"]},
    )

    assert values == ["English", "Arabic"]


def test_soft_skills_recover_core_competencies_lines_from_skills_section() -> None:
    phase2 = _build_phase2_input(
        canonical_sections={
            "Skills": (
                "Flutter\n"
                "CORE COMPETENCIES\n"
                "• Technical Problem Solving: Strong debugging and troubleshooting capabilities in complex Flutter environments.\n"
                "• Collaborative Development: Experienced in working within technical teams and maintaining clear project documentation.\n"
                "• Continuous Learning: Rapidly adapting to new frameworks and evolving industry best practices to deliver modern mobile solutions."
            )
        }
    )

    values, audit = recover_soft_skills(
        phase2,
        {"soft_skills": []},
        {"soft_skills": []},
    )

    assert values == [
        "Technical Problem Solving: Strong debugging and troubleshooting capabilities in complex Flutter environments.",
        "Collaborative Development: Experienced in working within technical teams and maintaining clear project documentation.",
        "Continuous Learning: Rapidly adapting to new frameworks and evolving industry best practices to deliver modern mobile solutions.",
    ]
    assert any("Recovered soft_skill:" in note for note in audit["notes"])


def test_certifications_recover_omitted_source_item() -> None:
    phase2 = _build_phase2_input(certification_candidates=["AWS SAA", "CCNA"])

    values, audit = recover_certifications(
        phase2,
        {"certifications": ["AWS SAA", "CCNA"]},
        {"certifications": ["AWS SAA"]},
    )

    assert values == ["AWS SAA", "CCNA"]
    assert any("Recovered certification: CCNA" in note for note in audit["notes"])


def test_technical_skills_ignore_section_wrapped_skill_fragments() -> None:
    phase2 = _build_phase2_input(
        skill_candidates=[
            "Programming Languages: JavaScript",
            "TypeScript, C#",
            "Frontend Development: React.js",
            "Docker",
        ]
    )

    values, audit = recover_technical_skills(
        phase2,
        {"technical_skills": ["Docker"]},
        {"technical_skills": ["JavaScript", "React.js"]},
    )

    assert values == ["JavaScript", "React.js", "Docker"]
    assert not any("Programming Languages: JavaScript" in note for note in audit["notes"])


def test_technical_skills_do_not_recover_soft_skills_or_section_labels() -> None:
    phase2 = _build_phase2_input(
        skill_candidates=["CORE COMPETENCIES", "Teamwork", "Problem Solving", "Docker"]
    )

    values, _ = recover_technical_skills(
        phase2,
        {"technical_skills": ["Docker"]},
        {"technical_skills": ["Python"]},
    )

    assert values == ["Python", "Docker"]


def test_technical_skills_dedupe_common_formatting_variants() -> None:
    phase2 = _build_phase2_input()

    values, _ = recover_technical_skills(
        phase2,
        {
            "technical_skills": [
                "React.js",
                "Fast Api",
                "SQLserver",
                "C# / .NET Core",
                "Visual Studio/ VS Code",
            ]
        },
        {
            "technical_skills": [
                "React",
                "FastAPI",
                "SQL Server",
                "C#/.NET Core",
                "Visual Studio / VS Code",
            ]
        },
    )

    assert values == [
        "React",
        "FastAPI",
        "SQL Server",
        "C#/.NET Core",
        "Visual Studio / VS Code",
    ]


def test_technical_skills_filter_fragmented_recovery_noise() -> None:
    phase2 = _build_phase2_input(
        skill_candidates=[
            "Technical Concepts",
            "Directory",
            "Linux (Ubuntu –",
            "RabbitMQ).",
            "with innovative solutions.",
            "Scala Backend Technologies — Spring Boot",
            "Docker",
            "Clean Architecture.",
            "REST APIs",
        ]
    )

    values, _ = recover_technical_skills(
        phase2,
        {"technical_skills": []},
        {"technical_skills": ["Docker", "REST APIs"]},
    )

    assert values == ["Docker", "REST APIs", "Clean Architecture"]


def test_technical_skills_filter_remaining_category_wrappers() -> None:
    phase2 = _build_phase2_input(
        skill_candidates=[
            "Backend: Spring Boot",
            "Web Development:",
            "Networking:",
            "Testing: Unit Testing (PHPUnit / JUnit)",
            "Problem Solving: Strong DSA understanding (advanced)",
            "Cumulative GPA: 1 (German Grading System)",
            "Data analysis tools: Excel, SQL, Power BI, Tableau",
            "JWT",
        ]
    )

    values, _ = recover_technical_skills(
        phase2,
        {"technical_skills": []},
        {"technical_skills": ["JWT"]},
    )

    assert values == ["JWT"]


def test_languages_ignore_section_labels_and_technology_noise() -> None:
    phase2 = _build_phase2_input(
        language_candidates=["LANGUAGES", "Languages", "Python", "English", "Arabic (Native)"]
    )

    values, _ = recover_languages(
        phase2,
        {"languages": ["English", "Arabic (Native)"]},
        {"languages": []},
    )

    assert values == ["English", "Arabic (Native)"]


def test_certifications_ignore_section_labels_dates_and_sentences() -> None:
    phase2 = _build_phase2_input(
        certification_candidates=[
            "CERTIFICATES",
            "june 2024 - jan 2025",
            "Worked on an AI-powered camera project focusing on intelligent monitoring.",
            "CCNA",
        ]
    )

    values, _ = recover_certifications(
        phase2,
        {"certifications": ["CCNA"]},
        {"certifications": []},
    )

    assert values == ["CCNA"]


def test_certifications_trim_mixed_sentences_and_reject_activity_noise() -> None:
    phase2 = _build_phase2_input(
        certification_candidates=[
            "AITB Python Certificate (20 training hours) Completed Introduction to Python training",
            "● Route Acadmey",
            "Route Acadmey june 2024-jan 2025",
            "Automated data processing tasks, improving efficiency and reducing manual errors in reporting.",
            "Excellence Awards for Academic Achievement: Ranked 4th at the GIU (Winter 2023)",
        ]
    )

    values, _ = recover_certifications(
        phase2,
        {"certifications": []},
        {"certifications": []},
    )

    assert values == [
        "AITB Python Certificate (20 training hours)",
        "Route Acadmey",
    ]


def test_certifications_reject_provider_location_and_section_fragments() -> None:
    phase2 = _build_phase2_input(
        certification_candidates=[
            "B.Sc. in Management Information Systems (MIS)",
            "Cairo",
            "Egypt",
            "NTI & ITI",
            "Certified Cybersecurity Fundamentals",
            "National Telecommunication Institute (NTI)",
            "AI for Digital Marketing",
            "Information Technology Institute (ITI)",
            "HR Management Certification",
            "Professional Course",
            "TECHNICAL SKILLS &",
            "CCNA",
        ]
    )

    values, _ = recover_certifications(
        phase2,
        {"certifications": []},
        {"certifications": []},
    )

    assert values == [
        "Certified Cybersecurity Fundamentals",
        "HR Management Certification",
        "CCNA",
    ]


def test_certifications_dedupe_date_suffixed_base_and_clean_recovered_value() -> None:
    phase2 = _build_phase2_input(certification_candidates=["Route Acadmey"])

    values, _ = recover_certifications(
        phase2,
        {"certifications": []},
        {"certifications": ["Route Acadmey june 2024-jan 2025"]},
    )

    assert values == ["Route Acadmey june 2024-jan 2025"]


def _build_phase2_input(**overrides) -> Phase2Input:
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
