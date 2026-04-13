"""Final Phase 2 Milestone 1 assembly."""

from typing import Any, Dict

from contracts.phase2_input import Phase2Input
from phase2.contracts.validated_cv import ValidatedCv
from phase2.reconciliation.lists import (
    reconcile_certifications,
    reconcile_languages,
    reconcile_technical_skills,
)
from phase2.reconciliation.singletons import (
    reconcile_email,
    reconcile_github,
    reconcile_linkedin,
    reconcile_location,
    reconcile_name,
    reconcile_phone_number,
)


def reconcile_phase2_milestone1(
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    optimizer_payload: Dict[str, Any],
) -> ValidatedCv:
    """Reconcile simple singleton and list fields into a validated CV."""

    return ValidatedCv(
        name=reconcile_name(phase2_input, parser_payload, optimizer_payload),
        email=reconcile_email(phase2_input, parser_payload, optimizer_payload),
        phone_number=reconcile_phone_number(phase2_input, parser_payload, optimizer_payload),
        location=reconcile_location(phase2_input, parser_payload, optimizer_payload),
        linkedin=reconcile_linkedin(phase2_input, parser_payload, optimizer_payload),
        github=reconcile_github(phase2_input, parser_payload, optimizer_payload),
        technical_skills=reconcile_technical_skills(phase2_input, parser_payload, optimizer_payload),
        languages=reconcile_languages(phase2_input, parser_payload, optimizer_payload),
        certifications=reconcile_certifications(phase2_input, parser_payload, optimizer_payload),
    )
