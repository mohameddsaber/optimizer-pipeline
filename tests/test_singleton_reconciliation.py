"""Tests for coverage-mode singleton preservation and trivial recovery."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.finalize import reconcile_phase2_coverage_mode


def test_optimizer_base_is_preserved_for_simple_singletons() -> None:
    phase2 = _build_phase2_input()
    optimizer_payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone_number": "+201000000000",
        "location": "Cairo, Egypt",
    }

    validated = reconcile_phase2_coverage_mode(phase2, {}, optimizer_payload)

    assert validated.data["name"] == "Jane Doe"
    assert validated.data["email"] == "jane@example.com"
    assert validated.data["phone_number"] == "+201000000000"
    assert validated.data["location"] == "Cairo, Egypt"


def test_linkedin_and_github_are_trivially_recovered_when_missing() -> None:
    phase2 = _build_phase2_input(
        contact_candidates={
            "linkedin": ["linkedin.com/in/jane"],
            "github": ["github.com/jane"],
        }
    )

    validated = reconcile_phase2_coverage_mode(phase2, {}, {"name": "Jane Doe"})

    assert validated.data["linkedin"] == "linkedin.com/in/jane"
    assert validated.data["github"] == "github.com/jane"
    assert "linkedin" in validated.audit.recovered_fields
    assert "github" in validated.audit.recovered_fields


def test_trivial_social_recovery_ignores_header_noise() -> None:
    phase2 = _build_phase2_input(
        contact_candidates={
            "linkedin": ["Jane Doe | LinkedIn | GitHub", "linkedin.com/in/jane"],
            "github": ["Jane Doe | LinkedIn | GitHub", "github.com/jane"],
        }
    )

    validated = reconcile_phase2_coverage_mode(phase2, {}, {"name": "Jane Doe"})

    assert validated.data["linkedin"] == "linkedin.com/in/jane"
    assert validated.data["github"] == "github.com/jane"


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
    for key, value in overrides.items():
        if key == "contact_candidates":
            payload["contact_candidates"].update(value)
        else:
            payload[key] = value
    return Phase2Input.model_validate(payload)
