"""GET /registry: the skills, games and AI providers that drive the UI."""

from fastapi import APIRouter

from backend.registry.loader import load_registry
from backend.registry.models import Registry

router = APIRouter(tags=["registry"])


@router.get("/registry", response_model=Registry)
def get_registry() -> Registry:
    registry = load_registry()
    visible = [p for p in registry.providers if not p.hidden]
    # Courses carry the question bank and its answers: the UI reads GET /course instead.
    return registry.model_copy(update={"providers": visible, "courses": []})
