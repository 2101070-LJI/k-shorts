import gc
import json
import subprocess
import sys
import wave
from dataclasses import dataclass, field
from pathlib import Path

_CHUNK_SEC = 30  # 30s = 1 Whisper window — ctranslate2 4.7.1 crashes on multi-window audio on this CUDA build


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class AsrResult:
    language: str
    text: str
    words: list[Word] = field(default_factory=list)


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def _split_wav(src: Path, chunk_sec: int) -> list[tuple[Path, float]]:
    tmp_dir = src.parent / "_asr_chunks"
    tmp_dir.mkdir(exist_ok=True)
    with wave.open(str(src), "rb") as wf:
        sr = wf.getframerate()
        n_ch = wf.getnchannels()
        sw = wf.getsampwidth()
        total = wf.getnframes()
        chunk_frames = chunk_sec * sr
        chunks: list[tuple[Path, float]] = []
        idx = 0
        while idx * chunk_frames < total:
            wf.setpos(idx * chunk_frames)
            frames = wf.readframes(min(chunk_frames, total - idx * chunk_frames))
            p = tmp_dir / f"chunk_{idx:04d}.wav"
            with wave.open(str(p), "wb") as out:
                out.setnchannels(n_ch)
                out.setsampwidth(sw)
                out.setframerate(sr)
                out.writeframes(frames)
            chunks.append((p, (idx * chunk_frames) / sr))
            idx += 1
    return chunks


# ---------------------------------------------------------------------------
# Subprocess worker — run via `python -m app.pipeline.stages.asr <wav> <offset>`
# so a ctranslate2 crash never kills the server process.
# ---------------------------------------------------------------------------
_WORKER_SCRIPT = """
import gc, json, sys, torch
from faster_whisper import WhisperModel

wav_path, offset = sys.argv[1], float(sys.argv[2])
model_size = sys.argv[3] if len(sys.argv) > 3 else "large-v3"

model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
try:
    segs, info = model.transcribe(
        wav_path, language="ko", word_timestamps=True,
        vad_filter=True, beam_size=2, chunk_length=25,
    )
    words = []
    text_parts = []
    for seg in segs:
        text_parts.append(seg.text)
        for w in seg.words or []:
            if w.start is None or w.end is None:
                continue
            words.append({"start": w.start + offset, "end": w.end + offset, "text": w.word.strip()})
    result = {"language": info.language, "text": "".join(text_parts), "words": words}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()
finally:
    del model
    gc.collect()
    torch.cuda.empty_cache()
"""


def _transcribe_chunk_subprocess(
    wav_path: Path, offset: float, model_size: str
) -> tuple[str, list[Word], str]:
    import tempfile, os
    # Write worker script to a temp file to avoid Windows command-line quoting issues
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(_WORKER_SCRIPT)
        script_path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, script_path, str(wav_path), str(offset), model_size],
            capture_output=True,
            timeout=3600,
        )
    finally:
        os.unlink(script_path)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace")[-800:]
        raise RuntimeError(f"ASR subprocess failed (code {proc.returncode}): {err}")
    raw = proc.stdout.decode("utf-8", errors="replace")
    data = json.loads(raw)
    words = [Word(start=w["start"], end=w["end"], text=w["text"]) for w in data["words"]]
    return data["text"], words, data["language"]


def transcribe(audio_path: Path, model_size: str = "large-v3") -> AsrResult:
    """Transcribe via isolated subprocesses — one per 30s chunk.
    Results are cached to <audio_dir>/asr_cache.json so re-runs are instant.
    """
    import shutil

    cache_path = audio_path.parent / "asr_cache.json"
    if cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        words = [Word(start=w["start"], end=w["end"], text=w["text"]) for w in data["words"]]
        return AsrResult(language=data["language"], text=data["text"], words=words)

    duration = _wav_duration(audio_path)

    if duration <= _CHUNK_SEC * 1.1:
        text, words, lang = _transcribe_chunk_subprocess(audio_path, 0.0, model_size)
        return AsrResult(language=lang, text=text, words=words)

    chunks = _split_wav(audio_path, _CHUNK_SEC)
    tmp_dir = chunks[0][0].parent if chunks else None
    all_text: list[str] = []
    all_words: list[Word] = []
    lang = "ko"
    try:
        import logging
        _log = logging.getLogger(__name__)
        for i, (chunk_path, offset) in enumerate(chunks):
            _log.info("ASR chunk %d/%d offset=%.0fs", i + 1, len(chunks), offset)
            try:
                t, w, l = _transcribe_chunk_subprocess(chunk_path, offset, model_size)
                all_text.append(t)
                all_words.extend(w)
                lang = l
            except RuntimeError as e:
                # ctranslate2 native crash on specific audio — skip chunk, continue
                _log.warning("ASR chunk %d skipped (native crash): %s", i + 1, e)
    finally:
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

    result = AsrResult(language=lang, text="".join(all_text), words=all_words)
    cache_path.write_text(
        json.dumps({
            "language": result.language,
            "text": result.text,
            "words": [{"start": w.start, "end": w.end, "text": w.text} for w in result.words],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return result
