"""Tests for grouped entry matching."""

from phase2.reconciliation.grouped_match import (
    ComparableGroupedEntry,
    match_education_entries,
    match_experience_entries,
    match_project_entries,
    match_training_entries,
)


def test_same_experience_entry_with_title_variation_matches() -> None:
    left = ComparableGroupedEntry(
        kind="experience",
        source="parser",
        raw_text="Senior Backend Engineer at Acme 2022-2024",
        primary_name="Senior Backend Engineer",
        secondary_name="Acme",
        date_range="2022 - 2024",
    )
    right = ComparableGroupedEntry(
        kind="experience",
        source="optimizer",
        raw_text="Backend Engineer Acme 2022-2024",
        primary_name="Backend Engineer",
        secondary_name="Acme",
        date_range="2022 - 2024",
    )

    result = match_experience_entries(left, right)

    assert result.matched is True
    assert result.score >= 5.0


def test_same_project_with_richer_optimizer_description_matches() -> None:
    left = ComparableGroupedEntry(
        kind="projects",
        source="phase2_input",
        raw_text="Tellix platform for CV optimization",
        primary_name="Tellix",
        date_range="2024",
        technologies=["Python", "FastAPI"],
    )
    right = ComparableGroupedEntry(
        kind="projects",
        source="optimizer",
        raw_text="Tellix CV Optimization Platform with FastAPI backend",
        primary_name="Tellix",
        date_range="2024",
        technologies=["FastAPI", "Docker"],
    )

    result = match_project_entries(left, right)

    assert result.matched is True
    assert "name_exact" in result.reasons


def test_education_entries_with_same_institution_and_date_match() -> None:
    left = ComparableGroupedEntry(
        kind="education",
        source="parser",
        raw_text="BSc Ain Shams University 2022-2026",
        primary_name="BSc Computer Science",
        secondary_name="Ain Shams University",
        date_range="2022 - 2026",
    )
    right = ComparableGroupedEntry(
        kind="education",
        source="phase2_input",
        raw_text="Bachelor of Computer Science | Ain Shams University | 2022-2026",
        primary_name="Bachelor of Computer Science",
        secondary_name="Ain Shams University",
        date_range="2022 - 2026",
    )

    result = match_education_entries(left, right)

    assert result.matched is True


def test_unrelated_entries_do_not_match() -> None:
    left = ComparableGroupedEntry(
        kind="trainings_courses",
        source="parser",
        raw_text="CCNA Training NTI 2024",
        primary_name="CCNA Training",
        secondary_name="NTI",
        date_range="2024",
    )
    right = ComparableGroupedEntry(
        kind="trainings_courses",
        source="optimizer",
        raw_text="AWS Cloud Practitioner Udemy 2025",
        primary_name="AWS Cloud Practitioner",
        secondary_name="Udemy",
        date_range="2025",
    )

    result = match_training_entries(left, right)

    assert result.matched is False
