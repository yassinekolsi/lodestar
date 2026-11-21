"""Import the seven locally supplied chapters into the demo student's library.

Run inside the dev container: python -m backend.documents.import_demo /src
The source PDFs remain local; this command does not commit or publish course material.
"""

import argparse
from pathlib import Path

import httpx

CHAPTERS = (
    ("Cours 1-*.pdf", "C++", "Chapter 1: C++ foundations"),
    ("Cours 2-*.pdf", "C++", "Chapter 2: Standard Template Library"),
    ("Cours 3-*.pdf", "C++", "Chapter 3: Operator overloading"),
    ("Cours 4-*.pdf", "C++", "Chapter 4: File handling"),
    ("Chapitre 1*.pdf", "Probability", "Chapter 1"),
    ("Chapitre 2*.pdf", "Probability", "Chapter 2"),
    ("Chapitre 3*.pdf", "Probability", "Chapter 3"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=900) as client:
        response = client.post("/demo")
        response.raise_for_status()
        client.headers["Authorization"] = f"Bearer {response.json()['token']}"
        response = client.get("/subjects")
        response.raise_for_status()
        subjects = {s["name"]: s["subject_id"] for s in response.json()}
        response = client.get("/documents")
        response.raise_for_status()
        existing = {d["filename"] for d in response.json()}
        for pattern, subject, chapter in CHAPTERS:
            files = list(args.directory.glob(pattern))
            if len(files) != 1:
                raise SystemExit(f"Expected one local PDF matching {pattern}")
            file = files[0]
            if file.name in existing:
                print(f"Already imported: {chapter}", flush=True)
                continue
            if subject not in subjects:
                response = client.post("/subjects", json={"name": subject})
                response.raise_for_status()
                subjects[subject] = response.json()["subject_id"]
            print(f"Reading {subject}, {chapter}...", flush=True)
            with file.open("rb") as stream:
                response = client.post(
                    "/documents",
                    files={"file": (file.name, stream, "application/pdf")},
                    data={"subject_id": subjects[subject], "chapter": chapter},
                )
            if response.is_error:
                raise SystemExit(f"Import failed ({response.status_code}): {response.text[:300]}")
            doc = response.json()
            print(
                f"Saved: {doc['pages']} pages, {doc['passages']} passages; "
                f"searchable={doc['searchable']}",
                flush=True,
            )


if __name__ == "__main__":
    main()
