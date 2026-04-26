from app.pipeline.fewshot import _diverse_pick


def _row(pref_id: int, source: str, label: int = 1) -> dict:
    return {
        "pref_id": pref_id,
        "label": label,
        "clip_id": pref_id,
        "title": f"t{pref_id}",
        "reason": "",
        "source_video_id": source,
    }


def test_diverse_pick_prefers_unique_sources():
    rows = [_row(1, "A"), _row(2, "A"), _row(3, "B"), _row(4, "C")]
    picked = _diverse_pick(rows, k=2)
    assert [r["pref_id"] for r in picked] == [1, 3]


def test_diverse_pick_pads_when_not_enough_unique():
    rows = [_row(1, "A"), _row(2, "A"), _row(3, "A")]
    picked = _diverse_pick(rows, k=2)
    assert len(picked) == 2
    assert picked[0]["pref_id"] == 1
    assert picked[1]["pref_id"] in (2, 3)


def test_diverse_pick_empty_and_zero():
    assert _diverse_pick([], k=3) == []
    assert _diverse_pick([_row(1, "A")], k=0) == []


def test_diverse_pick_newest_first_preserved():
    rows = [_row(9, "Z"), _row(8, "Y"), _row(7, "X")]
    picked = _diverse_pick(rows, k=3)
    assert [r["pref_id"] for r in picked] == [9, 8, 7]
