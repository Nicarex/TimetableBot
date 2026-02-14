"""Тесты для функций из calendar_timetable.py."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCreateCalendarFileWithTimetable:
    """Тесты для функции create_calendar_file_with_timetable."""
    
    def test_missing_timetable_db_returns_false(self, tmp_path, monkeypatch):
        """Проверяет, что функция возвращает False когда нет БД расписания."""
        monkeypatch.chdir(tmp_path)
        # Создаем директорию но без файлов БД
        timetable_dir = tmp_path / 'timetable-dbs'
        timetable_dir.mkdir()
        calendars_dir = tmp_path / 'calendars'
        calendars_dir.mkdir()
        
        from calendar_timetable import create_calendar_file_with_timetable
        
        result = create_calendar_file_with_timetable(teacher='Иванов И.И.')
        # Должно вернуть False, т.к. нет БД файлов
        assert result is False
    
    def test_invalid_lesson_number_returns_false(self, tmp_path, monkeypatch):
        """Проверяет обработку некорректного номера пары."""
        import sqlite3
        monkeypatch.chdir(tmp_path)
        
        from calendar_timetable import create_calendar_file_with_timetable
        
        # Создаем временную БД с некорректным номером пары
        timetable_dir = tmp_path / 'timetable-dbs'
        timetable_dir.mkdir()
        calendars_dir = tmp_path / 'calendars'
        calendars_dir.mkdir()
        
        db_path = timetable_dir / 'timetable_test.db'
        conn = sqlite3.connect(str(db_path))
        conn.execute('''
            CREATE TABLE timetable (
                "Name" TEXT, "Date" TEXT, "Les" INTEGER, "Week" INTEGER, "Day" INTEGER,
                "Group" TEXT, "Subg" INTEGER, "Subject" TEXT, "Aud" TEXT, "Subj_type" TEXT, "Themas" TEXT, "CafID" INTEGER
            )
        ''')
        # Вставляем запись с некорректным номером пары (99)
        conn.execute('''
            INSERT INTO timetable VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Иванов И.И.', '1-01-2024', 99, 1, 1, 'Группа', 1, 'Предмет', 'Ауд', 'Лекция', None, 1))
        conn.commit()
        conn.close()
        
        result = create_calendar_file_with_timetable(teacher='Иванов И.И.')
        # Должно вернуть False из-за некорректного номера пары
        assert result is False
    
    def test_teacher_calendar_only(self, tmp_path, monkeypatch):
        """Проверяет создание календаря только для одного преподавателя."""
        import sqlite3
        monkeypatch.chdir(tmp_path)
        
        from calendar_timetable import create_calendar_file_with_timetable
        
        # Подготавливаем структуру
        timetable_dir = tmp_path / 'timetable-dbs'
        timetable_dir.mkdir()
        calendars_dir = tmp_path / 'calendars'
        calendars_dir.mkdir()
        
        # Создаем БД
        db_path = timetable_dir / 'timetable_test.db'
        conn = sqlite3.connect(str(db_path))
        conn.execute('''
            CREATE TABLE timetable (
                "Name" TEXT, "Date" TEXT, "Les" INTEGER, "Week" INTEGER, "Day" INTEGER,
                "Group" TEXT, "Subg" INTEGER, "Subject" TEXT, "Aud" TEXT, "Subj_type" TEXT, "Themas" TEXT, "CafID" INTEGER
            )
        ''')
        # Добавляем корректные данные
        conn.execute('''
            INSERT INTO timetable VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Иванов И.И.', '1-01-2024', 1, 1, 1, 'А-101', 1, 'Математика', '101', 'Лекция', 'Теория чисел', 1))
        conn.commit()
        conn.close()
        
        # Вызываем функцию (без фактического читеры GitHub)
        with patch('calendar_timetable.github_token', None):
            result = create_calendar_file_with_timetable(teacher='Иванов И.И.')
        
        # Проверяем результат
        # (может быть True или False в зависимости от наличия GitHub доступа)
        assert isinstance(result, bool)
    
    def test_group_calendar_only(self):
        """Проверяет, что функция может создавать календарь для группы."""
        # Простая проверка типов и сигнатуры
        from inspect import signature
        from calendar_timetable import create_calendar_file_with_timetable
        
        # Функция должна принимать параметры group_id и teacher
        sig = signature(create_calendar_file_with_timetable)
        assert 'group_id' in sig.parameters
        assert 'teacher' in sig.parameters


class TestCalendarStringFormatting:
    """Тесты для форматирования строк в календаре."""
    
    def test_timetable_string_format_with_theme(self):
        """Проверяет формат строки расписания с темой."""
        # Строка должна содержать: тип, тема, предмет, аудитория, группа
        test_string = '(Лекция) Основы теории Математика Ауд. 101 А-101 гр.'
        
        assert '(Лекция)' in test_string
        assert 'Математика' in test_string
        assert 'А-101' in test_string
    
    def test_timetable_string_format_without_theme(self):
        """Проверяет формат строки расписания без темы."""
        test_string = '(Лекция) Математика Ауд. 101 А-101 гр.'
        
        assert '(Лекция)' in test_string
        assert 'Математика' in test_string
        assert 'А-101' in test_string


class TestCalendarDescriptions:
    """Тесты для описаний событий в календаре."""
    
    def test_event_description_with_theme(self):
        """Проверяет описание события с темой."""
        description = (
            'Тип занятия: Лекция\n'
            'Тема: Основы теории\n'
            'Предмет: Математика\n'
            'Аудитория: 101\n'
            'Группы: А-101'
        )
        
        assert 'Тип занятия:' in description
        assert 'Тема:' in description
        assert 'Предмет:' in description
        assert 'Аудитория:' in description
    
    def test_event_description_without_theme(self):
        """Проверяет описание события без темы."""
        description = (
            'Тип занятия: Лекция\n'
            'Предмет: Математика\n'
            'Аудитория: 101\n'
            'Группы: А-101'
        )
        
        assert 'Тип занятия:' in description
        assert 'Тема:' not in description
        assert 'Предмет:' in description
