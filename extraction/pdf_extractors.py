"""PDF extraction backends for raw CV text preservation."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import fitz
    import pdfplumber

from extraction.models import RawPageExtraction, RawPdfExtraction, RawTextBlock
from extraction.normalize import normalize_text
from extraction.section_splitter import classify_heading_from_text


def extract_with_pymupdf(pdf_path: str) -> RawPdfExtraction:
    """Extract page text and blocks with PyMuPDF."""

    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for extract_with_pymupdf") from exc

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

    try:
        document = fitz.open(pdf_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to open PDF with PyMuPDF: {pdf_path}") from exc

    pages: List[RawPageExtraction] = []
    metadata: Dict[str, Any] = {
        "source_path": str(path),
        "extractor": "pymupdf",
        "page_count": len(document),
        "document_metadata": dict(document.metadata or {}),
    }

    try:
        for index, page in enumerate(document, start=1):
            page_text = normalize_text(page.get_text("text") or "")
            blocks = _extract_pymupdf_blocks(page, index)
            pages.append(
                RawPageExtraction(page_number=index, text=page_text, blocks=blocks)
            )
    except Exception as exc:
        raise RuntimeError(f"Failed during PyMuPDF extraction: {pdf_path}") from exc
    finally:
        document.close()

    full_text = "\n\n".join(page.text for page in pages if page.text).strip()
    return RawPdfExtraction(full_text=full_text, pages=pages, sections=[], metadata=metadata)


def extract_with_pdfplumber(pdf_path: str) -> RawPdfExtraction:
    """Extract page text and coarse blocks with pdfplumber."""

    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required for extract_with_pdfplumber") from exc

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

    try:
        document = pdfplumber.open(pdf_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to open PDF with pdfplumber: {pdf_path}") from exc

    pages: List[RawPageExtraction] = []
    metadata: Dict[str, Any] = {
        "source_path": str(path),
        "extractor": "pdfplumber",
    }

    try:
        for index, page in enumerate(document.pages, start=1):
            page_text = normalize_text(page.extract_text() or "")
            blocks = _extract_pdfplumber_blocks(page, index)
            pages.append(
                RawPageExtraction(page_number=index, text=page_text, blocks=blocks)
            )
    except Exception as exc:
        raise RuntimeError(f"Failed during pdfplumber extraction: {pdf_path}") from exc
    finally:
        document.close()

    metadata["page_count"] = len(pages)
    full_text = "\n\n".join(page.text for page in pages if page.text).strip()
    return RawPdfExtraction(full_text=full_text, pages=pages, sections=[], metadata=metadata)


def merge_extractions(
    primary: RawPdfExtraction, fallback: RawPdfExtraction
) -> RawPdfExtraction:
    """Merge fallback data conservatively, preferring the primary extractor."""

    if len(primary.pages) != len(fallback.pages):
        return fallback if _score_extraction(fallback) > _score_extraction(primary) else primary

    merged_pages: List[RawPageExtraction] = []
    fallback_used_pages: List[int] = []

    for primary_page, fallback_page in zip(primary.pages, fallback.pages):
        use_fallback_text = len(primary_page.text.strip()) < len(fallback_page.text.strip())
        use_fallback_blocks = len(primary_page.blocks) < len(fallback_page.blocks)

        selected_text = fallback_page.text if use_fallback_text else primary_page.text
        selected_blocks = fallback_page.blocks if use_fallback_blocks else primary_page.blocks

        if use_fallback_text or use_fallback_blocks:
            fallback_used_pages.append(primary_page.page_number)

        merged_pages.append(
            RawPageExtraction(
                page_number=primary_page.page_number,
                text=selected_text,
                blocks=selected_blocks,
            )
        )

    full_text = "\n\n".join(page.text for page in merged_pages if page.text).strip()
    metadata = dict(primary.metadata)
    metadata["fallback_extractor"] = fallback.metadata.get("extractor")
    metadata["fallback_used_pages"] = fallback_used_pages
    return RawPdfExtraction(full_text=full_text, pages=merged_pages, sections=[], metadata=metadata)


def _extract_pymupdf_blocks(page: "fitz.Page", page_number: int) -> List[RawTextBlock]:
    """Convert PyMuPDF text dict output into raw text blocks."""

    blocks: List[RawTextBlock] = []
    raw_dict = page.get_text("dict")
    for raw_block in raw_dict.get("blocks", []):
        if raw_block.get("type") != 0:
            continue
        text = _flatten_pymupdf_block_text(raw_block)
        normalized = normalize_text(text)
        if not normalized:
            continue
        bbox_raw = raw_block.get("bbox")
        bbox = tuple(float(value) for value in bbox_raw) if bbox_raw else None
        blocks.append(
            RawTextBlock(
                text=normalized,
                page_number=page_number,
                bbox=bbox,  # type: ignore[arg-type]
                kind=classify_heading_from_text(normalized),
            )
        )
    return blocks


def _flatten_pymupdf_block_text(raw_block: Dict[str, Any]) -> str:
    lines: List[str] = []
    for line in raw_block.get("lines", []):
        spans = line.get("spans", [])
        line_text = "".join(span.get("text", "") for span in spans)
        if line_text.strip():
            lines.append(line_text)
    return "\n".join(lines)


def _extract_pdfplumber_blocks(
    page: "pdfplumber.page.Page", page_number: int
) -> List[RawTextBlock]:
    """Build coarse text blocks from pdfplumber words grouped by line position."""

    words = page.extract_words(
        x_tolerance=2,
        y_tolerance=3,
        keep_blank_chars=False,
        use_text_flow=True,
    )
    if not words:
        return []

    grouped_lines: List[List[Dict[str, Any]]] = []
    current_line: List[Dict[str, Any]] = []
    current_top: Optional[float] = None

    for word in words:
        top = float(word["top"])
        if current_top is None or abs(top - current_top) <= 3:
            current_line.append(word)
            current_top = top if current_top is None else min(current_top, top)
            continue
        grouped_lines.append(current_line)
        current_line = [word]
        current_top = top

    if current_line:
        grouped_lines.append(current_line)

    blocks: List[RawTextBlock] = []
    for line_words in grouped_lines:
        sorted_words = sorted(line_words, key=lambda item: (float(item["x0"]), float(item["top"])))
        text = normalize_text(" ".join(word["text"] for word in sorted_words))
        if not text:
            continue
        bbox = (
            min(float(word["x0"]) for word in sorted_words),
            min(float(word["top"]) for word in sorted_words),
            max(float(word["x1"]) for word in sorted_words),
            max(float(word["bottom"]) for word in sorted_words),
        )
        blocks.append(
            RawTextBlock(
                text=text,
                page_number=page_number,
                bbox=bbox,
                kind=classify_heading_from_text(text),
            )
        )
    return blocks


def _score_extraction(extraction: RawPdfExtraction) -> int:
    return sum(len(page.text) + (len(page.blocks) * 20) for page in extraction.pages)
