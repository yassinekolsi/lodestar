"""OCR presentation repairs preserve formulas and leave C++ source alone."""

import pytest

from backend.documents.math_text import math_issues, repair_math


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (r"$$P(A)=\frac{1}{4$", r"$$P(A)=\frac{1}{4}$$"),
        (r"$P(A)=\frac{1}{4}}$", r"$P(A)=\frac{1}{4}$"),
        (r"$\left\{A,B\}$", r"$\{A,B\}$"),
        (r"$\left. P(A)=0.5$", r"$ P(A)=0.5$"),
        (
            r"$A\cap C=\{F,F\}\Rightarrow P(A\cap C)=\frac14$",
            r"$A\cap C=\{F,F\}\Rightarrow P(A\cap C)=\frac14$",
        ),
        (
            '```cpp\nstd::string s = "$"; if (x) {\n```',
            '```cpp\nstd::string s = "$"; if (x) {\n```',
        ),
    ],
)
def test_presentation_repairs_are_automatic_and_idempotent(source: str, expected: str) -> None:
    assert repair_math(source) == expected
    assert repair_math(expected) == expected
    assert not math_issues(expected)
