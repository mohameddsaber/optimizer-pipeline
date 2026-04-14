"""Coverage-mode list recovery helpers."""

import re
from typing import Any, Dict, Iterable, List, Tuple

from contracts.phase2_input import Phase2Input
from phase2.reconciliation.normalize import normalize_skill, normalize_text


def recover_soft_skills(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Preserve optimizer soft skills and append missing competency-style source-backed items."""

    return _recover_list_field(
        base_values=_get_string_list(optimizer_payload, "soft_skills"),
        source_values=_extract_soft_skill_candidates(phase2_input),
        parser_values=_filter_recoverable_soft_skill_values(_get_string_list(parser_payload, "soft_skills")),
        field_name="soft_skills",
        comparison_key_fn=_comparison_key,
    )


def recover_technical_skills(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Preserve optimizer skills and append missing source-backed skills."""

    return _recover_list_field(
        base_values=_get_string_list(optimizer_payload, "technical_skills"),
        source_values=_filter_recoverable_skill_values(phase2_input.skill_candidates),
        parser_values=_filter_recoverable_skill_values(_get_string_list(parser_payload, "technical_skills")),
        field_name="technical_skills",
        comparison_key_fn=_technical_skill_comparison_key,
    )


def recover_languages(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Preserve optimizer languages and append missing source-backed languages."""

    return _recover_list_field(
        base_values=_get_string_list(optimizer_payload, "languages"),
        source_values=_filter_recoverable_language_values(phase2_input.language_candidates),
        parser_values=_filter_recoverable_language_values(_get_string_list(parser_payload, "languages")),
        field_name="languages",
        comparison_key_fn=_comparison_key,
    )


def recover_certifications(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Preserve optimizer certifications and append missing source-backed certifications."""

    return _recover_list_field(
        base_values=_get_string_list(optimizer_payload, "certifications"),
        source_values=_filter_recoverable_certification_values(phase2_input.certification_candidates),
        parser_values=_filter_recoverable_certification_values(_get_string_list(parser_payload, "certifications")),
        field_name="certifications",
        comparison_key_fn=_certification_comparison_key,
    )


def reconcile_technical_skills(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Backward-compatible alias for coverage-mode skill recovery."""

    return recover_technical_skills(phase2_input, parser_payload, optimizer_payload)


def reconcile_soft_skills(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Backward-compatible alias for coverage-mode soft-skill recovery."""

    return recover_soft_skills(phase2_input, parser_payload, optimizer_payload)


def reconcile_languages(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Backward-compatible alias for coverage-mode language recovery."""

    return recover_languages(phase2_input, parser_payload, optimizer_payload)


def reconcile_certifications(
    phase2_input: Phase2Input, parser_payload: Dict[str, Any], optimizer_payload: Dict[str, Any]
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Backward-compatible alias for coverage-mode certification recovery."""

    return recover_certifications(phase2_input, parser_payload, optimizer_payload)


def _recover_list_field(
    base_values: List[str],
    source_values: List[str],
    parser_values: List[str],
    field_name: str,
    comparison_key_fn,
) -> Tuple[List[str], Dict[str, List[str]]]:
    final_values: List[str] = []
    seen = set()
    audit = {"recovered_items": [], "recovered_fields": [], "notes": []}

    for value in base_values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        key = comparison_key_fn(normalized)
        if key in seen:
            continue
        seen.add(key)
        final_values.append(normalized)

    for value in source_values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        key = comparison_key_fn(normalized)
        if key in seen:
            continue
        seen.add(key)
        final_values.append(normalized)
        audit["recovered_items"].append("{0}:{1}".format(field_name, normalized))
        audit["notes"].append("Recovered {0}: {1} from source evidence".format(field_name.rstrip("s"), normalized))

    for value in parser_values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        key = comparison_key_fn(normalized)
        if key in seen:
            continue
        seen.add(key)
        final_values.append(normalized)
        audit["recovered_items"].append("{0}:{1}".format(field_name, normalized))
        audit["notes"].append("Recovered {0}: {1} from parser evidence".format(field_name.rstrip("s"), normalized))

    return final_values, audit


def _comparison_key(value: str) -> str:
    return normalize_skill(value).lower()


def _technical_skill_comparison_key(value: str) -> str:
    normalized = normalize_skill(value).lower()
    normalized = normalized.replace("(unit testing)", "").strip()
    normalized = normalized.replace("(saa-c03 certified)", "").strip()
    normalized = normalized.replace("(certified)", "").strip()
    normalized = normalized.replace("environment configuration & deployment support", "deployment support")
    normalized = normalized.replace("java script", "javascript")
    normalized = normalized.replace("type script", "typescript")
    normalized = normalized.replace("fast api", "fastapi")
    normalized = normalized.replace("react.js", "react")
    normalized = normalized.replace("node.js", "node")
    normalized = normalized.replace("sqlserver", "sql server")
    normalized = normalized.replace("sqlite", "sqlite")
    normalized = normalized.replace("asp.net", "aspdotnet")
    normalized = normalized.replace(".net", "dotnet")
    normalized = re.sub(r"\s*/\s*", "/", normalized)
    normalized = re.sub(r"\s*,\s*", ",", normalized)
    normalized = normalized.replace(" / ", "/")
    normalized = normalized.replace(", ", ",")
    normalized = normalized.replace("visual studio/ vs code", "visual studio/vs code")
    normalized = normalized.replace("visual studio / vs code", "visual studio/vs code")
    normalized = normalized.replace("sql/sqlite", "sql,sqlite")
    normalized = normalized.replace("sql / sqlite", "sql,sqlite")
    normalized = normalized.replace("c#/dotnet core", "c#/dotnet core")
    normalized = normalized.replace("c# / dotnet core", "c#/dotnet core")
    normalized = " ".join(normalized.split())
    return normalized


def _certification_comparison_key(value: str) -> str:
    normalized = _normalize_recoverable_certification_value(value).lower()
    normalized = re.sub(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}\s*[-–]?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)?[a-z]*\s*\d{0,4}",
        "",
        normalized,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip(" ,;|.-")
    return normalized


def _filter_recoverable_skill_values(values: List[str]) -> List[str]:
    filtered: List[str] = []
    for value in values:
        normalized = _normalize_recoverable_skill_value(value)
        if not normalized:
            continue
        if (
            _is_section_wrapped_skill(normalized)
            or _is_non_atomic_skill_value(normalized)
            or not _looks_like_technical_skill(normalized)
        ):
            continue
        filtered.append(normalized)
    return filtered


def _is_section_wrapped_skill(value: str) -> bool:
    lowered = value.lower()
    if ":" in value:
        prefix = lowered.split(":", 1)[0].strip()
        if prefix in {
            "backend",
            "programming languages",
            "frontend development",
            "backend development",
            "databases",
            "testing & tools",
            "testing and tools",
            "cloud & devops",
            "cloud and devops",
            "concepts",
            "web",
            "web development",
            "mobile",
            "tools",
            "tools & practices",
            "developer tools",
            "version control",
            "soft skills",
            "spoken languages",
            "core cs",
            "backend technologies",
            "frameworks & libraries",
            "languages & frameworks",
            "software design",
            "state management",
            "networking",
            "testing",
            "problem solving",
            "data analysis tools",
            "cumulative gpa",
            "ai & machine learning",
            "ci/cd & deployment",
            "testing/devops",
            "engineering & it",
            "ai & automation",
            "sales & communication",
            "digital finance & marketing",
        }:
            return True
    return False


def _is_non_atomic_skill_value(value: str) -> bool:
    lowered = value.lower().strip(" .")
    if lowered in _SECTION_LABELS:
        return True
    if value in {"▪", "●", "•"}:
        return True
    if lowered in _SKILL_FRAGMENT_BLACKLIST:
        return True
    if ", " in value and len([part for part in value.split(",") if part.strip()]) > 1:
        return True
    if value.count("(") != value.count(")"):
        return True
    if value.endswith(")") and "(" not in value:
        return True
    if any(dash in value for dash in {"—", "–"}) and any(
        token in lowered
        for token in {
            "technologies",
            "technology",
            "tools",
            "backend",
            "frontend",
            "frameworks",
            "framework",
            "languages",
            "skills",
        }
    ):
        return True
    if lowered.startswith(("and ", "with ", "on ", "using ", "maintaining ", "best practices", "worked on ")):
        return True
    if any(token in lowered for token in {"soft skills", "languages", "certificates", "certifications", "volunteering"}):
        return True
    if lowered in _COMMON_SOFT_SKILLS:
        return True
    return False


def _looks_like_technical_skill(value: str) -> bool:
    lowered = value.lower()
    word_count = len(value.split())
    if word_count <= 3:
        return True
    if any(keyword in lowered for keyword in _TECHNICAL_KEYWORDS):
        return True
    if re.search(r"\b[A-Z]{2,}\b", value):
        return True
    return False


def _normalize_recoverable_skill_value(value: str) -> str:
    normalized = normalize_text(value)
    normalized = normalized.strip(" ,;|")
    normalized = re.sub(r"[.]+$", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _filter_recoverable_language_values(values: List[str]) -> List[str]:
    filtered: List[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or _is_non_language_value(normalized):
            continue
        filtered.append(normalized)
    return filtered


def _extract_soft_skill_candidates(phase2_input: Phase2Input) -> List[str]:
    skills_text = phase2_input.canonical_sections.get("Skills", "")
    if not skills_text:
        return []

    candidates: List[str] = []
    normalized = skills_text.replace("\r\n", "\n").replace("\r", "\n")
    parts = [part.strip() for part in re.split(r"(?:^|\n)\s*[•●▪·]\s*", normalized) if part.strip()]
    if len(parts) <= 1:
        parts = [part.strip() for part in normalized.splitlines() if part.strip()]

    for part in parts:
        inline_parts = [segment.strip() for segment in re.split(r"\s+[•●▪·]\s+", part) if segment.strip()]
        if not inline_parts:
            inline_parts = [part]
        for inline_part in inline_parts:
            candidate = _normalize_recoverable_soft_skill_value(inline_part)
            if candidate:
                candidates.append(candidate)
    return _filter_recoverable_soft_skill_values(candidates)


def _filter_recoverable_soft_skill_values(values: List[str]) -> List[str]:
    filtered: List[str] = []
    for value in values:
        normalized = _normalize_recoverable_soft_skill_value(value)
        if not normalized or _is_non_soft_skill_value(normalized):
            continue
        filtered.append(normalized)
    return filtered


def _normalize_recoverable_soft_skill_value(value: str) -> str:
    normalized = normalize_text(value)
    normalized = re.sub(r"^[•●▪·-]\s*", "", normalized)
    normalized = normalized.strip(" ,;|")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _is_non_soft_skill_value(value: str) -> bool:
    lowered = value.lower().strip(" .")
    if lowered in _SECTION_LABELS:
        return True
    if ":" not in value:
        return lowered not in _COMMON_SOFT_SKILLS
    prefix = lowered.split(":", 1)[0].strip()
    if prefix not in {
        "technical problem solving",
        "collaborative development",
        "continuous learning",
        "personal traits",
        "communication",
        "leadership",
        "teamwork",
        "problem solving",
        "problem-solving",
        "adaptability",
        "critical thinking",
        "time management",
    }:
        return True
    suffix = lowered.split(":", 1)[1].strip()
    if not suffix or len(suffix.split()) < 3:
        return True
    return False


def _is_non_language_value(value: str) -> bool:
    lowered = value.lower().strip(" .")
    if lowered in _SECTION_LABELS:
        return True
    if ":" in value:
        return True
    if len(value.split()) == 1 and value.isupper() and len(value) > 3:
        return True
    if any(token in lowered for token in {"python", "java", "javascript", "react", "node", "sql", "docker", "git"}):
        return True
    return False


def _filter_recoverable_certification_values(values: List[str]) -> List[str]:
    filtered: List[str] = []
    for value in values:
        normalized = _normalize_recoverable_certification_value(value)
        if (
            not normalized
            or _is_non_certification_value(normalized)
            or not _looks_like_certification_value(normalized)
        ):
            continue
        filtered.append(normalized)
    return filtered


def _is_non_certification_value(value: str) -> bool:
    lowered = value.lower().strip(" .")
    if lowered in _SECTION_LABELS:
        return True
    if value in {"▪", "●", "•"}:
        return True
    if lowered in {"systems", "countries"}:
        return True
    if any(token in lowered for token in {"award", "awards", "ranked ", "scholarship", "competition"}):
        return True
    if re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|\d{4})\b", lowered) and not _has_certification_keyword(lowered):
        return True
    if any(
        token in lowered
        for token in {
            "extra-curricular",
            "extra curricular",
            "worked on",
            "identify ",
            "understand ",
            "and folders using",
            "networks",
            "contributed to",
            "automated ",
            "improving efficiency",
            "solution aimed",
        }
    ):
        return True
    if ":" in value and "certificate" not in lowered and "certification" not in lowered:
        return True
    if len(value.split()) > 12 and not _has_certification_keyword(lowered):
        return True
    return False


def _normalize_recoverable_certification_value(value: str) -> str:
    normalized = normalize_text(value).lstrip("•●▪- ").strip(" ,;|")
    normalized = re.sub(
        r"\b(completed|identify|understand|worked on|contributed to|automated)\b.*$",
        "",
        normalized,
        flags=re.IGNORECASE,
    ).strip(" ,;|.-")
    normalized = re.sub(
        r"\s+\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s*\d{4}\s*[-–]\s*\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s*\d{4}\b.*$",
        "",
        normalized,
        flags=re.IGNORECASE,
    ).strip(" ,;|.-")
    return normalized


def _has_certification_keyword(value: str) -> bool:
    return any(
        keyword in value
        for keyword in {
            "certificate",
            "certification",
            "certified",
            "academy",
            "ccna",
            "aws",
            "comptia",
            "cisco",
            "license",
            "credential",
            "route acadmey",
            "route academy",
        }
    )


def _looks_like_certification_value(value: str) -> bool:
    lowered = value.lower()
    if _has_certification_keyword(lowered):
        return True
    if any(token in lowered for token in {"ccna", "aws saa", "aws", "comptia", "pmp", "ielts", "toefl"}):
        return True
    if lowered in {"route acadmey", "route academy"}:
        return True
    if "fundamentals" in lowered and any(token in lowered for token in {"cisco", "cybersecurity"}):
        return True
    return False


_SECTION_LABELS = {
    "languages",
    "language",
    "skills",
    "technical skills",
    "technical skill",
    "core competencies",
    "competencies",
    "technologies",
    "certificates",
    "certifications",
    "training",
    "trainings",
    "courses",
    "projects",
    "experience",
    "education",
    "summary",
    "profile",
    "background",
    "volunteering",
    "technical concepts",
}

_COMMON_SOFT_SKILLS = {
    "teamwork",
    "leadership",
    "time management",
    "communication",
    "public speaking",
    "analytical thinking",
    "team player",
    "detail oriented",
    "critical thinking",
    "interpersonal intelligence",
    "problem solving",
    "problem-solving and critical thinking",
    "communication and presentation skills",
    "team collaboration and leadership",
    "networking fundamentals",
}

_SKILL_FRAGMENT_BLACKLIST = {
    "technical concepts",
    "technologies",
    "directory",
    "adaptability",
}

_TECHNICAL_KEYWORDS = {
    "api",
    "asp",
    "architecture",
    "algorithm",
    "android",
    "ansible",
    "authentication",
    "aws",
    "azure",
    "c#",
    "c++",
    "cloud",
    "compiler",
    "css",
    "database",
    "debugging",
    "devops",
    "dhcp",
    "dns",
    "docker",
    "entity framework",
    "express",
    "fastapi",
    "figma",
    "firebase",
    "flutter",
    "framework",
    "git",
    "github",
    "hibernate",
    "html",
    "java",
    "javascript",
    "jira",
    "jwt",
    "keras",
    "kotlin",
    "kubernetes",
    "langchain",
    "laravel",
    "linux",
    "machine learning",
    "microservices",
    "mongodb",
    "mysql",
    "net",
    "network",
    "next.js",
    "node",
    "oauth",
    "oracle",
    "phpunit",
    "postman",
    "postgresql",
    "problem solving",
    "python",
    "pytorch",
    "rabbitmq",
    "react",
    "redis",
    "rest",
    "scikit",
    "selenium",
    "server",
    "signalr",
    "sql",
    "spring",
    "stateful widget",
    "subnetting",
    "tailwind",
    "tensorflow",
    "terraform",
    "testing",
    "typescript",
    "unit testing",
    "visual studio",
    "widget",
    "windows",
    "yolo",
}


def _get_string_list(payload: Dict[str, Any], key: str) -> List[str]:
    value = payload.get(key)
    if value is None:
        return []
    if isinstance(value, str):
        normalized = normalize_text(value)
        return [normalized] if normalized else []
    if not isinstance(value, list):
        return []
    items: List[str] = []
    for item in value:
        normalized = normalize_text(str(item))
        if normalized:
            items.append(normalized)
    return items
