"""Phase 1 regression metrics for extractor hardening."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from contracts.phase1_output import Phase1Output
from phase2.adapters.phase1_to_phase2 import build_phase2_input
from phase2.reconciliation.lists import recover_soft_skills
from phase2.reconciliation.supplemental import recover_supplemental_content

_SECTION_BLEED_RE = re.compile(
    r"(?:^|\s)(?:EDUCATION|CERTIFICATIONS|TECHNICAL SKILLS|SKILLS|LANGUAGES|COURSES|EXPERIENCE|PROJECTS|ACHIEVEMENTS)\s*&\s*$",
    re.IGNORECASE,
)
_COMPOSITE_HEADING_TOKEN_RE = re.compile(r"\s*(?:&|/|\band\b)\s*", re.IGNORECASE)
_KNOWN_COMPOSITE_PARTS = {
    "education",
    "certifications",
    "courses",
    "training",
    "trainings",
    "skills",
    "languages",
    "experience",
    "projects",
    "achievements",
    "awards",
    "activities",
    "information",
    "summary",
}


def load_phase1_snapshot(path: str | Path) -> List[Phase1Output]:
    """Load a JSONL file of Phase 1 outputs."""

    rows: List[Phase1Output] = []
    snapshot_path = Path(path)
    with snapshot_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            filtered = {
                key: value
                for key, value in payload.items()
                if key
                in {
                    "full_text",
                    "pages",
                    "sections",
                    "metadata",
                    "raw_blocks",
                    "normalized_blocks",
                    "semantic_blocks",
                    "diagnostics",
                }
            }
            metadata = dict(filtered.get("metadata") or {})
            if "cv_id" in payload:
                metadata["cv_id"] = payload["cv_id"]
            if "file_path" in payload:
                metadata["file_path"] = payload["file_path"]
            filtered["metadata"] = metadata
            rows.append(Phase1Output.model_validate(filtered))
    return rows


def build_phase1_regression_report(rows: Sequence[Phase1Output]) -> Dict[str, Any]:
    """Build regression metrics over a collection of Phase 1 outputs."""

    report_rows: List[Dict[str, Any]] = []
    oversized_general_files: List[Dict[str, Any]] = []
    section_bleed_files: List[Dict[str, Any]] = []
    suspicious_composite_heading_files: List[Dict[str, Any]] = []

    aggregate_candidate_counts = {
        "projects": 0,
        "experience": 0,
        "education": 0,
        "certifications": 0,
        "trainings": 0,
        "achievements": 0,
        "activities": 0,
        "publications": 0,
        "soft_skills": 0,
    }

    for row in rows:
        phase2_input = build_phase2_input(row)
        supplemental_data, _ = recover_supplemental_content(phase2_input, {}, {})
        soft_skills, _ = recover_soft_skills(phase2_input, {}, {})

        candidate_counts = {
            "projects": len(phase2_input.project_candidates),
            "experience": len(phase2_input.experience_candidates),
            "education": len(phase2_input.education_candidates),
            "certifications": len(phase2_input.certification_candidates),
            "trainings": len(phase2_input.training_candidates),
            "achievements": len(supplemental_data["achievements"]),
            "activities": len(supplemental_data["activities"]),
            "publications": len(supplemental_data["publications"]),
            "soft_skills": len(soft_skills),
        }
        for key, value in candidate_counts.items():
            aggregate_candidate_counts[key] += value

        bleed_markers = detect_section_bleed(row)
        composite_headings = detect_suspicious_composite_headings(row)
        possible_errors = list(row.diagnostics.possible_errors)
        has_oversized_general = "oversized_general_section" in possible_errors

        row_report = {
            "cv_id": str(row.metadata.get("cv_id", "")),
            "file_path": str(row.metadata.get("file_path", "")),
            "section_count": len(row.sections),
            "oversized_general": has_oversized_general,
            "section_bleed_markers": bleed_markers,
            "suspicious_composite_headings": composite_headings,
            "candidate_counts": candidate_counts,
            "possible_errors": possible_errors,
        }
        report_rows.append(row_report)

        if has_oversized_general:
            oversized_general_files.append(
                {
                    "cv_id": row_report["cv_id"],
                    "file_path": row_report["file_path"],
                    "general_block_ratio": row.diagnostics.general_block_ratio,
                }
            )
        if bleed_markers:
            section_bleed_files.append(
                {
                    "cv_id": row_report["cv_id"],
                    "file_path": row_report["file_path"],
                    "markers": bleed_markers,
                }
            )
        if composite_headings:
            suspicious_composite_heading_files.append(
                {
                    "cv_id": row_report["cv_id"],
                    "file_path": row_report["file_path"],
                    "headings": composite_headings,
                }
            )

    return {
        "total_files": len(rows),
        "section_count_per_cv": [
            {
                "cv_id": row["cv_id"],
                "file_path": row["file_path"],
                "section_count": row["section_count"],
            }
            for row in report_rows
        ],
        "files_with_oversized_general": oversized_general_files,
        "files_with_section_bleed": section_bleed_files,
        "files_with_suspicious_composite_headings": suspicious_composite_heading_files,
        "candidate_counts_total": aggregate_candidate_counts,
        "candidate_counts_per_cv": [
            {
                "cv_id": row["cv_id"],
                "file_path": row["file_path"],
                "candidate_counts": row["candidate_counts"],
            }
            for row in report_rows
        ],
        "rows": report_rows,
    }


def detect_section_bleed(row: Phase1Output) -> List[str]:
    """Detect likely trailing section bleed markers inside section content."""

    markers: List[str] = []
    for section in row.sections:
        content = section.content.strip()
        if not content:
            continue
        last_line = content.splitlines()[-1].strip()
        if _SECTION_BLEED_RE.search(last_line):
            markers.append(f"{section.heading}: {last_line}")
    return _dedupe_preserve_order(markers)


def detect_suspicious_composite_headings(row: Phase1Output) -> List[str]:
    """Detect headings that likely combine multiple logical sections."""

    headings: List[str] = []
    for section in row.sections:
        heading = section.heading.strip()
        lowered = heading.lower()
        if not _COMPOSITE_HEADING_TOKEN_RE.search(lowered):
            continue
        parts = [part.strip() for part in _COMPOSITE_HEADING_TOKEN_RE.split(lowered) if part.strip()]
        if len(parts) < 2:
            continue
        if sum(1 for part in parts if any(token in part for token in _KNOWN_COMPOSITE_PARTS)) >= 2:
            headings.append(heading)
    return _dedupe_preserve_order(headings)


def write_phase1_regression_report(output_path: str | Path, report: Dict[str, Any]) -> None:
    """Write one JSON regression report."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        key = value.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output
