"""Utilities for evaluating whether Phase 2 recovered parser-missed raw-text content."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from phase2.reconciliation.normalize import normalize_text

_BULLET_SPLIT_RE = re.compile(r"(?:^|\n)\s*[•●▪·]\s*", re.MULTILINE)
_TOKEN_RE = re.compile(r"[a-z0-9+#./]+")


def load_missed_csv(path: str | Path) -> List[Dict[str, Any]]:
    """Load the parser-vs-raw benchmark CSV."""

    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows: List[Dict[str, Any]] = []
        for row in reader:
            rows.append(
                {
                    "cv_id": (row.get("\ufeffcv_id") or row.get("cv_id") or "").strip(),
                    "missed_count": int((row.get("missed_count") or "0").strip() or 0),
                    "missed_from_raw_text": row.get("missed_from_raw_text") or "",
                }
            )
        return rows


def load_phase2_results(path: str | Path) -> List[Dict[str, Any]]:
    """Load Phase 2 JSONL results."""

    results_path = Path(path)
    with results_path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def evaluate_phase2_missed_content(
    csv_rows: Sequence[Dict[str, Any]],
    phase2_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluate whether Phase 2 recovered content listed in missed_from_raw_text."""

    phase2_by_cv_id = {str(row.get("cv_id", "")).strip(): row for row in phase2_rows if row.get("cv_id") is not None}

    row_reports: List[Dict[str, Any]] = []
    total_chunks = 0
    recovered_chunks = 0
    rows_with_missed = 0
    rows_with_any_recovered = 0

    for csv_row in csv_rows:
        cv_id = str(csv_row.get("cv_id", "")).strip()
        missed_text = csv_row.get("missed_from_raw_text", "")
        chunks = split_missed_text_into_chunks(missed_text)
        if not chunks:
            continue

        rows_with_missed += 1
        phase2_row = phase2_by_cv_id.get(cv_id)
        if phase2_row is None:
            row_reports.append(
                {
                    "cv_id": cv_id,
                    "file_path": "",
                    "status": "missing_phase2_result",
                    "missed_chunks": chunks,
                    "recovered_chunks": [],
                    "unrecovered_chunks": chunks,
                    "recovered_ratio": 0.0,
                }
            )
            total_chunks += len(chunks)
            continue

        validated_data = phase2_row.get("validated_cv", {}).get("data", {})
        evidence_strings = flatten_validated_data_strings(validated_data)
        normalized_whole = normalize_for_match(" ".join(evidence_strings))
        normalized_segments = [normalize_for_match(segment) for segment in evidence_strings if normalize_for_match(segment)]

        recovered: List[str] = []
        unrecovered: List[str] = []
        for chunk in chunks:
            if is_chunk_recovered(chunk, normalized_whole, normalized_segments, validated_data):
                recovered.append(chunk)
            else:
                unrecovered.append(chunk)

        total_chunks += len(chunks)
        recovered_chunks += len(recovered)
        if recovered:
            rows_with_any_recovered += 1

        row_reports.append(
            {
                "cv_id": cv_id,
                "file_path": phase2_row.get("file_path", ""),
                "status": "matched",
                "missed_chunks": chunks,
                "recovered_chunks": recovered,
                "unrecovered_chunks": unrecovered,
                "recovered_ratio": round(len(recovered) / max(1, len(chunks)), 3),
            }
        )

    return {
        "total_rows_with_missed_content": rows_with_missed,
        "rows_with_any_recovered_content": rows_with_any_recovered,
        "total_missed_chunks": total_chunks,
        "recovered_chunks": recovered_chunks,
        "recovery_rate": round(recovered_chunks / max(1, total_chunks), 3),
        "rows": row_reports,
    }


def split_missed_text_into_chunks(text: str) -> List[str]:
    """Split missed raw text into deterministic comparison chunks."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    bullet_parts = [part.strip() for part in _BULLET_SPLIT_RE.split(normalized) if part.strip()]
    raw_parts = bullet_parts if len(bullet_parts) > 1 else [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]

    chunks: List[str] = []
    for part in raw_parts:
        subparts = [segment.strip() for segment in re.split(r"\n\s*\n", part) if segment.strip()]
        for subpart in subparts:
            cleaned = normalize_text(subpart)
            if not cleaned:
                continue
            if len(tokenize(cleaned)) < 3:
                continue
            chunks.append(cleaned)
    return _dedupe_preserve_order(chunks)


def flatten_validated_data_strings(value: Any) -> List[str]:
    """Collect all string leaves from validated_cv.data for matching."""

    strings: List[str] = []
    _walk_strings(value, strings)
    return strings


def normalize_for_match(text: str) -> str:
    """Normalize text for deterministic containment checks."""

    normalized = normalize_text(text).lower()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9+#./ ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def is_chunk_recovered(
    chunk: str,
    normalized_whole: str,
    normalized_segments: Sequence[str],
    validated_data: Dict[str, Any] | None = None,
) -> bool:
    """Return whether a missed-content chunk appears to be recovered in Phase 2 output."""

    normalized_chunk = normalize_for_match(chunk)
    if not normalized_chunk:
        return False
    if normalized_chunk in normalized_whole:
        return True

    chunk_tokens = tokenize(normalized_chunk)
    if len(chunk_tokens) < 3:
        return False

    for segment in normalized_segments:
        if not segment:
            continue
        if _token_overlap_ratio(chunk_tokens, tokenize(segment)) >= 0.8:
            return True

    if validated_data and _is_scalar_education_chunk_recovered(chunk, validated_data):
        return True
    return False


def tokenize(text: str) -> List[str]:
    """Tokenize normalized text for overlap checks."""

    return _TOKEN_RE.findall(text.lower())


def _token_overlap_ratio(left: Sequence[str], right: Sequence[str]) -> float:
    if not left or not right:
        return 0.0
    left_set = set(left)
    right_set = set(right)
    return len(left_set & right_set) / float(max(1, min(len(left_set), len(right_set))))


def _walk_strings(value: Any, output: List[str]) -> None:
    if isinstance(value, str):
        normalized = normalize_text(value)
        if normalized:
            output.append(normalized)
        return
    if isinstance(value, list):
        for item in value:
            _walk_strings(item, output)
        return
    if isinstance(value, dict):
        for item in value.values():
            _walk_strings(item, output)


def _is_scalar_education_chunk_recovered(chunk: str, validated_data: Dict[str, Any]) -> bool:
    """Handle scalar education details that may be stored without their raw-text wrapper."""

    education_entries = validated_data.get("education")
    if not isinstance(education_entries, list):
        return False

    normalized_chunk = normalize_for_match(chunk)
    compact_chunk = re.sub(r"\s+", "", normalized_chunk)

    if "gpa" in normalized_chunk:
        ratio_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", chunk)
        if not ratio_match:
            return False
        expected_ratio = f"{ratio_match.group(1)}/{ratio_match.group(2)}"
        expected_ratio_compact = re.sub(r"\s+", "", normalize_for_match(expected_ratio))

        for entry in education_entries:
            if not isinstance(entry, dict):
                continue
            gpa_value = entry.get("GPA") or entry.get("gpa") or ""
            if not isinstance(gpa_value, str):
                continue
            normalized_gpa = normalize_for_match(gpa_value)
            compact_gpa = re.sub(r"\s+", "", normalized_gpa)
            if expected_ratio_compact and expected_ratio_compact in compact_gpa:
                return True

        if expected_ratio_compact and expected_ratio_compact in compact_chunk:
            return False

    scalar_match = re.search(r"\(\s*([A-F][+-]?)\s*\)", chunk, re.IGNORECASE)
    if scalar_match and "project grade" in normalized_chunk:
        expected_grade = scalar_match.group(1).upper()
        for entry in education_entries:
            if not isinstance(entry, dict):
                continue
            project_grade = entry.get("graduation_project_grade") or entry.get("project_grade") or ""
            if not isinstance(project_grade, str):
                continue
            normalized_value = normalize_for_match(project_grade).upper()
            if expected_grade == normalized_value or f" {expected_grade} " in f" {normalized_value} ":
                return True

    return False


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for value in values:
        key = normalize_for_match(value)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped
