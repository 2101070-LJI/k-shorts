from dataclasses import dataclass

from app.pipeline.boundary import Interval, snap_boundaries
from app.pipeline.stages.asr import AsrResult, Word


@dataclass
class _FakeAsr:
    words: list
    text: str = ""
    language: str = "ko"


def make_asr(word_starts: list[float]) -> AsrResult:
    words = [Word(start=s, end=s + 0.3, text=f"w{i}") for i, s in enumerate(word_starts)]
    return AsrResult(language="ko", text="", words=words)


def test_snap_enforces_min_length():
    asr = make_asr([i * 0.5 for i in range(200)])  # words every 0.5s up to ~100s
    silences = [Interval(9.5, 10.0), Interval(12.5, 13.0)]
    start, end = snap_boundaries(10.0, 13.0, asr, silences)
    assert end - start >= 15.0 - 1e-9


def test_snap_clips_max_length():
    asr = make_asr([i * 0.5 for i in range(200)])
    silences = []
    start, end = snap_boundaries(5.0, 80.0, asr, silences)
    assert end - start <= 60.0  # max 59 + small tolerance from tail
