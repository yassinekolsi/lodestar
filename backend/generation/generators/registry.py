"""Generators by game id. A game listed here needs generated content in its exercise spec.

Course exercises don't: their questions come from the course (backend/agent/learning.py). The
pipeline stays for content an LLM writes and code checks, such as questions drafted from an
uploaded course (docs/plan/19, "What's next")."""

from backend.generation.generators.base import Generator

GENERATORS: dict[str, Generator] = {}
