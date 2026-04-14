"""Tests for missed_from_raw_text Phase 2 recovery benchmarking."""

from phase2.reporting.missed_content_report import (
    evaluate_phase2_missed_content,
    is_chunk_recovered,
    normalize_for_match,
    split_missed_text_into_chunks,
)


def test_split_missed_text_into_chunks_splits_bullets_and_paragraphs() -> None:
    text = "• Docker, Kubernetes, Helm\n\n• GPA 2.75 / 4.0 (Good).\n\nAnother missing paragraph here."

    chunks = split_missed_text_into_chunks(text)

    assert chunks == [
        "Docker, Kubernetes, Helm",
        "GPA 2.75 / 4.0 (Good).",
        "Another missing paragraph here.",
    ]


def test_is_chunk_recovered_matches_by_normalized_substring() -> None:
    chunk = "Docker, Kubernetes, Helm"
    normalized_whole = normalize_for_match("Skills Docker Kubernetes Helm AWS")
    normalized_segments = [normalize_for_match("Skills Docker Kubernetes Helm AWS")]

    assert is_chunk_recovered(chunk, normalized_whole, normalized_segments) is True


def test_is_chunk_recovered_matches_scalar_education_gpa_value() -> None:
    chunk = "GPA 2.75 / 4.0 (Good)."
    validated_data = {
        "education": [
            {
                "university_name": "Higher Technological Institute",
                "GPA": "2.75/4.0",
            }
        ]
    }

    assert is_chunk_recovered(chunk, "", [], validated_data) is True


def test_is_chunk_recovered_matches_scalar_education_project_grade_value() -> None:
    chunk = "Graduation Project Grade (A+)"
    validated_data = {
        "education": [
            {
                "university_name": "Higher Technological Institute",
                "graduation_project_grade": "A+",
            }
        ]
    }

    assert is_chunk_recovered(chunk, "", [], validated_data) is True


def test_evaluate_phase2_missed_content_reports_recovered_and_unrecovered_chunks() -> None:
    csv_rows = [
        {
            "cv_id": "1",
            "missed_count": 2,
            "missed_from_raw_text": "• Docker, Kubernetes, Helm\n\n• GPA 2.75 / 4.0 (Good).",
        }
    ]
    phase2_rows = [
        {
            "cv_id": "1",
            "file_path": "CVs/test.pdf",
            "validated_cv": {
                "data": {
                    "technical_skills": ["Docker", "Kubernetes", "Helm"],
                    "education": [{"GPA": "2.75/4.0"}],
                }
            },
        }
    ]

    report = evaluate_phase2_missed_content(csv_rows, phase2_rows)

    assert report["total_rows_with_missed_content"] == 1
    assert report["recovered_chunks"] == 2
    row = report["rows"][0]
    assert row["recovered_chunks"] == [
        "Docker, Kubernetes, Helm",
        "GPA 2.75 / 4.0 (Good).",
    ]
    assert row["unrecovered_chunks"] == []
