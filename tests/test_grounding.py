"""Tests for grounding helpers."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.grounding import find_grounding_sources, is_value_grounded


def test_grounded_skill_from_phase2_input_is_accepted() -> None:
    phase2 = _build_phase2_input(skill_candidates=["Python", "SQL"])

    assert is_value_grounded("Python", phase2, {}, "skill") is True


def test_optimizer_only_unsupported_skill_is_not_grounded() -> None:
    phase2 = _build_phase2_input(skill_candidates=["Python", "SQL"])

    assert is_value_grounded("Cobol", phase2, {}, "skill") is False


def test_grounded_email_phone_and_url_detection() -> None:
    phase2 = _build_phase2_input(
        full_text="Reach me at jane@example.com or +20 100 000 0000 linkedin.com/in/jane github.com/jane",
        contact_candidates={
            "email": ["jane@example.com"],
            "phone": ["+20 100 000 0000"],
            "linkedin": ["linkedin.com/in/jane"],
            "github": ["github.com/jane"],
        },
    )

    assert is_value_grounded("jane@example.com", phase2, {}, "email")
    assert is_value_grounded("+20 100 000 0000", phase2, {}, "phone")
    assert is_value_grounded("linkedin.com/in/jane", phase2, {}, "url")
    assert "phase2_input" in find_grounding_sources("github.com/jane", phase2, {}, "url")


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
