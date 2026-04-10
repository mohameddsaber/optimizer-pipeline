"""Unit tests for raw CV extraction heuristics."""

from extraction.models import RawPageExtraction, RawTextBlock
from extraction.normalize import normalize_text
from extraction.section_splitter import (
    classify_heading_from_text,
    is_heading_text,
    split_into_sections,
)
from extraction.models import RawPdfExtraction
from extraction.service import audit_extraction_quality, is_extraction_weak


def test_normalize_text_collapses_whitespace_and_preserves_bullets() -> None:
    text = "SUMMARY\r\n\r\n  -   Built   APIs \r\n\t•  Led migration\n\n\nPython    Developer"
    normalized = normalize_text(text)

    assert normalized == "SUMMARY\n\n- Built APIs\n• Led migration\n\nPython Developer"


def test_is_heading_text_matches_known_variants_case_insensitively() -> None:
    assert is_heading_text("WORK EXPERIENCE")
    assert is_heading_text("technical skills:")
    assert is_heading_text(" Summary ")
    assert not is_heading_text("Senior Software Engineer")


def test_classify_heading_from_text_detects_common_block_types() -> None:
    assert classify_heading_from_text("EDUCATION") == "heading"
    assert classify_heading_from_text("- Improved latency by 35%") == "bullet"
    assert classify_heading_from_text("Python | SQL | Docker") == "table"
    assert classify_heading_from_text("Built backend services for large-scale payments platform.") == "paragraph"


def test_split_into_sections_uses_heading_lines_and_tracks_pages() -> None:
    pages = [
        RawPageExtraction(
            page_number=1,
            text="SUMMARY\nBackend engineer with 8 years of experience.\n\nEXPERIENCE\nAcme Corp\n- Built APIs",
            blocks=[
                RawTextBlock(text="SUMMARY", page_number=1, bbox=None, kind="heading"),
                RawTextBlock(
                    text="Backend engineer with 8 years of experience.",
                    page_number=1,
                    bbox=None,
                    kind="paragraph",
                ),
                RawTextBlock(text="EXPERIENCE", page_number=1, bbox=None, kind="heading"),
                RawTextBlock(text="Acme Corp", page_number=1, bbox=None, kind="other"),
                RawTextBlock(text="- Built APIs", page_number=1, bbox=None, kind="bullet"),
            ],
        ),
        RawPageExtraction(
            page_number=2,
            text="EDUCATION:\nCairo University",
            blocks=[
                RawTextBlock(text="EDUCATION:", page_number=2, bbox=None, kind="heading"),
                RawTextBlock(text="Cairo University", page_number=2, bbox=None, kind="paragraph"),
            ],
        ),
    ]

    sections = split_into_sections(pages)

    assert [section.heading for section in sections] == ["Summary", "Experience", "Education"]
    assert sections[0].content == "Backend engineer with 8 years of experience."
    assert sections[1].content == "Acme Corp\n- Built APIs"
    assert sections[1].source_pages == [1]
    assert sections[2].source_pages == [2]


def test_split_into_sections_keeps_general_content_before_first_heading() -> None:
    pages = [
        RawPageExtraction(
            page_number=1,
            text="Jane Doe\nSenior Engineer\n\nSKILLS\nPython\nSQL",
            blocks=[],
        )
    ]

    sections = split_into_sections(pages)

    assert sections[0].heading == "General"
    assert sections[0].content == "Jane Doe\nSenior Engineer"
    assert sections[1].heading == "Skills"


def test_is_extraction_weak_flags_sparse_results() -> None:
    weak_pages = [
        RawPageExtraction(page_number=1, text="", blocks=[]),
        RawPageExtraction(page_number=2, text="Short", blocks=[]),
    ]

    assert is_extraction_weak(weak_pages) is True


def test_is_extraction_weak_accepts_reasonable_results() -> None:
    strong_pages = [
        RawPageExtraction(
            page_number=1,
            text="Experienced software engineer with strong Python and data engineering background.",
            blocks=[
                RawTextBlock(
                    text="Experienced software engineer with strong Python and data engineering background.",
                    page_number=1,
                    bbox=None,
                    kind="paragraph",
                ),
                RawTextBlock(text="SKILLS", page_number=1, bbox=None, kind="heading"),
            ],
        ),
        RawPageExtraction(
            page_number=2,
            text="Professional Experience\nAcme Corp\nBuilt resilient pipelines and backend systems.",
            blocks=[
                RawTextBlock(text="Professional Experience", page_number=2, bbox=None, kind="heading"),
                RawTextBlock(
                    text="Built resilient pipelines and backend systems.",
                    page_number=2,
                    bbox=None,
                    kind="paragraph",
                ),
            ],
        ),
    ]

    assert is_extraction_weak(strong_pages) is False


def test_audit_extraction_quality_flags_fragmented_low_quality_output() -> None:
    pages = [
        RawPageExtraction(
            page_number=1,
            text="|\n|\nA\nB\nC\n|\n|\nX",
            blocks=[],
        ),
        RawPageExtraction(
            page_number=2,
            text="A\nB\nC\n|\n|\nA\nB\nC",
            blocks=[],
        ),
    ]
    extraction = RawPdfExtraction(full_text="\n".join(page.text for page in pages), pages=pages, sections=[], metadata={})

    audit = audit_extraction_quality(extraction)

    assert audit["weak"] is True
    assert audit["score"] < 70
    codes = {reason["code"] for reason in audit["reasons"]}
    assert "low_text" in codes or "very_low_text" in codes
    assert "very_few_blocks" in codes


def test_audit_extraction_quality_accepts_reasonable_resume_like_output() -> None:
    pages = [
        RawPageExtraction(
            page_number=1,
            text=(
                "SUMMARY\nExperienced software engineer with Python and backend expertise.\n"
                "EXPERIENCE\nAcme Corp\nBuilt resilient APIs for high-scale systems.\n"
                "SKILLS\nPython\nSQL\nDocker"
            ),
            blocks=[
                RawTextBlock(text="SUMMARY", page_number=1, bbox=None, kind="heading"),
                RawTextBlock(
                    text="Experienced software engineer with Python and backend expertise.",
                    page_number=1,
                    bbox=None,
                    kind="paragraph",
                ),
                RawTextBlock(text="EXPERIENCE", page_number=1, bbox=None, kind="heading"),
                RawTextBlock(
                    text="Built resilient APIs for high-scale systems.",
                    page_number=1,
                    bbox=None,
                    kind="paragraph",
                ),
                RawTextBlock(text="SKILLS", page_number=1, bbox=None, kind="heading"),
            ],
        )
    ]
    extraction = RawPdfExtraction(
        full_text=pages[0].text,
        pages=pages,
        sections=split_into_sections(pages),
        metadata={},
    )

    audit = audit_extraction_quality(extraction)

    assert audit["weak"] is False
    assert audit["score"] >= 70
