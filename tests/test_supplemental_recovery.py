"""Tests for awards/achievements/activities/publications recovery in coverage mode."""

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.finalize import reconcile_phase2_coverage_mode
from phase2.reconciliation.supplemental import recover_supplemental_content


def test_supplemental_recovery_classifies_chunks_into_target_fields() -> None:
    phase2 = _phase2(
        canonical_sections={
            "Achievements": (
                "Publication (AC 2025): Smart Tourism Meets AI: A Multimodal Assistant.\n\n"
                "ECPC 2025 Finalist Ranked 98th nationally among competitive programming teams.\n\n"
                "Founded and led a volunteer team that collected academic materials.\n\n"
                "Helped lead a tour of the Russian Pavilion and managed exhibition demonstrations."
            )
        }
    )

    recovered, audit = recover_supplemental_content(phase2, {}, {})

    assert recovered["publications"] == [
        "Smart Tourism Meets AI: A Multimodal Assistant."
    ]
    assert recovered["awards"] == [
        "ECPC 2025 Finalist Ranked 98th nationally among competitive programming teams."
    ]
    assert recovered["achievements"] == [
        "Founded and led a volunteer team that collected academic materials."
    ]
    assert recovered["activities"] == [
        "Helped lead a tour of the Russian Pavilion and managed exhibition demonstrations."
    ]
    assert len(audit["recovered_items"]) == 4


def test_supplemental_recovery_preserves_optimizer_base_without_duplicates() -> None:
    phase2 = _phase2(
        canonical_sections={
            "Achievements": (
                "ECPC 2025 Finalist Ranked 98th nationally among competitive programming teams.\n\n"
                "Founded and led a volunteer team that collected academic materials."
            )
        }
    )
    optimizer_payload = {
        "awards": ["ECPC 2025 Finalist Ranked 98th nationally among competitive programming teams."],
        "achievements": [],
        "activities": [],
        "publications": [],
    }

    recovered, _ = recover_supplemental_content(phase2, {}, optimizer_payload)

    assert recovered["awards"] == [
        "ECPC 2025 Finalist Ranked 98th nationally among competitive programming teams."
    ]
    assert recovered["achievements"] == [
        "Founded and led a volunteer team that collected academic materials."
    ]


def test_coverage_mode_adds_supplemental_fields_to_validated_data() -> None:
    phase2 = _phase2(
        canonical_sections={
            "Achievements": (
                "Publication (AC 2025): Smart Tourism Meets AI: A Multimodal Assistant.\n\n"
                "Third place in IPM Math Egyptian competition for mental math.\n\n"
                "Founded and led a volunteer team that collected academic materials.\n\n"
                "Member in Org Team in Compiler Community."
            )
        }
    )

    validated = reconcile_phase2_coverage_mode(phase2, {}, {"name": "Jane Doe"})

    assert validated.data["publications"] == [
        "Smart Tourism Meets AI: A Multimodal Assistant."
    ]
    assert validated.data["awards"] == [
        "Third place in IPM Math Egyptian competition for mental math."
    ]
    assert validated.data["achievements"] == [
        "Founded and led a volunteer team that collected academic materials."
    ]
    assert validated.data["activities"] == [
        "Member in Org Team in Compiler Community."
    ]
    assert any("Recovered publication:" in note for note in validated.audit.notes)
    assert any("Recovered award:" in note for note in validated.audit.notes)
    assert any("Recovered achievement:" in note for note in validated.audit.notes)
    assert any("Recovered activitie:" in note or "Recovered activity:" in note for note in validated.audit.notes)


def test_supplemental_recovery_reads_publication_from_education_section() -> None:
    phase2 = _phase2(
        canonical_sections={
            "Education": (
                "German University in Cairo\n"
                "Bachelor Thesis (A+): AI-powered multimodal assistant for cultural interpretation and tourism.\n"
                "Publication (AC 2025): Smart Tourism Meets AI: A Multimodal Assistant for Exploratory Cultural Engagement."
            )
        }
    )

    recovered, _ = recover_supplemental_content(phase2, {}, {})

    assert recovered["publications"] == [
        "Smart Tourism Meets AI: A Multimodal Assistant for Exploratory Cultural Engagement."
    ]


def test_supplemental_recovery_reads_activities_from_volunteering_tail_in_skills() -> None:
    phase2 = _phase2(
        canonical_sections={
            "Skills": (
                "Python\n"
                "Languages: Arabic, English\n"
                "VOLUNTEERING\n"
                "MAY 2022, EVENT\n"
                "- Responsible for data entry and providing access to individuals on the technical committee.\n"
                "- Helped lead a tour of the Russian Pavilion and managed exhibition demonstrations."
            )
        }
    )

    recovered, _ = recover_supplemental_content(phase2, {}, {})

    assert recovered["activities"] == [
        "Responsible for data entry and providing access to individuals on the technical committee.",
        "Helped lead a tour of the Russian Pavilion and managed exhibition demonstrations.",
    ]


def test_achievements_section_defaults_to_achievements_when_no_stronger_signal_exists() -> None:
    phase2 = _phase2(
        canonical_sections={
            "Achievements": (
                "Pioneer Tech Influencer: First Egyptian creator to technically dissect social media algorithms.\n\n"
                "Multi-Language Developer: Mastered 7 programming languages, enabling versatile architecture across different platforms and OS.\n\n"
                "High-Speed Execution: Professional Ultra-Fast Typing Speed with an obsession for detail and data integrity."
            )
        }
    )

    recovered, _ = recover_supplemental_content(phase2, {}, {})

    assert recovered["achievements"] == [
        "Pioneer Tech Influencer: First Egyptian creator to technically dissect social media algorithms.",
        "Multi-Language Developer: Mastered 7 programming languages, enabling versatile architecture across different platforms and OS.",
        "High-Speed Execution: Professional Ultra-Fast Typing Speed with an obsession for detail and data integrity.",
    ]


def test_clean_chunk_strips_trailing_section_bleed() -> None:
    phase2 = _phase2(
        canonical_sections={
            "Achievements": "High-Speed Execution: Professional Ultra-Fast Typing Speed with an obsession for detail and data integrity. EDUCATION &"
        }
    )

    recovered, _ = recover_supplemental_content(phase2, {}, {})

    assert recovered["achievements"] == [
        "High-Speed Execution: Professional Ultra-Fast Typing Speed with an obsession for detail and data integrity."
    ]


def _phase2(**overrides) -> Phase2Input:
    payload = {
        "contract_version": "phase2-input-v1",
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
