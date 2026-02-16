"""Расширенные тесты для platform_context.py и sql_db."""
import pytest
from platform_context import resolve_platform, PlatformContext


class TestResolveplatformExtended:
    """Расширенные тесты для resolve_platform."""

    def test_priority_order_email_wins(self):
        ctx = resolve_platform(
            email='a@b.com',
            vk_id_chat='123',
            vk_id_user='456',
            telegram='789',
            discord='999'
        )
        assert ctx.platform == 'email'
        assert ctx.user_id == 'a@b.com'

    def test_priority_vk_chat_second(self):
        ctx = resolve_platform(
            vk_id_chat='123',
            vk_id_user='456',
            telegram='789'
        )
        assert ctx.platform == 'vk_chat'

    def test_priority_vk_user_third(self):
        ctx = resolve_platform(
            vk_id_user='456',
            telegram='789',
            discord='999'
        )
        assert ctx.platform == 'vk_user'

    def test_priority_telegram_fourth(self):
        ctx = resolve_platform(
            telegram='789',
            discord='999'
        )
        assert ctx.platform == 'telegram'

    def test_priority_discord_fifth(self):
        ctx = resolve_platform(discord='999')
        assert ctx.platform == 'discord'

    def test_all_platforms_correct(self):
        assert resolve_platform(email='test@mail.com').platform == 'email'
        assert resolve_platform(vk_id_chat='123').platform == 'vk_chat'
        assert resolve_platform(vk_id_user='456').platform == 'vk_user'
        assert resolve_platform(telegram='789').platform == 'telegram'
        assert resolve_platform(discord='999').platform == 'discord'

    def test_user_id_preserved(self):
        test_id = 'unique_test_id_12345'
        ctx = resolve_platform(email=test_id)
        assert ctx.user_id == test_id

    def test_platform_context_dataclass(self):
        ctx = PlatformContext('test', '123')
        assert ctx.platform == 'test'
        assert ctx.user_id == '123'

    def test_multiple_calls_independent(self):
        ctx1 = resolve_platform(email='a@b.com')
        ctx2 = resolve_platform(telegram='123')
        assert ctx1.platform == 'email'
        assert ctx2.platform == 'telegram'
        assert ctx1.user_id != ctx2.user_id


class TestMessagingBuildFunctions:
    """Тесты для функций построения сообщений в sql_db.py."""

    def test_build_saved_response_comprehensive(self):
        from sql_db import _build_saved_response
        result = _build_saved_response('Учитель ', 'Группа ', is_chat=False)
        assert 'преподават' in result.lower()
        assert 'груп' in result.lower()

        result = _build_saved_response('Учитель ', '', is_chat=False)
        assert 'преподават' in result.lower()
        assert 'груп' not in result.lower()

        result = _build_saved_response('', 'Группа ', is_chat=False)
        assert 'груп' in result.lower()
        assert 'преподават' not in result.lower()

    def test_build_saved_response_in_chat_mode(self):
        from sql_db import _build_saved_response
        result = _build_saved_response('Учитель ', 'Группа ', is_chat=True)
        assert result


class TestBuildAddedResponse:
    """Тесты для _build_added_response."""

    def test_build_added_response_all_parts(self):
        from sql_db import _build_added_response
        result = _build_added_response('Существующее', 'Учитель', 'Группа')
        assert 'Существующее' in result
        assert 'Учитель' in result
        assert 'Группа' in result

    def test_build_added_response_partial(self):
        from sql_db import _build_added_response
        result = _build_added_response('', 'Учитель', '')
        assert 'Учитель' in result
        result = _build_added_response('', '', 'Группа')
        assert 'Группа' in result

    def test_build_added_response_empty(self):
        from sql_db import _build_added_response
        result = _build_added_response('', '', '')
        assert result == ''
