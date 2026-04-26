import pytest

from app.services.ollama_client import _parse_json


def test_clean_json():
    assert _parse_json('{"a": 1}') == {"a": 1}


def test_wrapped_in_prose():
    raw = "여기 결과입니다:\n```json\n{\"clips\": [{\"start\": 1}]}\n```\n끝"
    assert _parse_json(raw) == {"clips": [{"start": 1}]}


def test_no_json():
    with pytest.raises(ValueError):
        _parse_json("hello world")
