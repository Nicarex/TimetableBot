from platform_context import resolve_platform, PlatformContext


def test_resolve_email():
    ctx = resolve_platform(email='test@mail.com')
    assert ctx == PlatformContext('email', 'test@mail.com')


def test_resolve_vk_chat():
    ctx = resolve_platform(vk_id_chat='12345')
    assert ctx == PlatformContext('vk_chat', '12345')


def test_resolve_vk_user():
    ctx = resolve_platform(vk_id_user='67890')
    assert ctx == PlatformContext('vk_user', '67890')


def test_resolve_telegram():
    ctx = resolve_platform(telegram='111222')
    assert ctx == PlatformContext('telegram', '111222')


def test_resolve_discord():
    ctx = resolve_platform(discord='333444')
    assert ctx == PlatformContext('discord', '333444')


def test_resolve_none():
    ctx = resolve_platform()
    assert ctx is None


def test_resolve_priority():
    # email has highest priority
    ctx = resolve_platform(email='a@b.com', telegram='123')
    assert ctx.platform == 'email'
