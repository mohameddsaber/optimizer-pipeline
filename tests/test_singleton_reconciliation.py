"""Tests for singleton reconciliation."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.finalize import reconcile_phase2_milestone1
from phase2.reconciliation.singletons import (
    reconcile_email,
    reconcile_linkedin,
    reconcile_location,
    reconcile_phone_number,
)


def test_parser_email_beats_missing_optimizer() -> None:
    phase2 = _build_phase2_input()

    reconciled = reconcile_email(phase2, {"email": "jane@example.com"}, {})

    assert reconciled.value == "jane@example.com"
    assert reconciled.source == "parser"


def test_phase2_phone_candidate_beats_malformed_parser_phone() -> None:
    phase2 = _build_phase2_input(contact_candidates={"phone": ["+20 100 000 0000"]})

    reconciled = reconcile_phone_number(phase2, {"phone_number": "abc"}, {})

    assert reconciled.value == "+20 100 000 0000"
    assert reconciled.source == "phase2_input"


def test_grounded_optimizer_linkedin_is_accepted_if_parser_missing() -> None:
    phase2 = _build_phase2_input(
        full_text="linkedin.com/in/jane-doe",
        contact_candidates={"linkedin": ["linkedin.com/in/jane-doe"]},
    )

    reconciled = reconcile_linkedin(phase2, {}, {"linkedin": "linkedin.com/in/jane-doe"})

    assert reconciled.value == "linkedin.com/in/jane-doe"
    assert reconciled.grounded is True


def test_over_specific_optimizer_location_is_rejected_if_not_grounded() -> None:
    phase2 = _build_phase2_input(contact_candidates={"location": ["Cairo, Egypt"]})

    reconciled = reconcile_location(phase2, {}, {"location": "Nasr City, Cairo, Egypt"})

    assert reconciled.value == "Cairo, Egypt"
    assert "rejected ungrounded or over-specific optimizer location" not in reconciled.notes


def test_milestone1_end_to_end_skills_and_location_notes() -> None:
    phase2 = _build_phase2_input(
        full_text="Jane Doe\nCairo, Egypt\nPython | SQL | Docker\nlinkedin.com/in/jane",
        canonical_sections={"Skills": "Python | SQL | Docker"},
        uncategorized_text="Jane Doe\nCairo, Egypt",
        contact_candidates={
            "name": ["Jane Doe"],
            "location": ["Cairo, Egypt"],
            "linkedin": ["linkedin.com/in/jane"],
            "email": [],
            "phone": [],
            "github": [],
        },
        skill_candidates=["Python", "SQL", "Docker"],
        diagnostics_flags=["fallback_used"],
    )
    parser_payload = {"name": "Jane Doe", "location": "Cairo, Egypt", "technical_skills": ["Python", "SQL"]}
    optimizer_payload = {"technical_skills": ["Docker", "Cobol"], "location": "Nasr City, Cairo, Egypt"}

    validated = reconcile_phase2_milestone1(phase2, parser_payload, optimizer_payload)

    assert validated.location.value == "Cairo, Egypt"
    assert validated.location.source in {"parser", "phase2_input"}
    assert validated.technical_skills.value == ["Python", "SQL", "Docker"]
    assert validated.technical_skills.source == "merged"
    assert any("rejected ungrounded optimizer value: Cobol" in note for note in validated.technical_skills.notes)


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
