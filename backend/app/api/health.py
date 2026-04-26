import httpx
from fastapi import APIRouter

from app.config import settings
from app.db import weights_repo

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    ollama_ok = _ping_ollama()
    return {
        "status": "ok",
        "ollama": "connected" if ollama_ok else "unreachable",
        "default_model": settings.default_llm_model,
        "current_weights": weights_repo.current_weights(),
    }


def _ping_ollama() -> bool:
    try:
        r = httpx.get(f"{settings.ollama_host}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False
