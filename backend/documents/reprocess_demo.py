"""Replace local demo chapter extraction; quarantine old OCR before calling Gemini."""

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, insert, select, update

from backend.api.main import _memory
from backend.config import get_settings
from backend.contracts.events import LibraryChanged, LibraryPayload
from backend.db import tables as t
from backend.db.engine import get_async_engine
from backend.db.twin_store import append_event, user_scope
from backend.documents.import_demo import CHAPTERS
from backend.documents.ocr import Transcription, extract_document
from backend.llm.factory import LlmFactory
from backend.registry.loader import load_registry


async def run(directory: Path, probability_only: bool) -> None:
    settings = get_settings()
    engine = get_async_engine()
    registry = load_registry()
    factory = LlmFactory(registry, settings, engine)
    memory, _ = await _memory(settings)
    try:
        async with engine.connect() as conn:
            user_id = await conn.scalar(
                select(t.users.c.user_id).where(t.users.c.display_name == "Alex")
            )
        if user_id is None:
            raise ValueError("The demo student is missing.")
        # Quarantine all earlier probability OCR immediately, including pages not yet re-read.
        async with engine.begin() as conn:
            await conn.execute(
                update(t.documents)
                .where(
                    t.documents.c.user_id == user_id,
                    t.documents.c.filename.like("Chapitre %"),
                )
                .values(review_required=True, indexed=False)
            )
        for pattern, subject, chapter in CHAPTERS:
            if probability_only and subject != "Probability":
                continue
            file = next(directory.glob(pattern))  # noqa: ASYNC240 - local CLI input
            async with engine.connect() as conn:
                doc = (
                    await conn.execute(
                        select(t.documents).where(
                            t.documents.c.user_id == user_id, t.documents.c.filename == file.name
                        )
                    )
                ).one()
            data = file.read_bytes()
            async with engine.begin() as conn:
                await conn.execute(
                    update(t.documents)
                    .where(t.documents.c.doc_id == doc.doc_id)
                    .values(source_pdf=data, review_required=True, indexed=False)
                )
            if memory:
                await memory.delete_document(user_id, doc.doc_id)
            print(f"Reading {subject}, {chapter} with Gemini PDF vision...", flush=True)
            cache = (doc.extraction or {}).get("ocr_cache", {})

            async def checkpoint(
                index: int, result: Transcription, cache: dict[str, Any] = cache, doc: Any = doc
            ) -> None:
                cache[str(index)] = result.model_dump()
                async with engine.begin() as conn:
                    await conn.execute(
                        update(t.documents)
                        .where(t.documents.c.doc_id == doc.doc_id)
                        .values(extraction={**(doc.extraction or {}), "ocr_cache": cache})
                    )
                print(
                    f"  Page {index + 1} read; uncertainties: {len(result.uncertainties)}",
                    flush=True,
                )

            extracted = await extract_document(
                data,
                file.name,
                registry,
                factory,
                user_id,
                force_gemini=subject == "Probability",
                cached={int(i): Transcription.model_validate(v) for i, v in cache.items()},
                on_page=checkpoint,
            )
            rows = [
                {
                    "passage_id": uuid4(),
                    "user_id": user_id,
                    "doc_id": doc.doc_id,
                    "page": p.page,
                    "position": p.position,
                    "text": p.text,
                    "concepts": p.concepts,
                }
                for p in extracted.passages
            ]
            async with engine.begin() as conn:
                await user_scope(conn, user_id)
                await conn.execute(
                    delete(t.document_passages).where(t.document_passages.c.doc_id == doc.doc_id)
                )
                await conn.execute(insert(t.document_passages), rows)
                await conn.execute(
                    update(t.documents)
                    .where(t.documents.c.doc_id == doc.doc_id)
                    .values(
                        title=chapter,
                        passages=len(rows),
                        concepts=extracted.concepts(),
                        extraction={
                            "method": extracted.method,
                            "pages": extracted.page_texts,
                            "warnings": extracted.warnings,
                        },
                        review_required=extracted.review_required,
                    )
                )
                await append_event(
                    conn,
                    LibraryChanged(
                        user_id=user_id,
                        ts=datetime.now(UTC),
                        payload=LibraryPayload(action="document_uploaded", doc_id=doc.doc_id),
                    ),
                )
            print(
                f"Saved {extracted.pages} pages, {len(rows)} passages; "
                f"flagged pages: {sorted(extracted.warnings)}; review required: "
                f"{extracted.review_required}",
                flush=True,
            )
    finally:
        if memory:
            await memory._client.close()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--probability-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.directory, args.probability_only))


if __name__ == "__main__":
    main()
