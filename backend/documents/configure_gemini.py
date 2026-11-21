"""Explicit local demo setup using the operator-supplied GEMINI_API_KEY environment variable."""

import asyncio

from sqlalchemy import select

from backend.config import get_settings
from backend.db import tables as t
from backend.db.consent_store import set_consent
from backend.db.engine import get_async_engine
from backend.llm.factory import LlmFactory
from backend.registry.loader import load_registry


async def main() -> None:
    engine = get_async_engine()
    registry = load_registry()
    try:
        async with engine.begin() as conn:
            user_id = await conn.scalar(
                select(t.users.c.user_id).where(t.users.c.display_name == "Alex")
            )
            if user_id is None:
                raise ValueError("Create the demo student before configuring Gemini.")
            await set_consent(conn, user_id, registry.consent, "cloud_ai", True)
        factory = LlmFactory(registry, get_settings(), engine)
        models = await factory.import_gemini_environment(user_id)
        print("Available Flash models:", [m for m in models if "flash" in m])
        print("Requested OCR model available:", "gemini-3.5-flash-lite" in models)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
