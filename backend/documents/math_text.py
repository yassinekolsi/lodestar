"""Boundaries that keep a LaTeX formula or fenced code block intact."""

import re

BLOCK = re.compile(
    r"```[\s\S]*?```|\$\$[\s\S]*?\$\$|(?<!\\)\$(?:\\.|[^$])*?\$|"
    r"\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)"
)


def safe_cut(text: str, cut: int) -> int:
    for match in BLOCK.finditer(text):
        if match.start() < cut < match.end():
            return match.start() if match.start() >= 120 else match.end()
    return cut
