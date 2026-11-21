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
from backend.registry.models import Registry

PASSAGE_CHARS = 900
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

    def concepts(self) -> dict[str, list[int]]:
        """Concept -> the pages that mention it, in order."""
        out: dict[str, list[int]] = {}
        for p in self.passages:
            for c in p.concepts:
                pages = out.setdefault(c, [])
                if p.page not in pages:
                    pages.append(p.page)
        return out


def clean(text: str) -> str:
    text = text.replace("\r", "\n").replace("­", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # hyphenated across a line end
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [
        ln for ln in lines if ln and not re.fullmatch(r"(page\s*)?\d{1,4}(\s*/\s*\d+)?", ln, re.I)
    ]
    out: list[str] = []
    for ln in lines:
        # A line ending without punctuation usually continues on the next one.
        if out and not re.search(r"[.!?:;]$", out[-1]) and not re.match(r"^[-•*\d]", ln):
            out[-1] = f"{out[-1]} {ln}"
        else:
            out.append(ln)
    return "\n".join(re.sub(r"[ \t]+", " ", ln) for ln in out)


def pages_of(data: bytes, filename: str) -> tuple[list[str], str | None]:
    """The text of each page, and the title stored in the file if any."""
    if len(data) > MAX_BYTES:
        raise UnreadableDocument("That file is over 25 MB.")
    kind = PurePath(filename).suffix.lower()
    if kind not in KINDS:
        raise UnreadableDocument("Lodestar reads PDF, .txt and .md files.")
    if kind == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [(p.extract_text() or "") for p in reader.pages[:MAX_PAGES]]
            meta = reader.metadata
            title = str(meta.title).strip() if meta and meta.title else None
        except Exception as exc:  # pypdf raises many kinds of errors on broken files
            raise UnreadableDocument("That PDF couldn't be read.") from exc
    else:
        text = data.decode("utf-8", errors="replace")
        pages = text.split("\f") if "\f" in text else [text]
        title = None
    if not any(p.strip() for p in pages):
        raise UnreadableDocument(
            "No text found in that file. If it's a scan, export it with text (OCR) first."
        )
    return pages, title


def split_passages(pages: list[str]) -> list[Passage]:
    passages: list[Passage] = []
    for number, raw in enumerate(pages, start=1):
        paragraphs = [p.strip() for p in clean(raw).split("\n") if p.strip()]
        current = ""
        for para in paragraphs:
            if current and len(current) + len(para) + 1 > PASSAGE_CHARS:
                passages.append(Passage(number, len(passages), current))
                current = ""
            if len(para) > PASSAGE_CHARS:  # a very long paragraph: cut at sentence ends
                for sentence in re.split(r"(?<=[.!?])\s+", para):
                    if current and len(current) + len(sentence) + 1 > PASSAGE_CHARS:
                        passages.append(Passage(number, len(passages), current))
                        current = ""
                    current = f"{current} {sentence}".strip()
            else:
                current = f"{current}\n{para}".strip()
        if current:
            # A short tail joins the previous passage of the same page when there is one.
            last = passages[-1] if passages else None
            if len(current) < MIN_PASSAGE_CHARS and last is not None and last.page == number:
                last.text = f"{last.text}\n{current}"
            else:
                passages.append(Passage(number, len(passages), current))
    return passages


def title_of(filename: str, stored: str | None, pages: list[str]) -> str:
    if stored and len(stored) > 3 and not stored.lower().startswith(("microsoft", "untitled")):
        return stored[:120]
    for line in clean(pages[0]).split("\n"):
        if 3 < len(line) <= 90:
            return line
    return PurePath(filename).stem.replace("_", " ").replace("-", " ")[:120]


def extract(data: bytes, filename: str, registry: Registry) -> Extracted:
    pages, stored = pages_of(data, filename)
    passages = split_passages(pages)
    for p in passages:
        p.concepts = skills_in(p.text, registry)
    return Extracted(title_of(filename, stored, pages), len(pages), passages)
