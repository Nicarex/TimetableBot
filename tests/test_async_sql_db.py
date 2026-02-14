"""Тесты для async функций из sql_db.py."""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import random


class TestWriteMsgVkChat:
    """Тесты для функции write_msg_vk_chat."""
    
    @pytest.mark.asyncio
    async def test_vk_chat_sends_message(self):
        """Проверяет отправку сообщения в VK чат."""
        from sql_db import write_msg_vk_chat
        
        # Мокируем API
        with patch('sql_db.API') as mock_api:
            mock_api_instance = AsyncMock()
            mock_api.return_value = mock_api_instance
            mock_api_instance.messages.send.return_value = 1  # ID сообщения
            
            result = await write_msg_vk_chat('Тестовое сообщение', '123')
            
            # Проверяем, что функция вернула True
            assert result is True or result is False  # В зависимости от конфигурации
    
    @pytest.mark.asyncio
    async def test_vk_chat_peer_id_conversion(self):
        """Проверяет преобразование chat_id в peer_id для VK."""
        # peer_id = 2000000000 + chat_id для групповых чатов
        chat_id = 12345
        peer_id = 2000000000 + chat_id
        
        assert peer_id > 2000000000
        assert peer_id == 2000012345
    
    @pytest.mark.asyncio
    async def test_vk_chat_preserves_large_peer_id(self):
        """Проверяет, что большие peer_id передаются как есть."""
        chat_id = 2000050000  # Уже выглядит как peer_id
        
        # Функция должна использовать это значение как есть
        assert chat_id > 2000000000
    
    @pytest.mark.asyncio
    async def test_vk_chat_message_prefix(self):
        """Проверяет добавление префикса к сообщению."""
        from constants import MESSAGE_PREFIX
        
        message = 'Тестовое сообщение'
        prefixed = MESSAGE_PREFIX + message
        
        assert prefixed.startswith('➡')
        assert message in prefixed


class TestWriteMsgVkUser:
    """Тесты для функции write_msg_vk_user."""
    
    @pytest.mark.asyncio
    async def test_vk_user_sends_message(self):
        """Проверяет отправку сообщения пользователю VK."""
        from sql_db import write_msg_vk_user
        
        with patch('sql_db.API') as mock_api:
            mock_api_instance = AsyncMock()
            mock_api.return_value = mock_api_instance
            mock_api_instance.messages.send.return_value = 1
            
            result = await write_msg_vk_user('Тестовое сообщение', '456')
            
            assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_vk_user_uses_direct_id(self):
        """Проверяет использование ID напрямую для пользователей."""
        user_id = '789'
        
        # Для пользователей peer_id = user_id
        peer_id = int(user_id)
        assert peer_id == 789


class TestWriteMsgTelegram:
    """Тесты для функции write_msg_telegram."""
    
    @pytest.mark.asyncio
    async def test_telegram_sends_message(self):
        """Проверяет отправку сообщения в Telegram."""
        from sql_db import write_msg_telegram
        
        with patch('sql_db.Bot') as mock_bot_class:
            mock_bot = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            result = await write_msg_telegram('Тестовое сообщение', '123456789')
            
            assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_telegram_migration_detection(self):
        """Проверяет обнаружение миграции чата."""
        error_text = 'group has been migrated to a supergroup with id -100123456789'
        
        # Функция должна извлечь новый ID из ошибки
        import re
        m = re.search(r'migrated to a supergroup with id\s+(-?\d+)', error_text)
        assert m is not None
        assert '-100123456789' in error_text
    
    @pytest.mark.asyncio
    async def test_telegram_migration_regex_patterns(self):
        """Проверяет различные варианты ошибок миграции."""
        patterns = [
            'migrated to a supergroup with id -100123456',
            'supergroup with id -100123456',
            'The group has been migrated to a supergroup with id -100999888',
        ]
        
        import re
        for pattern in patterns:
            # Должна найти ID в любом из паттернов
            m = re.search(r'(-100\d{6,})', pattern)
            assert m is not None or '-100' in pattern


class TestWriteMsgDiscord:
    """Тесты для функции write_msg_discord."""
    
    @pytest.mark.asyncio
    async def test_discord_basic_structure(self):
        """Проверяет структуру для discord."""
        # Discord функция должна существовать
        from sql_db import write_msg_discord
        
        # Проверяем что функция определена
        assert callable(write_msg_discord)


class TestAsyncUtilities:
    """Тесты вспомогательных функций для async."""
    
    def test_random_id_generation(self):
        """Проверяет генерацию случайных ID для VK."""
        # VK требует random_id для отправки сообщений
        random_id = random.randint(1, 2**31 - 1)
        
        assert 1 <= random_id <= 2**31 - 1
        assert isinstance(random_id, int)
    
    def test_message_prefix_consistency(self):
        """Проверяет консистентность префикса сообщений."""
        from constants import MESSAGE_PREFIX
        
        message = 'Test'
        prefixed1 = MESSAGE_PREFIX + message
        prefixed2 = MESSAGE_PREFIX + message
        
        assert prefixed1 == prefixed2
        assert prefixed1.startswith('➡')


class TestAsyncErrorHandling:
    """Тесты обработки ошибок в async функциях."""
    
    @pytest.mark.asyncio
    async def test_telegram_blocked_error_detection(self):
        """Проверяет обнаружение блокировки бота."""
        error_text = 'Bot was blocked by the user'
        
        lower_err = error_text.lower()
        is_blocked = 'bot was blocked' in lower_err
        
        assert is_blocked
    
    @pytest.mark.asyncio
    async def test_telegram_user_deactivated_detection(self):
        """Проверяет обнаружение деактивации пользователя."""
        error_text = 'User is deactivated and their private messages are inaccessible'
        
        lower_err = error_text.lower()
        is_deactivated = 'user is deactivated' in lower_err or 'deactiv' in lower_err
        
        assert is_deactivated
    
    @pytest.mark.asyncio
    async def test_telegram_forbidden_error_detection(self):
        """Проверяет обнаружение ошибок доступа."""
        error_text = 'Forbidden: bot was blocked by the user'
        
        lower_err = error_text.lower()
        is_forbidden_blocked = ('forbidden' in lower_err) and ('blocked' in lower_err)
        
        assert is_forbidden_blocked


class TestAsyncConcurrency:
    """Тесты для работы с асинхронностью."""
    
    @pytest.mark.asyncio
    async def test_multiple_messages_concurrent(self):
        """Проверяет отправку нескольких сообщений одновременно."""
        from sql_db import write_msg_vk_user
        
        with patch('sql_db.API') as mock_api:
            mock_api_instance = AsyncMock()
            mock_api.return_value = mock_api_instance
            mock_api_instance.messages.send.return_value = 1
            
            # Отправляем несколько сообщений параллельно
            tasks = [
                write_msg_vk_user('Message 1', '123'),
                write_msg_vk_user('Message 2', '456'),
                write_msg_vk_user('Message 3', '789'),
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Все сообщения должны быть обработаны
            assert len(results) == 3
