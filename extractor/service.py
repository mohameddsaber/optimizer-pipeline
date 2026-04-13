"""Service orchestration for phase-1 CV PDF extraction."""

from pathlib import Path
import re
from typing import Any, Dict, List

from extractor.classification import classify_blocks
from extractor.models import (
    ExtractionDiagnostics,
    NormalizedBlock,
    RawPageExtraction,
    RawPdfExtraction,
    SuspiciousBlock,
)
from extractor.normalize import normalize_blocks, normalize_text
from extractor.pdf_extractors import extract_with_pdfplumber, extract_with_pymupdf, merge_extractions
from extractor.section_splitter import split_into_sections_with_diagnostics

_ALNUM_RE = re.compile(r"[A-Za-z0-9]")
_NOISE_RE = re.compile(r"[|_~`^<>[\]{}]")


def extract_raw_pdf(pdf_path: str) -> RawPdfExtraction:
    """Extract, normalize, classify, sectionize, and diagnose one PDF."""

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError("PDF file does not exist: {0}".format(pdf_path))
    if path.suffix.lower() != ".pdf":
        raise ValueError("Expected a PDF file, got: {0}".format(pdf_path))

    primary = extract_with_pymupdf(pdf_path)
    extraction = primary
    if is_extraction_weak(primary.pages):
        fallback = extract_with_pdfplumber(pdf_path)
        extraction = merge_extractions(primary, fallback)
        extraction.metadata["fallback_triggered"] = True
    else:
        extraction.metadata["fallback_triggered"] = False

    raw_blocks = extraction.raw_blocks
    normalized_blocks = normalize_blocks(raw_blocks)
    semantic_blocks = classify_blocks(normalized_blocks)
    sections, section_diagnostics = split_into_sections_with_diagnostics(semantic_blocks)
    diagnostics = build_diagnostics(
        raw_blocks, normalized_blocks, semantic_blocks, sections, extraction.metadata, section_diagnostics
    )
    pages = _build_pages(extraction.pages, normalized_blocks, semantic_blocks)
    full_text = normalize_text("\n\n".join(block.text for block in normalized_blocks if block.text))

    return RawPdfExtraction(
        full_text=full_text,
        pages=pages,
        sections=sections,
        metadata=extraction.metadata,
        raw_blocks=raw_blocks,
        normalized_blocks=normalized_blocks,
        semantic_blocks=semantic_blocks,
        diagnostics=diagnostics,
    )


def is_extraction_weak(pages: List[RawPageExtraction]) -> bool:
    """Flag obviously weak extractor output before deeper normalization."""

    if not pages:
        return True
    page_count = len(pages)
    empty_pages = sum(1 for page in pages if not page.text.strip())
    total_text_chars = sum(len(page.text.strip()) for page in pages)
    total_blocks = sum(len(page.raw_blocks or page.blocks) for page in pages)

    if total_text_chars < 80:
        return True
    if empty_pages / float(page_count) >= 0.5:
        return True
    if total_blocks <= max(1, page_count // 2):
        return True
    return False


def build_diagnostics(
    raw_blocks: List[Any],
    normalized_blocks: List[NormalizedBlock],
    semantic_blocks: List[Any],
    sections: List[Any],
    metadata: Dict[str, Any],
    section_diagnostics: Dict[str, Any],
) -> ExtractionDiagnostics:
    """Build deterministic diagnostics from real extraction outcomes."""

    suspicious_blocks: List[SuspiciousBlock] = []
    assigned_block_ids = {block_id for section in sections for block_id in section.block_ids}
    unassigned_blocks = [
        block.block_id
        for block in semantic_blocks
        if block.label != "section_heading" and block.block_id not in assigned_block_ids
    ]

    for block in semantic_blocks:
        reasons = _block_suspicion_reasons(block)
        for reason in reasons:
            suspicious_blocks.append(
                SuspiciousBlock(
                    block_id=block.block_id,
                    page_number=block.page_number,
                    reason=reason,
                    text=block.text,
                )
            )

    return ExtractionDiagnostics(
        merged_block_count=sum(1 for block in normalized_blocks if len(block.source_block_ids) > 1),
        unassigned_blocks=unassigned_blocks,
        suspicious_blocks=suspicious_blocks,
        section_count=int(section_diagnostics.get("section_count", len(sections))),
        general_block_ratio=float(section_diagnostics.get("general_block_ratio", 0.0)),
        possible_errors=list(section_diagnostics.get("possible_errors", [])),
        recovered_section_splits=int(section_diagnostics.get("recovered_section_splits", 0)),
        fallback_used=bool(metadata.get("fallback_triggered")),
    )


def audit_extraction_quality(extraction: RawPdfExtraction) -> Dict[str, Any]:
    """Return a higher-level quality audit over the phase-1 representation."""

    full_text = extraction.full_text
    text_length = len(full_text)
    section_count = len(extraction.sections)
    suspicious_count = len(extraction.diagnostics.suspicious_blocks)
    merged_block_count = extraction.diagnostics.merged_block_count
    alnum_ratio = (
        float(len(_ALNUM_RE.findall(full_text))) / float(text_length) if text_length else 0.0
    )
    noise_ratio = (
        float(len(_NOISE_RE.findall(full_text))) / float(max(1, len(full_text.replace(" ", ""))))
    )

    reasons: List[Dict[str, Any]] = []
    if text_length < 120:
        reasons.append({"code": "very_low_text", "severity": "critical", "metric": text_length})
    if section_count <= 1 and text_length >= 800:
        reasons.append({"code": "collapsed_sections", "severity": "high", "metric": section_count})
    for possible_error in extraction.diagnostics.possible_errors:
        if possible_error == "document_collapsed_into_general":
            reasons.append({"code": possible_error, "severity": "high", "metric": True})
        elif possible_error == "oversized_general_section":
            reasons.append({"code": possible_error, "severity": "medium", "metric": extraction.diagnostics.general_block_ratio})
        elif possible_error == "heading_candidates_found_inside_general":
            reasons.append({"code": possible_error, "severity": "medium", "metric": True})
    if suspicious_count >= max(5, len(extraction.semantic_blocks) // 3):
        reasons.append({"code": "many_suspicious_blocks", "severity": "medium", "metric": suspicious_count})
    if alnum_ratio < 0.45:
        reasons.append({"code": "low_alnum_ratio", "severity": "high", "metric": round(alnum_ratio, 3)})
    if noise_ratio > 0.08:
        reasons.append({"code": "high_noise_ratio", "severity": "medium", "metric": round(noise_ratio, 3)})
    if merged_block_count == 0 and len(extraction.raw_blocks) > len(extraction.pages) * 8:
        reasons.append({"code": "no_merges_detected", "severity": "low", "metric": merged_block_count})

    score = max(0, 100 - sum({"critical": 50, "high": 25, "medium": 12, "low": 5}[r["severity"]] for r in reasons))
    weak = any(reason["severity"] in {"critical", "high"} for reason in reasons) or score < 70
    return {
        "score": score,
        "weak": weak,
        "reasons": reasons,
        "metrics": {
            "text_length": text_length,
            "section_count": section_count,
            "general_block_ratio": extraction.diagnostics.general_block_ratio,
            "merged_block_count": merged_block_count,
            "suspicious_block_count": suspicious_count,
            "alnum_ratio": round(alnum_ratio, 3),
            "noise_ratio": round(noise_ratio, 3),
        },
    }


def _build_pages(
    original_pages: List[RawPageExtraction],
    normalized_blocks: List[NormalizedBlock],
    semantic_blocks: List[Any],
) -> List[RawPageExtraction]:
    pages: List[RawPageExtraction] = []
    for page in original_pages:
        page_normalized = [block for block in normalized_blocks if block.page_number == page.page_number]
        page_semantic = [block for block in semantic_blocks if block.page_number == page.page_number]
        page_text = normalize_text("\n".join(block.text for block in page_normalized))
        pages.append(
            RawPageExtraction(
                page_number=page.page_number,
                text=page_text,
                blocks=page.raw_blocks or page.blocks,
                raw_blocks=page.raw_blocks or page.blocks,
                normalized_blocks=page_normalized,
                semantic_blocks=page_semantic,
            )
        )
    return pages


def _block_suspicion_reasons(block: Any) -> List[str]:
    reasons: List[str] = []
    text = normalize_text(block.text)
    if not text:
        reasons.append("empty_text")
        return reasons
    if len(text) <= 2 and block.label not in {"date", "location"}:
        reasons.append("very_short_text")
    if len(text.split()) == 1 and not text.isalpha() and any(char.isdigit() for char in text):
        reasons.append("token_like_fragment")
    if _NOISE_RE.search(text) and len(text) <= 12:
        reasons.append("layout_noise_fragment")
    if text.count("|") >= 3 and block.label not in {"contact_line", "skills_line"}:
        reasons.append("delimiter_heavy_text")
    return reasons
