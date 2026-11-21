"""Boundaries that keep a LaTeX formula or fenced code block intact."""

import re

BLOCK = re.compile(
    r"```[\s\S]*?```|\$\$[\s\S]*?\$\$|(?<!\\)\$(?:\\.|[^$])*?\$|"
    r"\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|"
    r"^\|[^\n]+\|[ \t]*\n\|[ :|-]+\|[ \t]*(?:\n\|[^\n]+\|[ \t]*)+",
    re.M,
)


def safe_cut(text: str, cut: int) -> int:
    for match in BLOCK.finditer(text):
        if match.start() < cut < match.end():
            return match.start() if match.start() >= 120 else match.end()
    return cut


def math_issues(text: str) -> list[str]:
    """Conservative syntax checks; these never assert that a transcription is correct."""
    text = re.sub(r"```[\s\S]*?```", "", text)
    opened: str | None = None
    for match in re.finditer(r"(?<!\\)\${1,2}", text):
        token = match.group()
        if opened is None:
            opened = token
        elif opened == token:
            opened = None
        else:
            return [
                "Mixed inline and display math delimiters. Compare this page with the original."
            ]
    if opened:
        return ["An unclosed math delimiter needs review against the original."]
    for match in BLOCK.finditer(text):
        if len(re.findall(r"\\left\b", match.group())) != len(
            re.findall(r"\\right\b", match.group())
        ):
            return ["Unmatched formula sizing commands need review against the original."]
        depth = 0
        for brace in re.finditer(r"(?<!\\)[{}]", match.group()):
            depth += 1 if brace.group() == "{" else -1
            if depth < 0:
                return ["Unbalanced formula braces need review against the original."]
        if depth:
            return ["Unbalanced formula braces need review against the original."]
    return []
