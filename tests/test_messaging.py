from messaging import split_response


def test_split_response_basic():
    parts = split_response('Hello\nCut\nWorld')
    assert parts == ['➡ Hello\n', '➡ World']


def test_split_response_single():
    parts = split_response('Just one message')
    assert parts == ['➡ Just one message']


def test_split_response_empty_parts():
    parts = split_response('Cut\nCut\nHello')
    assert parts == ['➡ Hello']


def test_split_response_no_content():
    parts = split_response('')
    assert parts == []


def test_split_response_prefix():
    parts = split_response('Test')
    assert all(p.startswith('➡ ') for p in parts)
