import json
from functools import lru_cache
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


@lru_cache(maxsize=1)
def load_all() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(TEMPLATES_DIR.glob("*.json"))]


def load_one(template_id: str) -> dict | None:
    for tpl in load_all():
        if tpl.get("id") == template_id:
            return tpl
    return None
