"""Boundaries that keep a LaTeX formula or fenced code block intact."""

import re

BLOCK = re.compile(
    r"```[\s\S]*?```|\$\$[\s\S]*?\$\$|(?<!\\)\$(?:\\.|[^$])*?\$|"
    r"\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|"
    r"^\|[^\n]+\|[ \t]*\n\|[ :|-]+\|[ \t]*(?:\n\|[^\n]+\|[ \t]*)+",
    re.M,
)

MIXED_MATH = "Mixed inline and display math delimiters. Compare this page with the original."
UNCLOSED_MATH = "An unclosed math delimiter needs review against the original."
SIZING_MATH = "Unmatched formula sizing commands need review against the original."
BRACES_MATH = "Unbalanced formula braces need review against the original."
FORMATTING_WARNINGS = frozenset((MIXED_MATH, UNCLOSED_MATH, SIZING_MATH, BRACES_MATH))


def safe_cut(text: str, cut: int) -> int:
    for match in BLOCK.finditer(text):
        if match.start() < cut < match.end():
            return match.start() if match.start() >= 120 else match.end()
    return cut


def _repair_tex(text: str) -> str:
    """Repair presentation syntax only: never change a symbol, number or operator."""
    if len(re.findall(r"\\left\b", text)) != len(re.findall(r"\\right\b", text)):
        text = re.sub(r"\\(?:left|right)\s*\.", "", text)
        text = re.sub(r"\\(?:left|right)\b", "", text)
    depth = 0
    output: list[str] = []
    start = 0
    for match in re.finditer(r"(?<!\\)[{}]", text):
        output.append(text[start : match.start()])
        start = match.end()
        if match.group() == "{":
            depth += 1
            output.append("{")
        elif depth:
            depth -= 1
            output.append("}")
    output.append(text[start:])
    return "".join(output) + "}" * depth


def repair_math(text: str) -> str:
    """Normalize OCR math wrappers without asking the student to edit LaTeX.

    Source content is retained; only delimiters, grouping braces and sizing commands are
    repaired. Code is untouched. Unsupported TeX can still be saved and shown as source text.
    """
    output: list[str] = []
    for part in re.split(r"(```[\s\S]*?```)", text):
        if part.startswith("```"):
            output.append(part)
            continue
        part = re.sub(
            r"\\\[([\s\S]*?)(?:\\\]|$)|\\\(([\s\S]*?)(?:\\\)|$)",
            lambda m: (
                (r"\[" + _repair_tex(m[1]) + r"\]")
                if m[1] is not None
                else (r"\(" + _repair_tex(m[2]) + r"\)")
            ),
            part,
        )
        start = 0
        opened: str | None = None
        for match in re.finditer(r"(?<!\\)\${1,2}", part):
            if opened is None:
                output.extend((part[start : match.start()], match.group()))
                opened = match.group()
            else:
                output.extend((_repair_tex(part[start : match.start()]), opened))
                opened = None
            start = match.end()
        output.append(_repair_tex(part[start:]) + opened if opened else part[start:])
    return "".join(output)


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
            return [MIXED_MATH]
    if opened:
        return [UNCLOSED_MATH]
    for match in BLOCK.finditer(text):
        if match.group().startswith("|"):
            continue  # A Markdown table is not itself a TeX formula.
        if len(re.findall(r"\\left\b", match.group())) != len(
            re.findall(r"\\right\b", match.group())
        ):
            return [SIZING_MATH]
        depth = 0
        for brace in re.finditer(r"(?<!\\)[{}]", match.group()):
            depth += 1 if brace.group() == "{" else -1
            if depth < 0:
                return [BRACES_MATH]
        if depth:
            return [BRACES_MATH]
    return []
