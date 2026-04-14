"""Tests for Phase 2 coverage gap reporting."""

from phase2.reporting.coverage_report import analyze_phase2_result_row


def test_report_flags_missing_skill_from_phase2_and_parser() -> None:
    row = _row(
        phase2_input={"skill_candidates": ["Python", "Docker"]},
        parser_payload={"technical_skills": ["Python", "Docker"]},
        validated_data={"technical_skills": ["Python"]},
    )

    report = analyze_phase2_result_row(row)

    assert report["missing"]["technical_skills"]["phase2_input"] == ["Docker"]
    assert report["missing"]["technical_skills"]["parser"] == ["Docker"]


def test_report_flags_missing_project_candidate() -> None:
    row = _row(
        phase2_input={
            "project_candidates": [
                {
                    "text": "Tellix | CV platform | 2024",
                    "source_section": "Projects",
                    "hints": {"dates": ["2024"]},
                }
            ]
        },
        parser_payload={},
        validated_data={"projects": []},
    )

    report = analyze_phase2_result_row(row)

    assert len(report["missing"]["projects"]["phase2_input"]) == 1
    assert report["missing"]["projects"]["phase2_input"][0]["text"] == "Tellix | CV platform | 2024"


def test_report_ignores_project_when_final_output_contains_match() -> None:
    row = _row(
        phase2_input={
            "project_candidates": [
                {
                    "text": "Tellix | CV platform | 2024",
                    "source_section": "Projects",
                    "hints": {"dates": ["2024"]},
                }
            ]
        },
        parser_payload={},
        validated_data={
            "projects": [
                {
                    "project_name": "Tellix",
                    "description": "CV platform",
                    "tools": [],
                    "duration": "2024",
                    "link": "",
                }
            ]
        },
    )

    report = analyze_phase2_result_row(row)

    assert "projects" not in report["missing"]


def test_report_flags_missing_linkedin_candidate_when_final_empty() -> None:
    row = _row(
        phase2_input={"contact_candidates": {"linkedin": ["linkedin.com/in/jane"]}},
        parser_payload={},
        validated_data={"linkedin": ""},
    )

    report = analyze_phase2_result_row(row)

    assert report["missing"]["linkedin"]["phase2_input"] == ["linkedin.com/in/jane"]


def _row(
    phase2_input: dict,
    parser_payload: dict,
    validated_data: dict,
) -> dict:
    base_phase2_input = {
        "contract_version": "phase2-input-v1",
        "full_text": "",
        "canonical_sections": {},
        "uncategorized_text": "",
        "contact_candidates": {
            "name": [],
            "email": [],
            "phone": [],
            "location": [],
            "linkedin": [],
            "github": [],
        },
        "skill_candidates": [],
        "language_candidates": [],
        "experience_candidates": [],
        "project_candidates": [],
        "education_candidates": [],
        "certification_candidates": [],
        "training_candidates": [],
        "diagnostics_flags": [],
        "source_metadata": {},
    }
    for key, value in phase2_input.items():
        if key == "contact_candidates":
            base_phase2_input["contact_candidates"].update(value)
        else:
            base_phase2_input[key] = value

    return {
        "cv_id": "1",
        "file_path": "CVs/test.pdf",
        "phase2_input": base_phase2_input,
        "parser_payload": parser_payload,
        "validated_cv": {"data": validated_data},
    }
