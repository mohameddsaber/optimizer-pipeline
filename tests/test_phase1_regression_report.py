"""Tests for Phase 1 regression metrics reporting."""

from extractor.models import (
    ExtractionDiagnostics,
    RawPdfExtraction,
    RawSection,
)
from extractor.reporting.regression_report import (
    build_phase1_regression_report,
    detect_section_bleed,
    detect_suspicious_composite_headings,
)


def test_detect_section_bleed_finds_trailing_heading_tail() -> None:
    row = _phase1(
        sections=[
            RawSection(
                heading="Achievements",
                content="High-Speed Execution: Strong attention to detail. EDUCATION &",
                source_pages=[1],
                block_ids=["b1"],
            )
        ]
    )

    markers = detect_section_bleed(row)

    assert markers == ["Achievements: High-Speed Execution: Strong attention to detail. EDUCATION &"]


def test_regression_report_tracks_composite_headings_and_candidate_counts() -> None:
    row = _phase1(
        sections=[
            RawSection(
                heading="Education & Certifications",
                content="B.Sc. | Cairo University",
                source_pages=[1],
                block_ids=["s1"],
            ),
            RawSection(
                heading="Education",
                content="B.Sc. | Cairo University",
                source_pages=[1],
                block_ids=["s1b"],
            ),
            RawSection(
                heading="Achievements",
                content="Publication (AC 2025): Smart Tourism Meets AI.\n\nHelped lead a tour of the Russian Pavilion.",
                source_pages=[1],
                block_ids=["s2"],
            ),
            RawSection(
                heading="Skills",
                content=(
                    "Python | SQL\n\n"
                    "CORE COMPETENCIES\n"
                    "• Collaborative Development: Experienced in working within technical teams."
                ),
                source_pages=[1],
                block_ids=["s3"],
            ),
        ],
        diagnostics=ExtractionDiagnostics(possible_errors=["oversized_general_section"]),
        metadata={"file_path": "CVs/test.pdf", "cv_id": "1"},
    )

    report = build_phase1_regression_report([row])

    assert report["files_with_oversized_general"][0]["file_path"] == "CVs/test.pdf"
    assert report["files_with_suspicious_composite_headings"][0]["headings"] == ["Education & Certifications"]
    candidate_counts = report["candidate_counts_per_cv"][0]["candidate_counts"]
    assert candidate_counts["education"] == 1
    assert candidate_counts["publications"] == 1
    assert candidate_counts["activities"] == 1
    assert candidate_counts["soft_skills"] == 1


def _phase1(**overrides) -> RawPdfExtraction:
    payload = {
        "full_text": "",
        "pages": [],
        "sections": [],
        "metadata": {},
        "raw_blocks": [],
        "normalized_blocks": [],
        "semantic_blocks": [],
        "diagnostics": ExtractionDiagnostics(),
    }
    payload.update(overrides)
    return RawPdfExtraction.model_validate(payload)
