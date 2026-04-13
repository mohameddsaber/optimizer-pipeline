"""Tests for the Phase 1 -> Phase 2 adapter boundary."""

from contracts.phase1_output import Phase1Output
from contracts.phase2_input import Phase2Input
from extractor.models import (
    ExtractionDiagnostics,
    RawPageExtraction,
    RawSection,
    SemanticBlock,
)
from phase2.adapters.phase1_to_phase2 import build_phase2_input, canonicalize_section_name


def test_canonicalize_section_name_maps_known_aliases() -> None:
    assert canonicalize_section_name("professional summary") == "Summary"
    assert canonicalize_section_name("core competencies") == "Skills"
    assert canonicalize_section_name("career history") == "Experience"
    assert canonicalize_section_name("general") is None


def test_adapter_merges_repeated_skills_sections() -> None:
    phase1 = _build_phase1_output(
        sections=[
            RawSection(heading="Skills", content="Python | SQL", source_pages=[1], block_ids=["b1"]),
            RawSection(heading="Technical Skills", content="Docker | FastAPI", source_pages=[1], block_ids=["b2"]),
        ],
        semantic_blocks=[
            _semantic("b1", "skills_line", "Python | SQL"),
            _semantic("b2", "skills_line", "Docker | FastAPI"),
        ],
    )

    phase2 = build_phase2_input(phase1)

    assert phase2.canonical_sections["Skills"] == "Python | SQL\n\nDocker | FastAPI"
    assert phase2.skill_candidates[:4] == ["Python", "SQL", "Docker", "FastAPI"]


def test_adapter_preserves_uncategorized_general_text_separately() -> None:
    phase1 = _build_phase1_output(
        sections=[
            RawSection(heading="General", content="Jane Doe\nBackend Engineer", source_pages=[1], block_ids=["g1"]),
            RawSection(heading="Projects", content="Built internal tooling.", source_pages=[1], block_ids=["p1"]),
        ],
        semantic_blocks=[
            _semantic("g1", "heading", "Jane Doe"),
            _semantic("p1", "paragraph", "Built internal tooling."),
        ],
    )

    phase2 = build_phase2_input(phase1)

    assert phase2.uncategorized_text == "Jane Doe\nBackend Engineer"
    assert phase2.canonical_sections["Projects"] == "Built internal tooling."


def test_adapter_extracts_contact_candidates() -> None:
    phase1 = _build_phase1_output(
        full_text="Jane Doe\njane@example.com\n+20 100 000 0000\nlinkedin.com/in/jane\ngithub.com/jane",
        sections=[RawSection(heading="General", content="Jane Doe", source_pages=[1], block_ids=["h1"])],
        semantic_blocks=[
            _semantic("h1", "contact_line", "Jane Doe | jane@example.com | +20 100 000 0000 | linkedin.com/in/jane | github.com/jane"),
        ],
        metadata={"source_path": "CVs/Jane Doe.pdf", "page_count": 1, "extractor": "pymupdf"},
    )

    phase2 = build_phase2_input(phase1)

    assert "jane@example.com" in phase2.contact_candidates["email"]
    assert "+20 100 000 0000" in phase2.contact_candidates["phone"]
    assert any("linkedin.com" in item for item in phase2.contact_candidates["linkedin"])
    assert any("github.com" in item for item in phase2.contact_candidates["github"])


def test_adapter_extracts_languages_and_skills_from_delimited_lines() -> None:
    phase1 = _build_phase1_output(
        sections=[
            RawSection(heading="Skills", content="Python | SQL | Docker", source_pages=[1], block_ids=["s1"]),
            RawSection(heading="Languages", content="English | Arabic", source_pages=[1], block_ids=["l1"]),
        ],
        semantic_blocks=[
            _semantic("s1", "skills_line", "Python | SQL | Docker"),
            _semantic("l1", "paragraph", "English | Arabic"),
        ],
    )

    phase2 = build_phase2_input(phase1)

    assert phase2.skill_candidates[:3] == ["Python", "SQL", "Docker"]
    assert phase2.language_candidates == ["English", "Arabic"]


def test_adapter_maps_diagnostics_flags_without_geometry_leakage() -> None:
    phase1 = _build_phase1_output(
        sections=[RawSection(heading="General", content="Uncategorized content", source_pages=[1], block_ids=["g1"])],
        semantic_blocks=[_semantic("g1", "paragraph", "Summary hidden in general")],
        diagnostics=ExtractionDiagnostics(
            merged_block_count=3,
            section_count=1,
            general_block_ratio=0.8,
            possible_errors=["document_collapsed_into_general", "oversized_general_section"],
            recovered_section_splits=1,
            fallback_used=True,
        ),
    )

    phase2 = build_phase2_input(phase1)

    assert "fallback_used" in phase2.diagnostics_flags
    assert "document_collapsed_into_general" in phase2.diagnostics_flags
    assert "oversized_general_section" in phase2.diagnostics_flags
    assert "high_general_block_ratio" in phase2.diagnostics_flags
    assert "suspicious_section_split" in phase2.diagnostics_flags
    payload = phase2.model_dump()
    serialized = str(payload)
    assert "bbox" not in serialized
    assert "block_id" not in serialized


def test_adapter_stability_with_phase1_internal_fields() -> None:
    phase1 = Phase1Output.model_validate(
        {
            "full_text": "SUMMARY\nBackend engineer",
            "pages": [{"page_number": 1, "text": "SUMMARY\nBackend engineer", "blocks": [], "raw_blocks": [], "normalized_blocks": [], "semantic_blocks": []}],
            "sections": [{"heading": "Summary", "content": "Backend engineer", "source_pages": [1], "block_ids": []}],
            "metadata": {"source_path": "CVs/sample.pdf", "page_count": 1, "extractor": "pymupdf"},
            "raw_blocks": [],
            "normalized_blocks": [],
            "semantic_blocks": [],
            "diagnostics": {"section_count": 1},
        }
    )

    phase2 = build_phase2_input(phase1)

    assert isinstance(phase2, Phase2Input)
    assert phase2.source_metadata["file_name"] == "sample.pdf"


def test_adapter_regression_duplicate_skills_and_general_section() -> None:
    phase1 = _build_phase1_output(
        sections=[
            RawSection(heading="General", content="Jane Doe\nBackend Engineer", source_pages=[1], block_ids=["g1"]),
            RawSection(heading="Skills", content="Python | SQL", source_pages=[1], block_ids=["s1"]),
            RawSection(heading="Technical Skills", content="Docker | FastAPI", source_pages=[1], block_ids=["s2"]),
        ],
        semantic_blocks=[
            _semantic("g1", "heading", "Jane Doe"),
            _semantic("s1", "skills_line", "Python | SQL"),
            _semantic("s2", "skills_line", "Docker | FastAPI"),
        ],
        diagnostics=ExtractionDiagnostics(
            general_block_ratio=0.4,
            possible_errors=["oversized_general_section"],
            section_count=3,
        ),
    )

    phase2 = build_phase2_input(phase1)

    assert list(phase2.canonical_sections.keys()) == ["Skills"]
    assert phase2.uncategorized_text == "Jane Doe\nBackend Engineer"
    assert "oversized_general_section" in phase2.diagnostics_flags
    assert "high_general_block_ratio" in phase2.diagnostics_flags


def _build_phase1_output(
    full_text: str = "",
    sections=None,
    semantic_blocks=None,
    diagnostics=None,
    metadata=None,
) -> Phase1Output:
    sections = sections or []
    semantic_blocks = semantic_blocks or []
    diagnostics = diagnostics or ExtractionDiagnostics(section_count=len(sections))
    metadata = metadata or {"source_path": "CVs/example.pdf", "page_count": 1, "extractor": "pymupdf"}
    return Phase1Output(
        full_text=full_text or "\n".join(section.content for section in sections),
        pages=[RawPageExtraction(page_number=1, text=full_text or "", blocks=[], raw_blocks=[], normalized_blocks=[], semantic_blocks=semantic_blocks)],
        sections=sections,
        metadata=metadata,
        raw_blocks=[],
        normalized_blocks=[],
        semantic_blocks=semantic_blocks,
        diagnostics=diagnostics,
    )


def _semantic(block_id: str, label: str, text: str) -> SemanticBlock:
    return SemanticBlock(
        block_id=block_id,
        page_number=1,
        bbox=(1.0, 2.0, 3.0, 4.0),
        text=text,
        original_text=text,
        source_block_ids=[block_id],
        label=label,
        hints=[],
    )
