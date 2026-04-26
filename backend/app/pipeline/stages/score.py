from dataclasses import dataclass
from typing import Optional

from app.models.job import ClipCandidate
from app.pipeline.signals.fusion import Peak
from app.pipeline.stages.asr import AsrResult
from app.services.ollama_client import OllamaClient

PROMPT_TEMPLATE = """역할: 당신은 한국 예능 숏츠 편집자이다.
아래 전체 자막과 오디오가 주목한 지점을 참고해 15~59초 길이의 재미있는 구간 {k}개를 고른다.

[전체 자막 — 단어 단위 타임스탬프 (초)]
{transcript_block}

[오디오 신호가 주목한 지점]
{peaks_block}

[사용자 과거 선호 예시]
{fewshot_block}

[제약]
- 길이 15~59초, 구간끼리 최소 30초 간격
- 말 중간에서 시작/끝 금지 (단어 경계에 맞춤)

[출력 — JSON 객체만]
{{
  "clips": [
    {{"start": <초>, "end": <초>, "title": "<18자 이내>", "reason": "<한 문장>", "score": <0~10>}}
  ]
}}
"""


@dataclass
class ScoreConfig:
    k: int = 3
    max_words_in_prompt: int = 1500
    peak_window_s: float = 90.0   # words ±90s around each peak


def _format_words(asr: AsrResult, limit: int, peaks: Optional[list[Peak]] = None) -> str:
    """Return transcript focused on peak windows + sparse overview of the full video."""
    words = asr.words
    if not words:
        return "(자막 없음)"

    if not peaks:
        # No peaks: evenly sample across full duration
        step = max(1, len(words) // limit)
        sampled = words[::step][:limit]
        return "\n".join(f"{w.start:7.2f}  {w.text}" for w in sampled)

    # Build peak windows: ±90s around each peak
    window = 90.0
    selected: dict[int, bool] = {}
    for p in peaks:
        lo, hi = p.t - window, p.t + window
        for i, w in enumerate(words):
            if lo <= w.start <= hi:
                selected[i] = True

    # Fill remaining budget with evenly-spaced words from whole video
    budget = limit - len(selected)
    if budget > 0:
        step = max(1, len(words) // max(budget, 1))
        for i in range(0, len(words), step):
            if len(selected) >= limit:
                break
            selected[i] = True

    lines = [f"{words[i].start:7.2f}  {words[i].text}" for i in sorted(selected)]
    return "\n".join(lines)


def _format_peaks(peaks: list[Peak]) -> str:
    if not peaks:
        return "(신호 데이터 없음)"
    lines = []
    for p in peaks:
        parts = [f"laughter={p.laughter:.2f}", f"volume={p.volume:.2f}",
                 f"joy={p.emotion_joy:.2f}", f"surprise={p.emotion_surprise:.2f}",
                 f"tempo={p.tempo:.2f}"]
        if p.retention is not None:
            parts.insert(0, f"retention={p.retention:.2f}")
        mm = int(p.t) // 60
        ss = int(p.t) % 60
        lines.append(f"- {mm:02d}:{ss:02d}  score={p.score:.2f}  [{', '.join(parts)}]")
    return "\n".join(lines)


def _format_fewshot(examples: Optional[list[dict]]) -> str:
    if not examples:
        return "(아직 선호 데이터 없음)"
    lines = []
    for ex in examples:
        label = "👍" if ex.get("label", 0) > 0 else "👎"
        lines.append(f"- {label}  {ex.get('title', '')} — {ex.get('reason', '')}")
    return "\n".join(lines)


async def score_candidates(
    asr: AsrResult,
    peaks: list[Peak],
    fewshot: Optional[list[dict]] = None,
    cfg: ScoreConfig | None = None,
    llm_model: Optional[str] = None,
) -> list[ClipCandidate]:
    cfg = cfg or ScoreConfig()
    prompt = PROMPT_TEMPLATE.format(
        k=cfg.k,
        transcript_block=_format_words(asr, cfg.max_words_in_prompt, peaks),
        peaks_block=_format_peaks(peaks),
        fewshot_block=_format_fewshot(fewshot),
    )
    client = OllamaClient(model=llm_model)
    result = await client.generate_json(prompt)
    clips_raw = result.get("clips", [])
    out: list[ClipCandidate] = []
    for c in clips_raw[: cfg.k]:
        try:
            start = float(c["start"]); end = float(c["end"])
        except (KeyError, ValueError, TypeError):
            continue
        if end - start < 10 or end - start > 75:
            continue
        out.append(
            ClipCandidate(
                start=start, end=end,
                title=str(c.get("title", ""))[:32],
                reason=str(c.get("reason", ""))[:200],
                score=float(c.get("score", 0.0)),
            )
        )
    return out


# Backward compat — captions-only path used by initial M1 orchestrator
async def score_from_captions(asr: AsrResult, cfg: ScoreConfig | None = None) -> list[ClipCandidate]:
    return await score_candidates(asr, peaks=[], cfg=cfg)
