import sys
import os
import types

# Добавляем корень проекта в sys.path для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Мокаем тяжёлые внешние зависимости, которых может не быть в тестовом окружении
_MOCK_MODULES = [
    'loguru', 'vkbottle', 'vkbottle.bot', 'aiogram', 'aiogram.exceptions',
    'aiogram.types', 'aiogram.filters', 'nextcord', 'nextcord.ext',
    'nextcord.ext.commands', 'yagmail', 'chardet', 'pendulum',
    'pandas', 'github', 'icalendar', 'xlsxwriter',
    'aiohttp', 'aiohttp.client_exceptions',
]

for mod_name in _MOCK_MODULES:
    if mod_name not in sys.modules:
        mock_mod = types.ModuleType(mod_name)
        # Добавляем заглушки для часто используемых атрибутов
        mock_mod.__dict__.setdefault('__all__', [])
        sys.modules[mod_name] = mock_mod

# loguru.logger нужен многими модулями
_loguru = sys.modules['loguru']


class _MockLogger:
    """Заглушка для loguru.logger."""
    def log(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def critical(self, *a, **kw): pass
    def debug(self, *a, **kw): pass
    def remove(self, *a, **kw): pass
    def add(self, *a, **kw): return 0
    def level(self, *a, **kw): return None
    def catch(self, *a, **kw):
        if a and callable(a[0]):
            return a[0]
        return lambda fn: fn


_loguru.logger = _MockLogger()

# vkbottle.API нужен в sql_db.py
sys.modules['vkbottle'].API = lambda *a, **k: None

# chardet.detect нужен в other.py
sys.modules['chardet'].detect = lambda *a, **k: {'encoding': 'utf-8', 'confidence': 1.0}

# pendulum — заглушки для основных методов
_pendulum = sys.modules['pendulum']
_pendulum.now = lambda *a, **kw: None
_pendulum.set_locale = lambda *a, **kw: None
_pendulum.from_format = lambda *a, **kw: None

# pandas — заглушка для read_csv
_pandas = sys.modules['pandas']
_pandas.read_csv = lambda *a, **kw: None

# github.Github
_github = sys.modules['github']
_github.Github = lambda *a, **k: None

# icalendar
_ical = sys.modules['icalendar']
_ical.Calendar = type('Calendar', (), {'add': lambda s, *a, **k: None, 'add_component': lambda s, *a: None, 'to_ical': lambda s: b''})
_ical.Event = type('Event', (), {'add': lambda s, *a, **k: None, '__setitem__': lambda s, k, v: None})

# pytest-asyncio конфигурация для async тестов
import pytest

pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope='session')
def event_loop():
    """Создает event loop для async тестов."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
