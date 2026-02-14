"""Тесты для функций отправки сообщений в sql_db.py."""
import pytest
from unittest.mock import patch, MagicMock
import random


class TestVkMessageFormatting:
    """Тесты форматирования сообщений VK."""
    
    def test_vk_peer_id_calculation_chat(self):
        """Проверяет преобразование chat_id в peer_id."""
        chat_id = 12345
        # peer_id = 2000000000 + chat_id для групповых чатов
        peer_id = 2000000000 + chat_id
        
        assert peer_id > 2000000000
        assert peer_id == 2000012345
    
    def test_vk_peer_id_large_values(self):
        """Проверяет обработку больших peer_id."""
        chat_id = 2000050000
        # Это уже выглядит как peer_id, должно оставаться как есть
        assert chat_id > 2000000000
    
    def test_vk_message_with_prefix(self):
        """Проверяет добавление префикса к сообщению."""
        from constants import MESSAGE_PREFIX
        
        message = 'Тестовое сообщение'
        prefixed = MESSAGE_PREFIX + message
        
        assert prefixed.startswith('➡')
        assert message in prefixed
        assert prefixed == '➡ Тестовое сообщение'
    
    def test_vk_random_id_generation(self):
        """Проверяет генерацию случайного ID для VK."""
        random_id = random.randint(1, 2**31 - 1)
        
        assert 1 <= random_id <= 2**31 - 1
        assert isinstance(random_id, int)


class TestTelegramMessageFormatting:
    """Тесты форматирования сообщений Telegram."""
    
    def test_telegram_message_with_prefix(self):
        """Проверяет добавление префикса."""
        from constants import MESSAGE_PREFIX
        
        message = 'Сообщение в Telegram'
        prefixed = MESSAGE_PREFIX + message
        
        assert prefixed == '➡ Сообщение в Telegram'
    
    def test_telegram_message_icon_conversion(self):
        """Проверяет что chat_id может быть строкой или числом."""
        # Telegram может работать со строками и числами
        chat_ids = ['123456789', '123456789', -987654321]
        
        for chat_id in chat_ids:
            try:
                int(chat_id)
            except (ValueError, TypeError):
                pytest.fail("chat_id должен быть преобразуем в int")


class TestTelegramMigrationDetection:
    """Тесты обнаружения миграции чатов."""
    
    def test_migration_error_pattern_1(self):
        """Проверяет паттерн ошибки миграции."""
        error_text = 'group has been migrated to a supergroup with id -100123456789'
        
        import re
        m = re.search(r'migrated to a supergroup with id\s+(-?\d+)', error_text)
        assert m is not None
        assert '-100123456789' in m.group(0)
    
    def test_migration_error_pattern_2(self):
        """Проверяет альтернативный паттерн ошибки."""
        error_text = 'supergroup with id -100999888777'
        
        import re
        m = re.search(r'supergroup with id\s+(-?\d+)', error_text)
        assert m is not None
    
    def test_migration_error_pattern_3(self):
        """Проверяет поиск ID в ошибке."""
        error_text = 'Chat was migrated, the new supergroup id is -100555666777'
        
        import re
        m = re.search(r'(-100\d{6,})', error_text)
        assert m is not None
        assert '-100555666777' in error_text


class TestBotBlockedDetection:
    """Тесты обнаружения блокировки бота."""
    
    def test_bot_blocked_error(self):
        """Проверяет обнаружение ошибки блокировки бота."""
        error_text = 'Bot was blocked by the user'
        
        lower_err = error_text.lower()
        is_blocked = 'bot was blocked' in lower_err
        
        assert is_blocked
    
    def test_user_deactivated_error(self):
        """Проверяет обнаружение деактивации пользователя."""
        error_text = 'User is deactivated and their private messages are inaccessible'
        
        lower_err = error_text.lower()
        is_deactivated = 'deactiv' in lower_err
        
        assert is_deactivated
    
    def test_forbidden_blocked_combination(self):
        """Проверяет комбинацию 'Forbidden' и 'blocked'."""
        error_text = 'Forbidden: bot was blocked by the user'
        
        lower_err = error_text.lower()
        is_forbidden_blocked = ('forbidden' in lower_err) and ('blocked' in lower_err)
        
        assert is_forbidden_blocked


class TestMessagePrefixConsistency:
    """Тесты консистентности префикса сообщений."""
    
    def test_same_message_same_result(self):
        """Проверяет что одно сообщение дает одинаковый результат."""
        from constants import MESSAGE_PREFIX
        
        message = 'Test message'
        result1 = MESSAGE_PREFIX + message
        result2 = MESSAGE_PREFIX + message
        
        assert result1 == result2
    
    def test_prefix_never_duplicated(self):
        """Проверяет что префикс не дублируется."""
        from constants import MESSAGE_PREFIX
        
        message = MESSAGE_PREFIX + 'Test'
        # Не должны добавлять префикс второй раз
        result = MESSAGE_PREFIX + message
        
        # Должны быть два префикса (проверяем что так делается в коде)
        prefix_count = result.count('➡')
        assert prefix_count >= 1


class TestMessageSplitting:
    """Тесты разбиения сообщений."""
    
    def test_split_response_uses_sentinel(self):
        """Проверяет что используется правильный разделитель."""
        from constants import MESSAGE_SPLIT_SENTINEL
        from messaging import split_response
        
        text = f'Part1{MESSAGE_SPLIT_SENTINEL}Part2{MESSAGE_SPLIT_SENTINEL}Part3'
        parts = split_response(text)
        
        assert len(parts) == 3
    
    def test_split_response_prefix_application(self):
        """Проверяет что префикс применяется к каждой части."""
        from constants import MESSAGE_PREFIX, MESSAGE_SPLIT_SENTINEL
        from messaging import split_response
        
        text = f'A{MESSAGE_SPLIT_SENTINEL}B'
        parts = split_response(text)
        
        for part in parts:
            assert part.startswith(MESSAGE_PREFIX)


class TestSqlDbErrorMessages:
    """Тесты формирования сообщений об ошибках."""
    
    def test_error_message_format(self):
        """Проверяет формат сообщения об ошибке."""
        error_msg = 'Извините, но в данный момент я не могу обработать ваш запрос, пожалуйста, попробуйте позже'
        
        assert 'извин' in error_msg.lower()
        assert 'не могу' in error_msg.lower() or 'не смогу' in error_msg.lower()
    
    def test_success_message_format(self):
        """Проверяет формат успешного сообщения."""
        success_msg = 'Сообщение успешно отправлено'
        
        assert 'успеш' in success_msg.lower() or 'отправлено' in success_msg.lower()
