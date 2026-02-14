"""Расширенные тесты для platform_context.py."""
from platform_context import resolve_platform, PlatformContext


def test_platform_context_dataclass_fields():
    ctx = PlatformContext('test', 'test_table', 'test_id', '123')
    assert ctx.name == 'test'
    assert ctx.table == 'test_table'
    assert ctx.id_column == 'test_id'
    assert ctx.user_id == '123'


def test_platform_context_equality():
    a = PlatformContext('email', 'email', 'email', 'a@b.com')
    b = PlatformContext('email', 'email', 'email', 'a@b.com')
    assert a == b


def test_platform_context_inequality():
    a = PlatformContext('email', 'email', 'email', 'a@b.com')
    b = PlatformContext('email', 'email', 'email', 'c@d.com')
    assert a != b


def test_resolve_all_none_returns_none():
    assert resolve_platform(email=None, vk_id_chat=None, vk_id_user=None, telegram=None, discord=None) is None


def test_resolve_empty_string_is_valid():
    """Пустая строка — не None, должна распознаться как email."""
    ctx = resolve_platform(email='')
    assert ctx is not None
    assert ctx.name == 'email'
    assert ctx.user_id == ''


def test_each_platform_returns_correct_table():
    cases = [
        ('email', {'email': 'x'}, 'email', 'email'),
        ('vk_chat', {'vk_id_chat': 'x'}, 'vk_chat', 'vk_id'),
        ('vk_user', {'vk_id_user': 'x'}, 'vk_user', 'vk_id'),
        ('telegram', {'telegram': 'x'}, 'telegram', 'telegram_id'),
        ('discord', {'discord': 'x'}, 'discord', 'discord_id'),
    ]
    for name, kwargs, expected_table, expected_id_col in cases:
        ctx = resolve_platform(**kwargs)
        assert ctx.name == name, f'Failed for {name}'
        assert ctx.table == expected_table, f'Wrong table for {name}'
        assert ctx.id_column == expected_id_col, f'Wrong id_column for {name}'
