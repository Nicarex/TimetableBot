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
from datetime import datetime, timedelta

class _MockDateTime:
    """Mock для pendulum DateTime."""
    def __init__(self, dt=None):
        self.dt = dt if dt else datetime.now()
    
    def start_of(self, unit):
        if unit == 'week':
            # Понедельник текущей недели
            days_since_monday = self.dt.weekday()
            new_dt = self.dt - timedelta(days=days_since_monday)
            return _MockDateTime(new_dt.replace(hour=0, minute=0, second=0))
        elif unit == 'month':
            return _MockDateTime(self.dt.replace(day=1, hour=0, minute=0, second=0))
        return self
    
    def next(self, day_name):
        # Следующий понедельник (day_name == MONDAY)
        days_ahead = 7 - self.dt.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_dt = self.dt + timedelta(days=days_ahead)
        return _MockDateTime(next_dt)
    
    def add(self, **kwargs):
        new_dt = self.dt
        if 'months' in kwargs:
            month = self.dt.month + kwargs['months']
            year = self.dt.year
            while month > 12:
                month -= 12
                year += 1
            new_dt = self.dt.replace(year=year, month=month)
        elif 'years' in kwargs:
            new_dt = self.dt.replace(year=self.dt.year + kwargs['years'])
        elif 'days' in kwargs:
            new_dt = self.dt + timedelta(days=kwargs['days'])
        return _MockDateTime(new_dt)
    
    def subtract(self, **kwargs):
        new_dt = self.dt
        if 'years' in kwargs:
            new_dt = self.dt.replace(year=self.dt.year - kwargs['years'])
        return _MockDateTime(new_dt)
    
    def format(self, fmt_str):
        if fmt_str == 'D-MM-YYYY':
            # Формат без ведущего нуля в дне
            day = str(self.dt.day)
            month = f'{self.dt.month:02d}'
            year = self.dt.year
            return f'{day}-{month}-{year}'
        elif fmt_str == 'DD.MM.YYYY':
            return self.dt.strftime('%d.%m.%Y')
        elif fmt_str == 'MMMM':
            months = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                     'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
            return months[self.dt.month - 1]
        return str(self.dt)
    
    def isoweekday(self):
        return self.dt.isoweekday()
    
    def __add__(self, other):
        """Поддержка операции _MockDateTime + timedelta."""
        if isinstance(other, timedelta):
            return _MockDateTime(self.dt + other)
        return NotImplemented
    
    def __radd__(self, other):
        """Поддержка операции timedelta + _MockDateTime."""
        if isinstance(other, timedelta):
            return _MockDateTime(other + self.dt)
        return NotImplemented
    
    def __sub__(self, other):
        """Поддержка операции _MockDateTime - timedelta и _MockDateTime - _MockDateTime."""
        if isinstance(other, timedelta):
            return _MockDateTime(self.dt - other)
        elif isinstance(other, _MockDateTime):
            return self.dt - other.dt
        return NotImplemented
    
    def __eq__(self, other):
        if isinstance(other, _MockDateTime):
            return self.dt == other.dt
        return False

_pendulum = sys.modules['pendulum']
_pendulum.now = lambda *a, **kw: _MockDateTime()
_pendulum.set_locale = lambda *a, **kw: None
_pendulum.from_format = lambda *a, **kw: _MockDateTime()
_pendulum.MONDAY = 'MONDAY'
_pendulum.SUNDAY = 'SUNDAY'

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
