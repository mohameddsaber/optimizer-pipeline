"""Service layer for deterministic raw PDF extraction."""

from pathlib import Path
import re
from typing import Any, Dict, List

from extraction.models import RawPageExtraction, RawPdfExtraction, RawSection, RawTextBlock
from extraction.normalize import normalize_text
from extraction.pdf_extractors import (
    extract_with_pdfplumber,
    extract_with_pymupdf,
    merge_extractions,
)
from extraction.section_splitter import split_into_sections

_ALNUM_RE = re.compile(r"[A-Za-z0-9]")
_WORD_RE = re.compile(r"\b\w+\b")
_NOISE_CHARS = set("|_~`^<>[]{}")


def extract_raw_pdf(pdf_path: str) -> RawPdfExtraction:
    """Extract raw PDF content with PyMuPDF and conservative pdfplumber fallback."""

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {pdf_path}")

    primary = extract_with_pymupdf(pdf_path)
    extraction = primary

    if is_extraction_weak(primary.pages):
        fallback = extract_with_pdfplumber(pdf_path)
        extraction = merge_extractions(primary, fallback)
        extraction.metadata["fallback_triggered"] = True
    else:
        extraction.metadata["fallback_triggered"] = False

    normalized_pages = [_normalize_page(page) for page in extraction.pages]
    full_text = normalize_text("\n\n".join(page.text for page in normalized_pages if page.text))
    sections = split_into_sections(normalized_pages)

    return RawPdfExtraction(
        full_text=full_text,
        pages=normalized_pages,
        sections=sections,
        metadata=extraction.metadata,
    )


def is_extraction_weak(pages: List[RawPageExtraction]) -> bool:
    """Flag suspiciously weak extraction results for fallback handling."""

    if not pages:
        return True

    page_count = len(pages)
    empty_pages = sum(1 for page in pages if not page.text.strip())
    total_text_chars = sum(len(page.text.strip()) for page in pages)
    total_blocks = sum(len(page.blocks) for page in pages)

    if total_text_chars < 80:
        return True
    if empty_pages / page_count >= 0.5:
        return True
    if total_blocks <= max(1, page_count // 2):
        return True
    return False


def audit_extraction_quality(extraction: RawPdfExtraction) -> Dict[str, Any]:
    """Return a stricter deterministic audit report for an extraction.

    The audit is intentionally heuristic and explainable. It produces
    machine-readable reason codes instead of attempting semantic judgment.
    """

    pages = extraction.pages
    full_text = extraction.full_text or ""
    page_count = len(pages)
    empty_pages = sum(1 for page in pages if not page.text.strip())
    total_blocks = sum(len(page.blocks) for page in pages)
    total_lines = 0
    very_short_lines = 0
    repeated_lines: Dict[str, int] = {}
    total_non_space_chars = 0
    noise_chars = 0

    for page in pages:
        for raw_line in page.text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            total_lines += 1
            total_non_space_chars += sum(1 for char in line if not char.isspace())
            noise_chars += sum(1 for char in line if char in _NOISE_CHARS)
            if len(_WORD_RE.findall(line)) <= 1 and len(line) <= 3:
                very_short_lines += 1
            repeated_lines[line] = repeated_lines.get(line, 0) + 1

    repeated_line_instances = sum(count for count in repeated_lines.values() if count >= 3)
    full_text_length = len(full_text)
    sections_count = len(extraction.sections)
    fallback_triggered = bool(extraction.metadata.get("fallback_triggered"))
    alnum_chars = len(_ALNUM_RE.findall(full_text))
    alnum_ratio = (alnum_chars / full_text_length) if full_text_length else 0.0
    avg_chars_per_page = (full_text_length / page_count) if page_count else 0.0
    avg_blocks_per_page = (total_blocks / page_count) if page_count else 0.0
    short_line_ratio = (very_short_lines / total_lines) if total_lines else 1.0
    repeated_line_ratio = (repeated_line_instances / total_lines) if total_lines else 0.0
    noise_ratio = (noise_chars / total_non_space_chars) if total_non_space_chars else 0.0

    reasons: List[Dict[str, Any]] = []

    def add_reason(code: str, severity: str, message: str, metric: Any) -> None:
        reasons.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "metric": metric,
            }
        )

    if page_count == 0:
        add_reason("no_pages", "critical", "No pages were extracted.", page_count)
    if full_text_length < 120:
        add_reason("very_low_text", "critical", "Extracted text volume is extremely low.", full_text_length)
    elif full_text_length < 300:
        add_reason("low_text", "medium", "Extracted text volume is lower than expected for a CV.", full_text_length)
    elif full_text_length < 800 and avg_chars_per_page < 250:
        add_reason(
            "thin_text_density",
            "low",
            "Text density is somewhat low for the number of pages.",
            round(avg_chars_per_page, 2),
        )

    if empty_pages / page_count >= 0.5 if page_count else True:
        add_reason("many_empty_pages", "critical", "At least half of the pages are empty.", empty_pages)
    elif empty_pages > 0:
        add_reason("some_empty_pages", "medium", "One or more pages are empty.", empty_pages)

    if avg_blocks_per_page < 1.0:
        add_reason("very_few_blocks", "high", "Very few text blocks were extracted per page.", round(avg_blocks_per_page, 2))
    elif avg_blocks_per_page < 2.0:
        add_reason("low_block_density", "medium", "Block density is lower than expected.", round(avg_blocks_per_page, 2))

    if alnum_ratio < 0.45:
        add_reason("low_alnum_ratio", "high", "Text appears noisy or poorly decoded.", round(alnum_ratio, 3))

    if short_line_ratio > 0.45 and total_lines >= 8:
        add_reason("fragmented_lines", "medium", "A large share of lines are very short.", round(short_line_ratio, 3))

    if repeated_line_ratio > 0.2 and repeated_line_instances >= 6:
        add_reason("repeated_lines", "medium", "Many lines repeat three or more times.", round(repeated_line_ratio, 3))

    if noise_ratio > 0.08:
        add_reason("high_noise_ratio", "medium", "The text contains an unusual amount of layout noise characters.", round(noise_ratio, 3))

    if sections_count == 0 and full_text_length >= 400:
        add_reason("no_sections_detected", "medium", "No sections were detected despite substantial text.", sections_count)
    elif sections_count <= 1 and full_text_length >= 1200:
        add_reason("low_section_count", "low", "Few sections were detected for a long CV.", sections_count)

    if fallback_triggered:
        add_reason("fallback_triggered", "low", "The fallback extractor was required.", True)

    severity_weights = {"critical": 50, "high": 25, "medium": 12, "low": 5}
    penalty = sum(severity_weights[reason["severity"]] for reason in reasons)
    score = max(0, 100 - penalty)
    weak = any(reason["severity"] in {"critical", "high"} for reason in reasons) or score < 70

    return {
        "score": score,
        "weak": weak,
        "reason_count": len(reasons),
        "reasons": reasons,
        "metrics": {
            "page_count": page_count,
            "empty_pages": empty_pages,
            "full_text_length": full_text_length,
            "total_blocks": total_blocks,
            "sections_count": sections_count,
            "avg_chars_per_page": round(avg_chars_per_page, 2),
            "avg_blocks_per_page": round(avg_blocks_per_page, 2),
            "alnum_ratio": round(alnum_ratio, 3),
            "short_line_ratio": round(short_line_ratio, 3),
            "repeated_line_ratio": round(repeated_line_ratio, 3),
            "noise_ratio": round(noise_ratio, 3),
            "fallback_triggered": fallback_triggered,
        },
    }


def _normalize_page(page: RawPageExtraction) -> RawPageExtraction:
    blocks = [
        RawTextBlock(
            text=normalize_text(block.text),
            page_number=block.page_number,
            bbox=block.bbox,
            kind=block.kind,
        )
        for block in page.blocks
        if normalize_text(block.text)
    ]
    return RawPageExtraction(
        page_number=page.page_number,
        text=normalize_text(page.text),
        blocks=blocks,
    )
