"""Расширенные тесты для messaging.py."""
from messaging import split_response
from constants import MESSAGE_PREFIX, MESSAGE_SPLIT_SENTINEL


def test_split_uses_correct_sentinel():
    text = f'Part1{MESSAGE_SPLIT_SENTINEL}Part2'
    parts = split_response(text)
    assert len(parts) == 2


def test_split_uses_correct_prefix():
    parts = split_response('Hello')
    assert parts[0] == MESSAGE_PREFIX + 'Hello'


def test_split_multiple_parts():
    text = 'A\nCut\nB\nCut\nC'
    parts = split_response(text)
    assert len(parts) == 3
    assert parts[0] == '➡ A\n'
    assert parts[1] == '➡ B\n'
    assert parts[2] == '➡ C'


def test_split_handles_none_like_string():
    parts = split_response(None)
    assert parts == ['➡ None']


def test_split_preserves_newlines_within_parts():
    text = 'Line1\nLine2\nCut\nLine3'
    parts = split_response(text)
    assert len(parts) == 2
    assert '\n' in parts[0]  # newlines preserved inside part


def test_split_consecutive_sentinels():
    text = 'Cut\nCut\nCut\n'
    parts = split_response(text)
    assert parts == []


def test_split_large_text():
    """Проверяем что split корректно работает с большим текстом."""
    chunks = [f'Chunk{i}' for i in range(100)]
    text = 'Cut\n'.join(chunks)
    parts = split_response(text)
    assert len(parts) == 100
