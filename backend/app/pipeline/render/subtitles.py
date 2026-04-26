"""Build ASS subtitles from Whisper word timestamps + template caption style.

Groups words into 2-3 word blocks that stay on screen ~1.5-2s.
Emits an .ass file that ffmpeg `-vf subtitles=...` can burn in.
"""
from dataclasses import dataclass
from pathlib import Path

from app.pipeline.stages.asr import Word

MAX_WORDS_PER_BLOCK = 3
TARGET_BLOCK_S = 1.8


def _fmt_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def _hex_to_ass(color: str, alpha_hex: str = "00") -> str:
    """#RRGGBB → &H{AA}{BB}{GG}{RR}"""
    c = color.lstrip("#")
    if len(c) != 6:
        return "&H00FFFFFF"
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H{alpha_hex}{b}{g}{r}"


def _alpha_from_opacity(opacity: float) -> str:
    # ASS alpha: 00 = opaque, FF = fully transparent. opacity is 0..1 visibility.
    clamped = max(0.0, min(1.0, opacity))
    return f"{int(round((1 - clamped) * 255)):02X}"


def _group_words(words: list[Word], clip_start: float, clip_end: float) -> list[tuple[float, float, str]]:
    blocks: list[tuple[float, float, str]] = []
    buf: list[Word] = []

    def flush():
        if not buf:
            return
        start = max(buf[0].start, clip_start) - clip_start
        end = min(buf[-1].end, clip_end) - clip_start
        if end > start:
            text = " ".join(w.text for w in buf).strip()
            blocks.append((start, end, text))
        buf.clear()

    for w in words:
        if w.end < clip_start or w.start > clip_end:
            continue
        buf.append(w)
        span = buf[-1].end - buf[0].start
        if len(buf) >= MAX_WORDS_PER_BLOCK or span >= TARGET_BLOCK_S:
            flush()
    flush()
    return blocks


def _position_and_alignment(position: dict) -> tuple[int, int]:
    """Map template position.anchor to ASS alignment code + MarginV."""
    anchor = position.get("anchor", "bottom")
    margin_y = int(position.get("margin_y", 180))
    # Numpad keys: 1=bl 2=bc 3=br 4=ml 5=mc 6=mr 7=tl 8=tc 9=tr
    align_map = {"bottom": 2, "center": 5, "top": 8}
    return align_map.get(anchor, 2), margin_y


def _style_line(style: dict, animation_type: str) -> str:
    font_path = style.get("font", "")
    font_name = Path(font_path).stem or "Pretendard"
    size = int(style.get("size", 62))
    primary = _hex_to_ass(style.get("color", "#FFFFFF"))
    outline_color = _hex_to_ass(style.get("stroke", "#000000"))
    outline_w = int(style.get("stroke_width", 3))

    bg = style.get("background")
    border_style = 3 if bg else 1
    back_color = _hex_to_ass(
        (bg or {}).get("color", "#000000"),
        alpha_hex=_alpha_from_opacity((bg or {}).get("opacity", 1.0)),
    )

    align, margin_v = _position_and_alignment(style.get("position", {}))

    return (
        f"Style: Default,{font_name},{size},{primary},&H000000FF,"
        f"{outline_color},{back_color},0,0,0,0,100,100,0,0,"
        f"{border_style},{outline_w},0,{align},40,40,{margin_v},1"
    )


def _animation_prefix(animation: dict | None) -> str:
    if not animation:
        return ""
    typ = animation.get("type", "none")
    if typ == "fade":
        ms = int(float(animation.get("duration", 0.3)) * 1000)
        return f"{{\\fad({ms},0)}}"
    if typ == "pop":
        scale = float(animation.get("scale_from", 1.15))
        ms = int(float(animation.get("duration", 0.1)) * 1000)
        return f"{{\\fscx{int(scale*100)}\\fscy{int(scale*100)}\\t(0,{ms},\\fscx100\\fscy100)}}"
    return ""


def build_ass(
    words: list[Word],
    clip_start: float,
    clip_end: float,
    caption_style: dict,
    animation: dict | None,
    play_res: tuple[int, int] = (1080, 1920),
) -> str:
    blocks = _group_words(words, clip_start, clip_end)
    anim = _animation_prefix(animation)

    lines = [
        "[Script Info]",
        "Title: K-Shorts",
        "ScriptType: v4.00+",
        f"PlayResX: {play_res[0]}",
        f"PlayResY: {play_res[1]}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding",
        _style_line(caption_style, (animation or {}).get("type", "none")),
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    for start, end, text in blocks:
        safe = text.replace("\n", " ").replace("{", "").replace("}", "")
        lines.append(
            f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Default,,0,0,0,,{anim}{safe}"
        )
    return "\n".join(lines)


def write_ass(
    path: Path, words: list[Word], clip_start: float, clip_end: float,
    caption_style: dict, animation: dict | None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = build_ass(words, clip_start, clip_end, caption_style, animation)
    path.write_text(content, encoding="utf-8")
    return path
