"""One-shot ASR script — builds asr_cache.json without the server."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.pipeline.stages.asr import transcribe

audio = Path("data/videos/czuqJe_c7_s/audio.wav")
cache = audio.parent / "asr_cache.json"

if cache.exists():
    print("Cache already exists:", cache)
    sys.exit(0)

print(f"Transcribing {audio} ({audio.stat().st_size / 1024**2:.0f} MB)...")
result = transcribe(audio)
print(f"Done: {len(result.words)} words, lang={result.language}")
print(f"Cache saved to {cache}")
