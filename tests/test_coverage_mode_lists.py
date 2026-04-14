"""Additional coverage-mode list tests."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.finalize import reconcile_phase2_coverage_mode


def test_skills_recovery_keeps_optimizer_values_and_appends_missing() -> None:
    phase2 = _phase2(skill_candidates=["Python", "Docker", "SQL"])
    optimizer_payload = {"technical_skills": ["Python", "SQL"]}

    validated = reconcile_phase2_coverage_mode(phase2, {}, optimizer_payload)

    assert validated.data["technical_skills"] == ["Python", "SQL", "Docker"]
    assert any("Recovered technical_skill: Docker" in note for note in validated.audit.notes)


def test_no_duplicate_when_source_matches_optimizer_with_same_format() -> None:
    phase2 = _phase2(language_candidates=["English", "Arabic"])
    optimizer_payload = {"languages": ["English", "Arabic"]}

    validated = reconcile_phase2_coverage_mode(phase2, {}, optimizer_payload)

    assert validated.data["languages"] == ["English", "Arabic"]


def test_coverage_mode_does_not_append_technical_section_labels() -> None:
    phase2 = _phase2(
        skill_candidates=[
            "Programming Languages: JavaScript",
            "TypeScript, C#",
            "Frontend Development: React.js",
            "AWS (SAA-C03 certified)",
        ]
    )
    optimizer_payload = {"technical_skills": ["JavaScript", "React.js", "AWS"]}

    validated = reconcile_phase2_coverage_mode(phase2, {}, optimizer_payload)

    assert validated.data["technical_skills"] == ["JavaScript", "React.js", "AWS"]
    assert not any("Programming Languages: JavaScript" in note for note in validated.audit.notes)


def test_coverage_mode_dedupes_technical_skill_variants_against_optimizer_base() -> None:
    phase2 = _phase2()
    optimizer_payload = {"technical_skills": ["Jest", "AWS"]}
    parser_payload = {"technical_skills": ["Jest (unit testing)", "AWS (SAA-C03 certified)"]}

    validated = reconcile_phase2_coverage_mode(phase2, parser_payload, optimizer_payload)

    assert validated.data["technical_skills"] == ["Jest", "AWS"]


def test_coverage_mode_dedupes_common_technical_skill_surface_variants() -> None:
    phase2 = _phase2()
    optimizer_payload = {"technical_skills": ["React", "FastAPI", "SQL Server", "C#/.NET Core"]}
    parser_payload = {"technical_skills": ["React.js", "Fast Api", "SQLserver", "C# / .NET Core"]}

    validated = reconcile_phase2_coverage_mode(phase2, parser_payload, optimizer_payload)

    assert validated.data["technical_skills"] == ["React", "FastAPI", "SQL Server", "C#/.NET Core"]


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
