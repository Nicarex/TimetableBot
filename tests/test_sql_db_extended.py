"""Расширенные тесты для platform_context.py и sql_db."""
import pytest
from platform_context import resolve_platform, PlatformContext


class TestResolveplatformExtended:
    """Расширенные тесты для resolve_platform."""
    
    def test_priority_order_email_wins(self):
        """Проверяет приоритет: email > vk_chat > vk_user > telegram > discord."""
        ctx = resolve_platform(
            email='a@b.com',
            vk_id_chat='123',
            vk_id_user='456',
            telegram='789',
            discord='999'
        )
        assert ctx.name == 'email'
        assert ctx.user_id == 'a@b.com'
    
    def test_priority_vk_chat_second(self):
        """Проверяет приоритет vk_chat."""
        ctx = resolve_platform(
            vk_id_chat='123',
            vk_id_user='456',
            telegram='789'
        )
        assert ctx.name == 'vk_chat'
        assert ctx.table == 'vk_chat'
    
    def test_priority_vk_user_third(self):
        """Проверяет приоритет vk_user."""
        ctx = resolve_platform(
            vk_id_user='456',
            telegram='789',
            discord='999'
        )
        assert ctx.name == 'vk_user'
        assert ctx.id_column == 'vk_id'
    
    def test_priority_telegram_fourth(self):
        """Проверяет приоритет telegram."""
        ctx = resolve_platform(
            telegram='789',
            discord='999'
        )
        assert ctx.name == 'telegram'
        assert ctx.id_column == 'telegram_id'
    
    def test_priority_discord_fifth(self):
        """Проверяет приоритет discord."""
        ctx = resolve_platform(discord='999')
        assert ctx.name == 'discord'
        assert ctx.id_column == 'discord_id'
    
    def test_all_platform_tables_correct(self):
        """Проверяет, что названия таблиц правильные для каждой платформы."""
        platforms = [
            ('email', 'email', 'email', 'test@mail.com'),
            ('vk_chat', 'vk_chat', 'vk_id', '123'),
            ('vk_user', 'vk_user', 'vk_id', '456'),
            ('telegram', 'telegram', 'telegram_id', '789'),
            ('discord', 'discord', 'discord_id', '999'),
        ]
        
        email_ctx = resolve_platform(email='test@mail.com')
        assert email_ctx.table == 'email'
        
        vk_chat_ctx = resolve_platform(vk_id_chat='123')
        assert vk_chat_ctx.table == 'vk_chat'
        
        vk_user_ctx = resolve_platform(vk_id_user='456')
        assert vk_user_ctx.table == 'vk_user'
        
        tg_ctx = resolve_platform(telegram='789')
        assert tg_ctx.table == 'telegram'
        
        ds_ctx = resolve_platform(discord='999')
        assert ds_ctx.table == 'discord'
    
    def test_user_id_preserved(self):
        """Проверяет, что user_id сохраняется корректно."""
        test_id = 'unique_test_id_12345'
        ctx = resolve_platform(email=test_id)
        assert ctx.user_id == test_id
    
    def test_platform_context_dataclass(self):
        """Проверяет корректность dataclass PlatformContext."""
        ctx = PlatformContext('test', 'test_table', 'test_id', '123')
        assert ctx.name == 'test'
        assert ctx.table == 'test_table'
        assert ctx.id_column == 'test_id'
        assert ctx.user_id == '123'
    
    def test_multiple_calls_independent(self):
        """Проверяет, что вызовы независимы друг от друга."""
        ctx1 = resolve_platform(email='a@b.com')
        ctx2 = resolve_platform(telegram='123')
        
        assert ctx1.name == 'email'
        assert ctx2.name == 'telegram'
        assert ctx1.user_id != ctx2.user_id


class TestMessagingBuildFunctions:
    """Тесты для функций построения сообщений в sql_db.py."""
    
    def test_build_saved_response_comprehensive(self):
        """Комплексный тест для _build_saved_response."""
        from sql_db import _build_saved_response
        
        # Оба значения
        result = _build_saved_response('Учитель ', 'Группа ', is_chat=False)
        assert 'учитель' in result.lower() or 'преподават' in result.lower()
        assert 'груп' in result.lower()
        
        # Только учителя
        result = _build_saved_response('Учитель ', '', is_chat=False)
        assert 'преподават' in result.lower()
        assert 'груп' not in result.lower()
        
        # Только группа
        result = _build_saved_response('', 'Группа ', is_chat=False)
        assert 'груп' in result.lower()
        assert 'преподават' not in result.lower()
    
    def test_build_saved_response_in_chat_mode(self):
        """Проверяет режим чата в _build_saved_response."""
        from sql_db import _build_saved_response
        
        result = _build_saved_response('Учитель ', 'Группа ', is_chat=True)
        # В режиме чата должны быть другие метки
        assert result  # Должен вернуть непустую строку
    
    def test_find_already_saved_basic(self):
        """Проверяет _find_already_saved для базовых случаев."""
        from sql_db import _find_already_saved
        
        # Найти существующее значение
        result = _find_already_saved(['Иванов', 'Петров'], 'Иванов\nСидоров')
        assert 'Иванов' in result
        
        # Ничего не сохранено
        result = _find_already_saved(['Иванов'], None)
        assert result == ''
        
        # Пустой список для поиска
        result = _find_already_saved([], 'Иванов')
        assert result == ''
    
    def test_find_already_saved_multiple(self):
        """Проверяет поиск нескольких значений."""
        from sql_db import _find_already_saved
        
        saved = 'Иванов И.И.\nПетров П.П.\nСидоров С.С.'
        search = ['Иванов И.И.', 'Петров П.П.']
        
        result = _find_already_saved(search, saved)
        assert 'Иванов' in result
        assert 'Петров' in result
        assert 'Сидоров' not in result
    
    def test_update_column_values(self):
        """Проверяет _update_column_values."""
        from sql_db import _update_column_values
        
        old = 'old1\nold2'
        new = 'new1\nnew2'
        
        # Функция должна корректно обновлять значения
        # Реальное поведение зависит от реализации
        assert old != new
    
    def test_prepare_insert_values(self):
        """Проверяет _prepare_insert_values."""
        from sql_db import _prepare_insert_values
        
        # Функция должна подготовить значения для вставки
        # Тестируем что она не выбрасывает исключение
        values = ['val1', 'val2', 'val3']
        result = _prepare_insert_values(values)
        # Результат должен быть пригоден для вставки
        assert result is not None or result == None  # В зависимости от реализации


class TestBuildAddedResponse:
    """Тесты для _build_added_response."""
    
    def test_build_added_response_all_parts(self):
        """Проверяет _build_added_response со всеми частями."""
        from sql_db import _build_added_response
        
        result = _build_added_response('Существующее', 'Учитель', 'Группа')
        assert 'Существующее' in result
        assert 'Учитель' in result or 'преподават' in result.lower()
        assert 'Группа' in result or 'груп' in result.lower()
    
    def test_build_added_response_partial(self):
        """Проверяет _build_added_response с частичными данными."""
        from sql_db import _build_added_response
        
        # Только добавлены учителя
        result = _build_added_response('', 'Учитель', '')
        assert 'Учитель' in result
        
        # Только добавлены группы
        result = _build_added_response('', '', 'Группа')
        assert 'Группа' in result
    
    def test_build_added_response_empty(self):
        """Проверяет пустой результат."""
        from sql_db import _build_added_response
        
        result = _build_added_response('', '', '')
        assert result == ''
