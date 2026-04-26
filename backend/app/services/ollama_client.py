import json
import re

import httpx

from app.config import settings


class OllamaClient:
    def __init__(self, host: str | None = None, model: str | None = None) -> None:
        self.host = host or settings.ollama_host
        self.model = model or settings.default_llm_model

    async def generate_json(self, prompt: str, temperature: float = 0.2, timeout: float = 120.0) -> dict:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature},
                    "format": "json",
                },
            )
            r.raise_for_status()
            data = r.json()
        raw = data.get("response", "")
        return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if not m:
            raise ValueError(f"no JSON object in LLM response: {raw[:200]}")
        return json.loads(m.group(0))
