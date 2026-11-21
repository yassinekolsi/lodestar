"""From an uploaded file to passages Lodestar can search and cite (docs/plan/20).

- Text per page: PDF pages through pypdf; a .txt or .md file is one page per form feed.
- Cleaning: words split by a hyphen at a line end are joined, runs of spaces collapsed, lines that
  are only a page number dropped.
- Passages: paragraphs grouped up to about PASSAGE_CHARS characters, never across a page, so every
  passage keeps the page it can be cited by.
- Concepts: each passage is tagged with the course concepts it names (the same words the intent
  router uses: the concept names and their aliases), so a question about Bayes can be answered from
  the student's own pages on Bayes.

Pure functions, no database.
"""

import io
import re
from dataclasses import dataclass, field
from pathlib import PurePath

from pypdf import PdfReader

from backend.agent.intents import skills_in
from backend.documents.math_text import BLOCK, safe_cut
from backend.registry.models import Registry

PASSAGE_CHARS = 650
MIN_PASSAGE_CHARS = 120
MAX_BYTES = 25 * 1024 * 1024
MAX_PAGES = 400
KINDS = (".pdf", ".txt", ".md")


class UnreadableDocument(ValueError):
    """The file isn't a PDF or text file Lodestar can read, or has no text in it."""


@dataclass
class Passage:
    page: int
    position: int
    text: str
    concepts: list[str] = field(default_factory=list)


@dataclass
class Extracted:
    title: str
    pages: int
    passages: list[Passage]
    page_texts: list[str] = field(default_factory=list)
    method: str = "text"
    warnings: dict[str, list[str]] = field(default_factory=dict)
    review_required: bool = False

    def concepts(self) -> dict[str, list[int]]:
        """Concept -> the pages that mention it, in order."""
        out: dict[str, list[int]] = {}
        for p in self.passages:
            for c in p.concepts:
                pages = out.setdefault(c, [])
                if p.page not in pages:
                    pages.append(p.page)
        return out


def _clean_prose(text: str) -> str:
    text = text.replace("\r", "\n").replace("­", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # hyphenated across a line end
    lines = [ln.strip() for ln in text.split("\n")]
    out: list[str] = []
    for ln in lines:
        if re.fullmatch(r"(page\s*)?\d{1,4}(\s*/\s*\d+)?", ln, re.I):
            continue
        if not ln:
            if out and out[-1]:
                out.append("")
            continue
        # Keep short headings and code on their own lines. Blank lines delimit paragraphs.
        if (
            out
            and len(out[-1]) > 85
            and not re.search(r"[.!?:;{}]$", out[-1])
            and not re.match(r"^[-•*\d#]|^(class|void|int|#include)\b", ln)
        ):
            out[-1] = f"{out[-1]} {ln}"
        else:
            out.append(ln)
    return "\n".join(re.sub(r"[ \t]+", " ", ln) for ln in out)


def clean(text: str) -> str:
    def prose(value: str) -> str:
        if not value.strip():
            return value
        before = re.match(r"\s*", value)
        after = re.search(r"\s*$", value)
        return (
            (before.group() if before else "")
            + _clean_prose(value).strip()
            + (after.group() if after else "")
        )

    parts: list[str] = []
    start = 0
    for match in BLOCK.finditer(text):
        parts.extend([prose(text[start : match.start()]), match.group()])
        start = match.end()
    parts.append(prose(text[start:]))
    return "".join(parts)


def pages_of(
    data: bytes, filename: str, *, allow_scans: bool = False
) -> tuple[list[str], str | None]:
    """The text of each page, and the title stored in the file if any."""
    if len(data) > MAX_BYTES:
        raise UnreadableDocument("That file is over 25 MB.")
    kind = PurePath(filename).suffix.lower()
    if kind not in KINDS:
        raise UnreadableDocument("Lodestar reads PDF, .txt and .md files.")
    if kind == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            if len(reader.pages) > MAX_PAGES:
                raise UnreadableDocument("Split this PDF into files of at most 400 pages.")
            pages = [(p.extract_text() or "") for p in reader.pages]
            meta = reader.metadata
            title = str(meta.title).strip() if meta and meta.title else None
        except UnreadableDocument:
            raise
        except Exception as exc:  # pypdf raises many kinds of errors on broken files
            raise UnreadableDocument("That PDF couldn't be read.") from exc
        if not allow_scans and scanned_pages(pages):
            raise UnreadableDocument("This PDF needs Gemini OCR. Upload it through Documents.")
    else:
        text = data.decode("utf-8", errors="replace")
        pages = text.split("\f") if "\f" in text else [text]
        title = None
    if not allow_scans and not any(p.strip() for p in pages):
        raise UnreadableDocument(
            "No text found in that file. If it's a scan, export it with text (OCR) first."
        )
    return pages, title


def scanned_pages(pages: list[str]) -> list[int]:
    return [
        i for i, p in enumerate(pages) if len(re.sub(r"CamScanner|\s|\d", "", p, flags=re.I)) < 25
    ]


def split_passages(pages: list[str]) -> list[Passage]:
    passages: list[Passage] = []
    for number, raw in enumerate(pages, start=1):
        remaining = clean(raw).strip()
        while len(remaining) > PASSAGE_CHARS:
            window = remaining[:PASSAGE_CHARS]
            # Prefer a section/paragraph boundary, then a sentence, then a word.
            cut = window.rfind("\n", 400)
            if cut < 0:
                ends = list(re.finditer(r"[.!?]\s", window[400:]))
                cut = 400 + ends[-1].end() if ends else window.rfind(" ", 400)
            if cut < 0:
                cut = PASSAGE_CHARS  # code or a long formula without whitespace
            cut = safe_cut(remaining, cut)
            passages.append(Passage(number, len(passages), remaining[:cut].strip()))
            remaining = remaining[cut:].strip()
        if remaining:
            passages.append(Passage(number, len(passages), remaining))
    return passages


def title_of(filename: str, stored: str | None, pages: list[str]) -> str:
    if stored and len(stored) > 3 and not stored.lower().startswith(("microsoft", "untitled")):
        return stored[:120]
    for line in pages[0].splitlines():
        line = line.strip()
        if re.search(r"@|author|enseignant|année|filière|^dr\.|^prof", line, re.I):
            continue
        if 3 < len(line) <= 90:
            return line
    return PurePath(filename).stem.replace("_", " ").replace("-", " ")[:120]


def extract(data: bytes, filename: str, registry: Registry) -> Extracted:
    pages, stored = pages_of(data, filename)
    passages = split_passages(pages)
    for p in passages:
        p.concepts = skills_in(p.text, registry)
    return Extracted(title_of(filename, stored, pages), len(pages), passages, page_texts=pages)
