"""Unit tests for the phase-1 CV extraction pipeline."""

from pathlib import Path
from typing import List

import extractor.service as service_module
from extractor.classification import classify_blocks
from extractor.models import NormalizedBlock, RawPageExtraction, RawPdfExtraction, RawTextBlock
from extractor.normalize import normalize_blocks, normalize_text
from extractor.section_splitter import (
    normalize_section_heading,
    split_into_sections,
    split_into_sections_with_diagnostics,
)
from extractor.service import audit_extraction_quality, build_diagnostics, extract_raw_pdf, is_extraction_weak


def test_normalize_blocks_merges_multiline_bullet() -> None:
    raw_blocks = [
        RawTextBlock(
            block_id="raw-1-0",
            text="• Built ingestion pipeline",
            page_number=1,
            bbox=(72.0, 100.0, 260.0, 114.0),
        ),
        RawTextBlock(
            block_id="raw-1-1",
            text="for CV processing across teams",
            page_number=1,
            bbox=(90.0, 116.0, 290.0, 130.0),
        ),
    ]

    normalized = normalize_blocks(raw_blocks)

    assert len(normalized) == 1
    assert normalized[0].text == "• Built ingestion pipeline for CV processing across teams"
    assert normalized[0].source_block_ids == ["raw-1-0", "raw-1-1"]


def test_normalize_blocks_merges_deeply_indented_bullet_continuation() -> None:
    raw_blocks = [
        RawTextBlock(
            block_id="raw-1-0",
            text="• Technical Problem Solving: Strong debugging and troubleshooting capabilities in",
            page_number=1,
            bbox=(72.0, 100.0, 410.0, 114.0),
        ),
        RawTextBlock(
            block_id="raw-1-1",
            text="complex Flutter environments.",
            page_number=1,
            bbox=(118.0, 116.0, 320.0, 130.0),
        ),
        RawTextBlock(
            block_id="raw-1-2",
            text="• Collaborative Development: Worked well across teams.",
            page_number=1,
            bbox=(72.0, 142.0, 340.0, 156.0),
        ),
    ]

    normalized = normalize_blocks(raw_blocks)

    assert len(normalized) == 2
    assert normalized[0].text == (
        "• Technical Problem Solving: Strong debugging and troubleshooting capabilities in "
        "complex Flutter environments."
    )
    assert normalized[1].text == "• Collaborative Development: Worked well across teams."


def test_normalize_blocks_merges_certification_bullet_with_parenthetical_tail() -> None:
    raw_blocks = [
        RawTextBlock(
            block_id="raw-1-0",
            text="• AWS Certified Solutions Architect",
            page_number=1,
            bbox=(72.0, 100.0, 270.0, 114.0),
        ),
        RawTextBlock(
            block_id="raw-1-1",
            text="(Associate) - SAA-C03",
            page_number=1,
            bbox=(102.0, 116.0, 250.0, 130.0),
        ),
    ]

    normalized = normalize_blocks(raw_blocks)

    assert len(normalized) == 1
    assert normalized[0].text == "• AWS Certified Solutions Architect (Associate) - SAA-C03"


def test_normalize_blocks_merges_volunteering_bullet_with_uppercase_tail() -> None:
    raw_blocks = [
        RawTextBlock(
            block_id="raw-1-0",
            text="• Helped lead a tour of the Russian Pavilion and managed",
            page_number=1,
            bbox=(72.0, 100.0, 360.0, 114.0),
        ),
        RawTextBlock(
            block_id="raw-1-1",
            text="Exhibition demonstrations for visitors.",
            page_number=1,
            bbox=(108.0, 116.0, 330.0, 130.0),
        ),
    ]

    normalized = normalize_blocks(raw_blocks)

    assert len(normalized) == 1
    assert normalized[0].text == (
        "• Helped lead a tour of the Russian Pavilion and managed "
        "Exhibition demonstrations for visitors."
    )


def test_normalize_blocks_merges_course_bullet_with_wrapped_provider_line() -> None:
    raw_blocks = [
        RawTextBlock(
            block_id="raw-1-0",
            text="• Explore Emerging Tech",
            page_number=1,
            bbox=(72.0, 100.0, 220.0, 114.0),
        ),
        RawTextBlock(
            block_id="raw-1-1",
            text="IBM SkillsBuild",
            page_number=1,
            bbox=(110.0, 116.0, 210.0, 130.0),
        ),
    ]

    normalized = normalize_blocks(raw_blocks)

    assert len(normalized) == 1
    assert normalized[0].text == "• Explore Emerging Tech IBM SkillsBuild"


def test_normalize_blocks_merges_continuation_lines_by_alignment() -> None:
    raw_blocks = [
        RawTextBlock(
            block_id="raw-1-0",
            text="Built backend APIs and event-driven workflows",
            page_number=1,
            bbox=(72.0, 100.0, 330.0, 114.0),
        ),
        RawTextBlock(
            block_id="raw-1-1",
            text="for internal automation and reporting",
            page_number=1,
            bbox=(74.0, 116.0, 310.0, 130.0),
        ),
    ]

    normalized = normalize_blocks(raw_blocks)

    assert len(normalized) == 1
    assert "for internal automation and reporting" in normalized[0].text


def test_normalize_blocks_does_not_merge_following_section_heading() -> None:
    raw_blocks = [
        RawTextBlock(
            block_id="raw-1-0",
            text="High School, St. George's Collage School (SGC) Heliopolis | 2022",
            page_number=1,
            bbox=(72.0, 100.0, 340.0, 114.0),
        ),
        RawTextBlock(
            block_id="raw-1-1",
            text="Work Experience",
            page_number=1,
            bbox=(72.0, 118.0, 190.0, 132.0),
        ),
    ]

    normalized = normalize_blocks(raw_blocks)

    assert len(normalized) == 2
    assert normalized[0].text == "High School, St. George's Collage School (SGC) Heliopolis | 2022"
    assert normalized[1].text == "Work Experience"


def test_classify_blocks_detects_heading_contact_and_skills() -> None:
    normalized_blocks = [
        NormalizedBlock(
            block_id="norm-1-0",
            page_number=1,
            bbox=(72.0, 40.0, 410.0, 56.0),
            text="ahmed@example.com | +20 100 000 0000 | linkedin.com/in/ahmed",
            original_text="ahmed@example.com | +20 100 000 0000 | linkedin.com/in/ahmed",
            source_block_ids=["raw-1-0"],
            source_texts=["ahmed@example.com | +20 100 000 0000 | linkedin.com/in/ahmed"],
        ),
        NormalizedBlock(
            block_id="norm-1-1",
            page_number=1,
            bbox=(72.0, 90.0, 160.0, 106.0),
            text="EXPERIENCE",
            original_text="EXPERIENCE",
            source_block_ids=["raw-1-1"],
            source_texts=["EXPERIENCE"],
        ),
        NormalizedBlock(
            block_id="norm-1-2",
            page_number=1,
            bbox=(72.0, 180.0, 380.0, 194.0),
            text="Python | SQL | Docker | FastAPI",
            original_text="Python | SQL | Docker | FastAPI",
            source_block_ids=["raw-1-2"],
            source_texts=["Python | SQL | Docker | FastAPI"],
        ),
    ]

    labels = [block.label for block in classify_blocks(normalized_blocks)]
    assert labels == ["contact_line", "section_heading", "skills_line"]


def test_split_into_sections_does_not_collapse_resume_into_one_section() -> None:
    normalized_blocks = [
        _normalized("norm-1-0", 1, "SUMMARY", (72.0, 60.0, 160.0, 76.0)),
        _normalized("norm-1-1", 1, "Backend engineer focused on resilient systems.", (72.0, 80.0, 350.0, 94.0)),
        _normalized("norm-1-2", 1, "EXPERIENCE", (72.0, 120.0, 180.0, 136.0)),
        _normalized("norm-1-3", 1, "• Built APIs for high-volume workflows", (72.0, 140.0, 350.0, 154.0)),
        _normalized("norm-1-4", 1, "EDUCATION", (72.0, 200.0, 180.0, 216.0)),
        _normalized("norm-1-5", 1, "Cairo University", (72.0, 220.0, 210.0, 234.0)),
    ]

    sections = split_into_sections(classify_blocks(normalized_blocks))

    assert [section.heading for section in sections] == ["Summary", "Experience", "Education"]
    assert sections[1].content == "• Built APIs for high-volume workflows"


def test_normalize_section_heading_maps_aliases_to_canonical_names() -> None:
    assert normalize_section_heading("professional summary") == "Summary"
    assert normalize_section_heading("career history") == "Experience"
    assert normalize_section_heading("core competencies") == "Skills"
    assert normalize_section_heading("education and training") == "Education"
    assert normalize_section_heading("education & certifications") == "Education"
    assert normalize_section_heading("technical experience & training") == "Experience"
    assert normalize_section_heading("notable impact & achievements") == "Achievements"
    assert normalize_section_heading("volunteer work") == "Additional Information"
    assert normalize_section_heading("random heading") is None


def test_split_into_sections_handles_variant_headings() -> None:
    normalized_blocks = [
        _normalized("norm-1-0", 1, "PROFESSIONAL SUMMARY", (72.0, 60.0, 220.0, 76.0)),
        _normalized("norm-1-1", 1, "Backend engineer with platform experience.", (72.0, 80.0, 350.0, 94.0)),
        _normalized("norm-1-2", 1, "CAREER HISTORY", (72.0, 120.0, 210.0, 136.0)),
        _normalized("norm-1-3", 1, "Built APIs and internal tooling.", (72.0, 140.0, 320.0, 154.0)),
        _normalized("norm-1-4", 1, "CORE COMPETENCIES", (72.0, 170.0, 220.0, 186.0)),
        _normalized("norm-1-5", 1, "Python | SQL | Docker", (72.0, 190.0, 260.0, 204.0)),
    ]

    sections = split_into_sections(classify_blocks(normalized_blocks))

    assert [section.heading for section in sections] == ["Summary", "Experience", "Skills"]


def test_split_into_sections_promotes_leading_embedded_heading() -> None:
    semantic_blocks = [
        _semantic(
            "norm-1-0",
            1,
            "SUMMARY\nBackend engineer with strong API and platform experience.",
            "paragraph",
            (72.0, 80.0, 360.0, 120.0),
        ),
        _semantic(
            "norm-1-1",
            1,
            "TECHNICAL SKILLS",
            "section_heading",
            (72.0, 140.0, 200.0, 156.0),
        ),
        _semantic(
            "norm-1-2",
            1,
            "Python | SQL | FastAPI",
            "skills_line",
            (72.0, 160.0, 230.0, 176.0),
        ),
    ]

    sections = split_into_sections(semantic_blocks)

    assert [section.heading for section in sections] == ["Summary", "Skills"]
    assert sections[0].content == "Backend engineer with strong API and platform experience."


def test_split_into_sections_promotes_trailing_embedded_heading() -> None:
    semantic_blocks = [
        _semantic(
            "norm-1-0",
            1,
            "Python | SQL | Docker | FastAPI PROJECTS",
            "paragraph",
            (72.0, 100.0, 360.0, 116.0),
        ),
        _semantic(
            "norm-1-1",
            1,
            "Tellix platform for CV optimization.",
            "paragraph",
            (72.0, 130.0, 320.0, 146.0),
        ),
    ]

    sections = split_into_sections(semantic_blocks)

    assert [section.heading for section in sections] == ["General", "Projects"]
    assert sections[0].content == "Python | SQL | Docker | FastAPI"
    assert sections[1].content == "Tellix platform for CV optimization."


def test_split_into_sections_promotes_inline_delimited_heading_at_start() -> None:
    semantic_blocks = [
        _semantic(
            "norm-1-0",
            1,
            "Education and Qualifications | Computer Science | 2022-2026 | Ain Shams University",
            "paragraph",
            (72.0, 100.0, 360.0, 116.0),
        ),
        _semantic(
            "norm-1-1",
            1,
            "Projects",
            "section_heading",
            (72.0, 140.0, 150.0, 156.0),
        ),
        _semantic(
            "norm-1-2",
            1,
            "Tellix platform for CV optimization.",
            "paragraph",
            (72.0, 160.0, 300.0, 176.0),
        ),
    ]

    sections = split_into_sections(semantic_blocks)

    assert [section.heading for section in sections] == ["Education", "Projects"]
    assert sections[0].content == "Computer Science | 2022-2026 | Ain Shams University"


def test_split_into_sections_promotes_inline_delimited_heading_in_middle() -> None:
    semantic_blocks = [
        _semantic(
            "norm-1-0",
            1,
            "High School | 2022 | Work Experience",
            "paragraph",
            (72.0, 100.0, 320.0, 116.0),
        ),
        _semantic(
            "norm-1-1",
            1,
            "Founder & Web Developer | Built portfolio sites for clients.",
            "paragraph",
            (72.0, 120.0, 360.0, 136.0),
        ),
    ]

    sections = split_into_sections(semantic_blocks)

    assert [section.heading for section in sections] == ["General", "Experience"]
    assert sections[0].content == "High School | 2022"
    assert sections[1].content.startswith("Founder & Web Developer")


def test_split_into_sections_promotes_inline_delimited_courses_heading() -> None:
    semantic_blocks = [
        _semantic(
            "norm-1-0",
            1,
            "Assistant Accountant | 2024",
            "paragraph",
            (72.0, 100.0, 260.0, 116.0),
        ),
        _semantic(
            "norm-1-1",
            1,
            "Certifications & Courses | Explore Emerging Tech, IBM SkillsBuild",
            "paragraph",
            (72.0, 130.0, 360.0, 146.0),
        ),
    ]

    sections = split_into_sections(semantic_blocks)

    assert [section.heading for section in sections] == ["General", "Courses"]
    assert sections[1].content == "Explore Emerging Tech, IBM SkillsBuild"


def test_split_into_sections_promotes_same_line_leading_heading() -> None:
    semantic_blocks = [
        _semantic(
            "norm-1-0",
            1,
            "EXPERIENCE Digital Egypt Pioneers Initiative (DEPI)",
            "paragraph",
            (72.0, 100.0, 360.0, 116.0),
        ),
        _semantic(
            "norm-1-1",
            1,
            "DevOps Track Trainee",
            "paragraph",
            (72.0, 120.0, 220.0, 136.0),
        ),
    ]

    sections = split_into_sections(semantic_blocks)

    assert [section.heading for section in sections] == ["Experience"]
    assert sections[0].content.startswith("Digital Egypt Pioneers Initiative")


def test_split_into_sections_strips_trailing_section_bleed() -> None:
    semantic_blocks = [
        _semantic(
            "norm-1-0",
            1,
            "High-Speed Execution: Strong attention to detail. EDUCATION &",
            "paragraph",
            (72.0, 100.0, 360.0, 116.0),
        ),
    ]

    sections = split_into_sections(semantic_blocks)

    assert sections[0].content == "High-Speed Execution: Strong attention to detail."


def test_recovery_splits_oversized_general_section_without_text_loss() -> None:
    semantic_blocks = [
        _semantic("norm-1-0", 1, "Jane Doe", "heading", (72.0, 40.0, 160.0, 54.0)),
        _semantic("norm-1-1", 1, "Senior Backend Engineer", "heading", (72.0, 58.0, 220.0, 72.0)),
        _semantic("norm-1-2", 1, "Professional Summary", "other", (72.0, 100.0, 220.0, 116.0)),
        _semantic("norm-1-3", 1, "Built resilient systems for hiring workflows.", "paragraph", (72.0, 120.0, 360.0, 136.0)),
        _semantic("norm-1-4", 1, "Career History", "other", (72.0, 160.0, 200.0, 176.0)),
        _semantic("norm-1-5", 1, "Led backend delivery for internal tools.", "paragraph", (72.0, 180.0, 330.0, 196.0)),
    ]

    sections, section_diag = split_into_sections_with_diagnostics(semantic_blocks)
    original_text = normalize_text(
        "\n".join(
            block.text
            for block in semantic_blocks
            if block.label != "section_heading" and normalize_section_heading(block.text) is None
        )
    )
    split_text = normalize_text("\n".join(section.content for section in sections if section.content))

    assert "oversized_general_section" not in section_diag["possible_errors"]
    assert [section.heading for section in sections] == ["General", "Summary", "Experience"]
    assert split_text == original_text


def test_document_collapsed_into_general_is_flagged() -> None:
    semantic_blocks = [
        _semantic("norm-1-0", 1, "Jane Doe", "heading", (72.0, 40.0, 160.0, 54.0)),
        _semantic("norm-1-1", 1, "Backend engineer with Python and cloud experience.", "paragraph", (72.0, 70.0, 360.0, 86.0)),
        _semantic("norm-1-2", 1, "Built APIs and automation across teams.", "paragraph", (72.0, 96.0, 320.0, 112.0)),
    ]

    sections, section_diag = split_into_sections_with_diagnostics(semantic_blocks)

    assert len(sections) == 1
    assert sections[0].heading == "General"
    assert "document_collapsed_into_general" in section_diag["possible_errors"]


def test_build_diagnostics_reports_merged_and_suspicious_blocks() -> None:
    normalized_blocks = [
        NormalizedBlock(
            block_id="norm-1-0",
            page_number=1,
            bbox=(72.0, 100.0, 330.0, 130.0),
            text="• Built pipeline for CV ingestion",
            original_text="• Built pipeline\nfor CV ingestion",
            source_block_ids=["raw-1-0", "raw-1-1"],
            source_texts=["• Built pipeline", "for CV ingestion"],
        ),
        NormalizedBlock(
            block_id="norm-1-1",
            page_number=1,
            bbox=(72.0, 150.0, 90.0, 160.0),
            text="| |",
            original_text="| |",
            source_block_ids=["raw-1-2"],
            source_texts=["| |"],
        ),
    ]
    semantic_blocks = classify_blocks(normalized_blocks)
    sections, section_diag = split_into_sections_with_diagnostics(semantic_blocks)

    diagnostics = build_diagnostics([], normalized_blocks, semantic_blocks, sections, {}, section_diag)

    assert diagnostics.merged_block_count == 1
    assert diagnostics.section_count >= 1
    assert any(item.reason == "layout_noise_fragment" for item in diagnostics.suspicious_blocks)


def test_is_extraction_weak_flags_sparse_results() -> None:
    weak_pages = [
        RawPageExtraction(page_number=1, text="", blocks=[], raw_blocks=[]),
        RawPageExtraction(page_number=2, text="Short", blocks=[], raw_blocks=[]),
    ]

    assert is_extraction_weak(weak_pages) is True


def test_extract_raw_pdf_uses_fallback_when_primary_is_weak(monkeypatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    weak_primary = RawPdfExtraction(
        full_text="",
        pages=[RawPageExtraction(page_number=1, text="", blocks=[], raw_blocks=[])],
        sections=[],
        metadata={"extractor": "pymupdf"},
        raw_blocks=[],
    )
    strong_fallback_blocks = [
        RawTextBlock(
            block_id="raw-1-0",
            text="EXPERIENCE",
            page_number=1,
            bbox=(72.0, 80.0, 170.0, 96.0),
        ),
        RawTextBlock(
            block_id="raw-1-1",
            text="Built reliable data pipelines for document processing.",
            page_number=1,
            bbox=(72.0, 100.0, 380.0, 116.0),
        ),
    ]
    strong_fallback = RawPdfExtraction(
        full_text="EXPERIENCE\nBuilt reliable data pipelines for document processing.",
        pages=[
            RawPageExtraction(
                page_number=1,
                text="EXPERIENCE\nBuilt reliable data pipelines for document processing.",
                blocks=strong_fallback_blocks,
                raw_blocks=strong_fallback_blocks,
            )
        ],
        sections=[],
        metadata={"extractor": "pdfplumber"},
        raw_blocks=strong_fallback_blocks,
    )

    monkeypatch.setattr(service_module, "extract_with_pymupdf", lambda _: weak_primary)
    monkeypatch.setattr(service_module, "extract_with_pdfplumber", lambda _: strong_fallback)
    monkeypatch.setattr(service_module, "merge_extractions", lambda primary, fallback: fallback)

    extraction = extract_raw_pdf(str(pdf_path))

    assert extraction.metadata["fallback_triggered"] is True
    assert extraction.full_text.startswith("EXPERIENCE")
    assert extraction.sections[0].heading == "Experience"


def test_audit_extraction_quality_flags_collapsed_sections() -> None:
    blocks = [
        _normalized("norm-1-0", 1, "Very long resume text without any recognized section boundaries " * 20, (72.0, 100.0, 400.0, 180.0))
    ]
    semantic_blocks = classify_blocks(blocks)
    extraction = RawPdfExtraction(
        full_text=normalize_text("\n".join(block.text for block in blocks)),
        pages=[],
        sections=split_into_sections(semantic_blocks),
        metadata={},
        raw_blocks=[],
        normalized_blocks=blocks,
        semantic_blocks=semantic_blocks,
        diagnostics=build_diagnostics(
            [],
            blocks,
            semantic_blocks,
            split_into_sections(semantic_blocks),
            {},
            split_into_sections_with_diagnostics(semantic_blocks)[1],
        ),
    )

    audit = audit_extraction_quality(extraction)

    assert audit["weak"] is True
    assert any(reason["code"] == "collapsed_sections" for reason in audit["reasons"])


def _normalized(block_id: str, page_number: int, text: str, bbox: tuple) -> NormalizedBlock:
    return NormalizedBlock(
        block_id=block_id,
        page_number=page_number,
        bbox=bbox,
        text=text,
        original_text=text,
        source_block_ids=[block_id.replace("norm", "raw")],
        source_texts=[text],
    )


def _semantic(block_id: str, page_number: int, text: str, label: str, bbox: tuple):
    block = _normalized(block_id, page_number, text, bbox)
    return classify_blocks([block])[0].model_copy(update={"label": label})
