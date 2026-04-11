# Raw CV PDF Extraction

Phase 1 of the CV pipeline focuses on faithful PDF text extraction only. It preserves raw text, page-wise output, block-wise output, and a best-effort heading-based section split without attempting schema mapping, rewriting, or LLM parsing.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run On One PDF

```bash
python -c "from extraction.service import extract_raw_pdf; import json; result = extract_raw_pdf('path/to/resume.pdf'); print(json.dumps(result.model_dump(), indent=2))"
```

Or use the included test runner:

```bash
python run_extraction.py path/to/resume.pdf
python run_extraction.py "CVs/Mohamed Saber.pdf" --output extracted.jsonl
python run_extraction.py "CVs/Jan_Osama CV.pdf" --output extracted.jsonl
```

`--output` appends one JSON object per line. Use a `.jsonl` filename so repeated
single-PDF runs and batch runs all accumulate cleanly in the same file.

## Sample Returned JSON

```json
{
  "full_text": "SUMMARY\nBackend engineer...\n\nEXPERIENCE\nAcme Corp...",
  "pages": [
    {
      "page_number": 1,
      "text": "SUMMARY\nBackend engineer...",
      "blocks": [
        {
          "text": "SUMMARY",
          "page_number": 1,
          "bbox": [72.0, 80.0, 180.0, 96.0],
          "kind": "heading"
        }
      ]
    }
  ],
  "sections": [
    {
      "heading": "Summary",
      "content": "Backend engineer...",
      "source_pages": [1]
    }
  ],
  "metadata": {
    "source_path": "path/to/resume.pdf",
    "extractor": "pymupdf",
    "page_count": 1,
    "fallback_triggered": false
  }
}
```
