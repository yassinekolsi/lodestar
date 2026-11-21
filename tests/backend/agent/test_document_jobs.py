"""A small host reads one queued document at a time, with PDFs stored in Postgres."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.documents import jobs, library


async def test_reading_is_serial_even_when_uploads_arrive_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = 0
    peak = 0

    async def extract(*args: object) -> None:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1

    monkeypatch.setattr(jobs, "_read", extract)
    await asyncio.gather(
        *(jobs.read(None, None, uuid4(), uuid4(), b"notes", "notes.txt", False) for _ in range(3))
    )
    assert peak == 1


async def test_queued_pdf_does_not_retain_upload_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    read = AsyncMock()
    monkeypatch.setattr(jobs, "read", read)
    services = SimpleNamespace()
    user, doc = uuid4(), uuid4()
    await jobs.launch(services, None, user, doc, b"large original", "chapter.PDF", False)
    assert read.call_args.args[4] is None


async def test_listing_selects_metadata_without_pdf_or_extracted_pages() -> None:
    execute = AsyncMock(return_value=[])
    await library.documents(SimpleNamespace(execute=execute), uuid4())
    selected = set(execute.call_args.args[0].selected_columns.keys())
    assert "source_pdf" not in selected
    assert "extraction" not in selected
    assert "extraction_method" in selected
