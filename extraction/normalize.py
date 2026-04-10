"""Lightweight normalization helpers for extracted PDF text."""

import re
from typing import List

_LINE_ENDINGS_RE = re.compile(r"\r\n?|\u2028|\u2029")
_SPACE_RE = re.compile(r"[^\S\n]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_BULLET_PREFIXES = ("- ", "* ", "• ", "▪ ", "◦ ", "– ")


def normalize_text(text: str) -> str:
    """Normalize extracted text without aggressively rewriting content.

    The function intentionally preserves line boundaries because they often
    carry semantic meaning in resumes, such as bullets, headings, or short
    one-line role descriptions.
    """

    if not text:
        return ""

    normalized = _LINE_ENDINGS_RE.sub("\n", text)
    lines: List[str] = []

    for raw_line in normalized.split("\n"):
        line = _SPACE_RE.sub(" ", raw_line).strip()
        if not line:
            lines.append("")
            continue

        # Preserve common bullet prefixes with a single following space.
        for bullet in _BULLET_PREFIXES:
            if line.startswith(bullet.strip()):
                content = line[len(bullet.strip()) :].strip()
                line = f"{bullet.strip()} {content}" if content else bullet.strip()
                break

        lines.append(line)

    normalized = "\n".join(lines)
    normalized = _BLANK_LINES_RE.sub("\n\n", normalized)
    return normalized.strip()
