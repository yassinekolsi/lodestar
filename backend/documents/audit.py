"""Export private OCR review artifacts and representative original page images locally."""

import argparse
import subprocess
from pathlib import Path

from sqlalchemy import select

from backend.db import tables as t
from backend.db.engine import get_engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--no-images", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with get_engine().connect() as conn:
        rows = conn.execute(select(t.documents).where(t.documents.c.filename.like("Chapitre %")))
        for doc in rows:
            index = doc.filename.split()[1]
            extraction = doc.extraction or {}
            pages = extraction.get("pages", [])
            markdown = f"# Probability chapter {index}\n\n"
            for i, page in enumerate(pages, 1):
                markdown += f"## Page {i}\n\n{page}\n\n"
            (args.output / f"chapter-{index}.md").write_text(markdown, encoding="utf-8")
            selected = {1, 2, doc.pages, *(int(p) for p in extraction.get("warnings", {}))}
            if index == "2":
                selected |= {5, 6, 7}
            if args.no_images:
                selected = set()
            for page in sorted(selected):
                prefix = args.output / f"chapter-{index}-page-{page}"
                subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        str(page),
                        "-l",
                        str(page),
                        "-scale-to",
                        "1800",
                        "-singlefile",
                        "-png",
                        str(args.directory / doc.filename),
                        str(prefix),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
            print(
                f"Chapter {index}: {len(pages)}/{doc.pages} pages, "
                f"flagged pages {list(extraction.get('warnings', {}))}"
            )


if __name__ == "__main__":
    main()
