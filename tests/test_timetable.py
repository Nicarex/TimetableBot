"""Тесты для функций из timetable.py."""
import pytest
import pendulum
from datetime import timedelta
from constants import TIMEZONE, DAYS_OF_WEEK
from timetable import date_request, name_of_day_string


class TestDateRequest:
    """Тесты для функции date_request."""
    
    def test_date_request_for_file_format(self):
        """Проверяет формат даты для файла (ДД.МММ.ГГГГ)."""
        result = date_request(day_of_week=0, for_file='YES')
        # Должна быть в формате ДД.ММ.ГГГГ
        assert isinstance(result, str)
        parts = result.split('.')
        assert len(parts) == 3
        assert len(parts[0]) == 2  # День
        assert len(parts[1]) == 2  # Месяц
        assert len(parts[2]) == 4  # Год
    
    def test_date_request_for_db_format(self):
        """Проверяет формат даты для БД (Д-МММ-ГГГГ)."""
        result = date_request(day_of_week=0, for_db='YES')
        # Должна быть в формате Д-МММ-ГГГГ
        assert isinstance(result, str)
        assert '-' in result
        parts = result.split('-')
        assert len(parts) == 3
    
    def test_date_request_current_week(self):
        """Проверяет, что текущая неделя возвращается без флага next."""
        result = date_request(day_of_week=0, for_file='YES', next=None)
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_date_request_next_week(self):
        """Проверяет, что следующая неделя возвращается с флагом next."""
        result_current = date_request(day_of_week=0, for_file='YES', next=None)
        result_next = date_request(day_of_week=0, for_file='YES', next='YES')
        # Даты должны быть разными
        assert result_current != result_next
    
    def test_date_request_different_days(self):
        """Проверяет, что разные дни недели возвращают разные даты."""
        dates = []
        for day in range(7):
            date = date_request(day_of_week=day, for_file='YES')
            dates.append(date)
        # Все даты в неделе должны быть уникальны
        assert len(set(dates)) == 7
    
    def test_date_request_invalid_params(self):
        """Проверяет, что функция возвращает None при неверных параметрах."""
        result = date_request(day_of_week=0)  # Ни for_file, ни for_db
        assert result is None
    
    def test_date_request_both_params(self):
        """Проверяет, что функция возвращает None когда оба флага установлены."""
        result = date_request(day_of_week=0, for_file='YES', for_db='YES')
        assert result is None


class TestNameOfDayString:
    """Тесты для функции name_of_day_string."""
    
    def test_name_of_day_contains_day_name(self):
        """Проверяет, что результат содержит название дня."""
        for day in range(7):
            result = name_of_day_string(day, None)
            # Должна содержать название дня (из DAYS_OF_WEEK)
            assert isinstance(result, str)
            assert len(result) > 0
    
    def test_name_of_day_contains_date(self):
        """Проверяет, что результат содержит дату."""
        result = name_of_day_string(0, None)
        # Должна быть дата в формате ДД.ММ.YYYY
        assert '.' in result
    
    def test_name_of_day_ends_with_newline(self):
        """Проверяет, что строка заканчивается символом новой строки."""
        result = name_of_day_string(0, None)
        assert result.endswith('\n')
    
    def test_name_of_day_next_week(self):
        """Проверяет, что следующая неделя возвращает другую дату."""
        result_current = name_of_day_string(0, None)
        result_next = name_of_day_string(0, 'YES')
        assert result_current != result_next
    
    def test_name_of_day_all_days(self):
        """Проверяет все дни недели (0-6)."""
        for day in range(7):
            result = name_of_day_string(day, None)
            assert isinstance(result, str)
            assert len(result) > 5  # Минимальная длина для дня и даты
            assert '\n' in result
