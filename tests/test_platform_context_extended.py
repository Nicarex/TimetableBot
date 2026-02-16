"""Расширенные тесты для platform_context.py."""
from platform_context import resolve_platform, PlatformContext


def test_platform_context_dataclass_fields():
    ctx = PlatformContext('test', '123')
    assert ctx.platform == 'test'
    assert ctx.user_id == '123'


def test_platform_context_equality():
    a = PlatformContext('email', 'a@b.com')
    b = PlatformContext('email', 'a@b.com')
    assert a == b


def test_platform_context_inequality():
    a = PlatformContext('email', 'a@b.com')
    b = PlatformContext('email', 'c@d.com')
    assert a != b


def test_resolve_all_none_returns_none():
    assert resolve_platform(email=None, vk_id_chat=None, vk_id_user=None, telegram=None, discord=None) is None


def test_resolve_empty_string_is_valid():
    """Пустая строка — не None, должна распознаться как email."""
    ctx = resolve_platform(email='')
    assert ctx is not None
    assert ctx.platform == 'email'
    assert ctx.user_id == ''


def test_each_platform_returns_correct_platform():
    cases = [
        ('email', {'email': 'x'}),
        ('vk_chat', {'vk_id_chat': 'x'}),
        ('vk_user', {'vk_id_user': 'x'}),
        ('telegram', {'telegram': 'x'}),
        ('discord', {'discord': 'x'}),
    ]
    for expected_platform, kwargs in cases:
        ctx = resolve_platform(**kwargs)
        assert ctx.platform == expected_platform, f'Failed for {expected_platform}'
        assert ctx.user_id == 'x'
