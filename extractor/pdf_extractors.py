"""PDF extraction backends for phase-1 CV extraction."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import fitz
    import pdfplumber

from extractor.models import RawPageExtraction, RawPdfExtraction, RawTextBlock
from extractor.normalize import normalize_text


def extract_with_pymupdf(pdf_path: str) -> RawPdfExtraction:
    """Extract pages and raw blocks with PyMuPDF in reading order."""

    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for extract_with_pymupdf") from exc

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError("PDF file does not exist: {0}".format(pdf_path))

    try:
        document = fitz.open(pdf_path)
    except Exception as exc:
        raise RuntimeError("Failed to open PDF with PyMuPDF: {0}".format(pdf_path)) from exc

    pages: List[RawPageExtraction] = []
    raw_blocks: List[RawTextBlock] = []
    metadata: Dict[str, Any] = {
        "source_path": str(path),
        "extractor": "pymupdf",
        "page_count": len(document),
        "document_metadata": dict(document.metadata or {}),
    }

    try:
        for page_number, page in enumerate(document, start=1):
            page_blocks = _extract_pymupdf_blocks(page, page_number)
            page_text = normalize_text("\n".join(block.text for block in page_blocks))
            pages.append(
                RawPageExtraction(
                    page_number=page_number,
                    text=page_text,
                    blocks=page_blocks,
                    raw_blocks=page_blocks,
                )
            )
            raw_blocks.extend(page_blocks)
    except Exception as exc:
        raise RuntimeError("Failed during PyMuPDF extraction: {0}".format(pdf_path)) from exc
    finally:
        document.close()

    return RawPdfExtraction(
        full_text=normalize_text("\n\n".join(page.text for page in pages if page.text)),
        pages=pages,
        sections=[],
        metadata=metadata,
        raw_blocks=raw_blocks,
    )


def extract_with_pdfplumber(pdf_path: str) -> RawPdfExtraction:
    """Extract pages and raw blocks with pdfplumber."""

    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required for extract_with_pdfplumber") from exc

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError("PDF file does not exist: {0}".format(pdf_path))

    try:
        document = pdfplumber.open(pdf_path)
    except Exception as exc:
        raise RuntimeError("Failed to open PDF with pdfplumber: {0}".format(pdf_path)) from exc

    pages: List[RawPageExtraction] = []
    raw_blocks: List[RawTextBlock] = []
    metadata: Dict[str, Any] = {
        "source_path": str(path),
        "extractor": "pdfplumber",
    }

    try:
        for page_number, page in enumerate(document.pages, start=1):
            page_blocks = _extract_pdfplumber_blocks(page, page_number)
            page_text = normalize_text("\n".join(block.text for block in page_blocks))
            pages.append(
                RawPageExtraction(
                    page_number=page_number,
                    text=page_text,
                    blocks=page_blocks,
                    raw_blocks=page_blocks,
                )
            )
            raw_blocks.extend(page_blocks)
    except Exception as exc:
        raise RuntimeError("Failed during pdfplumber extraction: {0}".format(pdf_path)) from exc
    finally:
        document.close()

    metadata["page_count"] = len(pages)
    return RawPdfExtraction(
        full_text=normalize_text("\n\n".join(page.text for page in pages if page.text)),
        pages=pages,
        sections=[],
        metadata=metadata,
        raw_blocks=raw_blocks,
    )


def merge_extractions(primary: RawPdfExtraction, fallback: RawPdfExtraction) -> RawPdfExtraction:
    """Merge extractor outputs conservatively page by page."""

    if len(primary.pages) != len(fallback.pages):
        return fallback if _score_extraction(fallback) > _score_extraction(primary) else primary

    merged_pages: List[RawPageExtraction] = []
    merged_raw_blocks: List[RawTextBlock] = []
    fallback_used_pages: List[int] = []

    for primary_page, fallback_page in zip(primary.pages, fallback.pages):
        use_fallback = _page_score(fallback_page) > _page_score(primary_page)
        selected_page = fallback_page if use_fallback else primary_page
        if use_fallback:
            fallback_used_pages.append(primary_page.page_number)
        merged_pages.append(selected_page)
        merged_raw_blocks.extend(selected_page.raw_blocks or selected_page.blocks)

    metadata = dict(primary.metadata)
    metadata["fallback_extractor"] = fallback.metadata.get("extractor")
    metadata["fallback_used_pages"] = fallback_used_pages
    return RawPdfExtraction(
        full_text=normalize_text("\n\n".join(page.text for page in merged_pages if page.text)),
        pages=merged_pages,
        sections=[],
        metadata=metadata,
        raw_blocks=merged_raw_blocks,
    )


def _extract_pymupdf_blocks(page: "fitz.Page", page_number: int) -> List[RawTextBlock]:
    raw_dict = page.get_text("dict", sort=True)
    blocks: List[RawTextBlock] = []

    for block_index, raw_block in enumerate(raw_dict.get("blocks", [])):
        if raw_block.get("type") != 0:
            continue
        text = _flatten_pymupdf_block_text(raw_block)
        if not normalize_text(text):
            continue
        bbox_raw = raw_block.get("bbox")
        bbox = tuple(float(value) for value in bbox_raw) if bbox_raw else None
        blocks.append(
            RawTextBlock(
                block_id="raw-{0}-{1}".format(page_number, block_index),
                text=text,
                page_number=page_number,
                bbox=bbox,  # type: ignore[arg-type]
                kind="other",
            )
        )
    return sorted(blocks, key=_raw_block_sort_key)


def _flatten_pymupdf_block_text(raw_block: Dict[str, Any]) -> str:
    lines: List[str] = []
    for line in raw_block.get("lines", []):
        spans = line.get("spans", [])
        line_text = "".join(span.get("text", "") for span in spans)
        if line_text.strip():
            lines.append(line_text)
    return "\n".join(lines)


def _extract_pdfplumber_blocks(page: "pdfplumber.page.Page", page_number: int) -> List[RawTextBlock]:
    words = page.extract_words(
        x_tolerance=2,
        y_tolerance=3,
        keep_blank_chars=False,
        use_text_flow=True,
    )
    if not words:
        return []

    groups: List[List[Dict[str, Any]]] = []
    current_group: List[Dict[str, Any]] = []
    current_top: Optional[float] = None

    for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
        top = float(word["top"])
        if current_top is None or abs(top - current_top) <= 3:
            current_group.append(word)
            current_top = top if current_top is None else current_top
            continue
        groups.append(current_group)
        current_group = [word]
        current_top = top

    if current_group:
        groups.append(current_group)

    blocks: List[RawTextBlock] = []
    for block_index, group in enumerate(groups):
        text = " ".join(word["text"] for word in sorted(group, key=lambda item: float(item["x0"])))
        if not normalize_text(text):
            continue
        bbox = (
            min(float(word["x0"]) for word in group),
            min(float(word["top"]) for word in group),
            max(float(word["x1"]) for word in group),
            max(float(word["bottom"]) for word in group),
        )
        blocks.append(
            RawTextBlock(
                block_id="raw-{0}-{1}".format(page_number, block_index),
                text=text,
                page_number=page_number,
                bbox=bbox,
                kind="other",
            )
        )
    return sorted(blocks, key=_raw_block_sort_key)


def _raw_block_sort_key(block: RawTextBlock) -> tuple:
    if block.bbox is None:
        return (block.page_number, 0.0, 0.0, block.block_id)
    return (block.page_number, round(block.bbox[1], 2), round(block.bbox[0], 2), block.block_id)


def _score_extraction(extraction: RawPdfExtraction) -> int:
    return sum(_page_score(page) for page in extraction.pages)


def _page_score(page: RawPageExtraction) -> int:
    raw_blocks = page.raw_blocks or page.blocks
    return len(page.text) + (len(raw_blocks) * 20)
