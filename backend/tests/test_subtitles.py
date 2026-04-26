from app.pipeline.render.subtitles import (
    _fmt_time, _hex_to_ass, _alpha_from_opacity, _group_words, build_ass,
)
from app.pipeline.stages.asr import Word


def test_fmt_time():
    assert _fmt_time(0) == "0:00:00.00"
    assert _fmt_time(75.5) == "0:01:15.50"


def test_hex_to_ass_white():
    # #FFFFFF → &H00FFFFFF (BGR form is still all-Fs)
    assert _hex_to_ass("#FFFFFF") == "&H00FFFFFF"


def test_hex_to_ass_reverses_channels():
    # #FF0000 (red) → &H000000FF (ASS stores BGR)
    assert _hex_to_ass("#FF0000") == "&H000000FF"


def test_alpha_from_opacity_bounds():
    assert _alpha_from_opacity(1.0) == "00"  # fully visible = alpha 00
    assert _alpha_from_opacity(0.0) == "FF"
    assert _alpha_from_opacity(0.4) in {"98", "99", "9A"}


def make_word(s: float, e: float, text: str) -> Word:
    return Word(start=s, end=e, text=text)


def test_group_words_respects_clip_window():
    words = [
        make_word(0.0, 0.3, "A"),
        make_word(0.3, 0.6, "B"),
        make_word(10.0, 10.3, "C"),
    ]
    blocks = _group_words(words, clip_start=5.0, clip_end=15.0)
    # A, B fall before clip_start; C should show
    texts = [b[2] for b in blocks]
    assert "C" in texts
    assert not any("A" in t or "B" in t for t in texts)


def test_group_words_chunks_by_count_or_span():
    words = [make_word(i * 0.2, i * 0.2 + 0.15, f"w{i}") for i in range(6)]
    blocks = _group_words(words, clip_start=0.0, clip_end=10.0)
    assert all(len(b[2].split()) <= 3 for b in blocks)


def test_build_ass_contains_expected_sections():
    words = [make_word(0.5, 1.0, "안녕")]
    content = build_ass(
        words, 0.0, 5.0,
        caption_style={"font": "fonts/Pretendard-Medium.otf", "size": 62, "color": "#FFFFFF"},
        animation={"type": "fade", "duration": 0.4},
    )
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    assert "Style: Default" in content
    assert "Dialogue: 0," in content
    assert r"\fad(400,0)" in content
    assert "안녕" in content
