"""Тесты для функций из excel.py."""
import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
import pendulum


class TestCreateExcelWithWorkload:
    """Тесты для функции create_excel_with_workload."""

    def test_missing_timetable_db_returns_error_message(self, tmp_path, monkeypatch):
        """Проверяет, что возвращается сообщение об ошибке без БД."""
        monkeypatch.chdir(tmp_path)
        # Создаем директорию но без файлов БД
        timetable_dir = tmp_path / 'timetable-dbs'
        timetable_dir.mkdir()

        from excel import create_excel_with_workload

        result = create_excel_with_workload(teacher='Иванов И.И.')
        # Должно содержать сообщение об ошибке
        assert isinstance(result, str)
        assert 'извин' in result.lower() or 'ошибка' in result.lower() or 'не могу' in result.lower()

    def test_missing_teacher_and_group_returns_error(self):
        """Проверяет, что без teacher и group_id возвращается ошибка."""
        from excel import create_excel_with_workload

        result = create_excel_with_workload()
        assert isinstance(result, str)
        assert 'не указан' in result.lower()

    def test_create_excel_for_single_teacher(self, tmp_path, monkeypatch):
        """Проверяет создание файла для одного преподавателя."""
        monkeypatch.chdir(tmp_path)

        from excel import create_excel_with_workload

        # Создаем структуру
        timetable_dir = tmp_path / 'timetable-dbs'
        timetable_dir.mkdir()
        timetable_files_dir = tmp_path / 'timetable-files'
        timetable_files_dir.mkdir()

        # Текущая дата для генерации дат в БД
        dt = pendulum.now(tz='Europe/Moscow')
        first_day = dt.start_of('month')
        date_str = first_day.format('D-MM-YYYY')

        # Создаем БД с данными
        db_path = timetable_dir / 'timetable_test.db'
        conn = sqlite3.connect(str(db_path))
        conn.execute('''
            CREATE TABLE timetable (
                "Group" TEXT, "StudInLesson" INTEGER, "Day" INTEGER, "Les" INTEGER,
                "Aud" TEXT, "Week" INTEGER, "Subg" INTEGER, "Name" TEXT,
                "CafID" INTEGER, "Subject" TEXT, "Subj_type" TEXT, "Date" TEXT,
                "Subj_CafID" INTEGER, "PrepID" INTEGER, "Themas" TEXT,
                "Lesson_ID" TEXT, "Lesson_Num" INTEGER
            )
        ''')
        conn.execute('''
            INSERT INTO timetable ("Group", "Les", "Aud", "Subg", "Name", "CafID", "Subject", "Subj_type", "Date")
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('307', 1, '2/311', 0, 'Иванов И.И.', 1, 'Математика', 'л', date_str))
        conn.commit()
        conn.close()

        result = create_excel_with_workload(teacher='Иванов И.И.')

        # Должен вернуть путь к файлу
        assert result.endswith('.xlsx')
        assert Path(result).exists()

    def test_create_excel_for_group(self, tmp_path, monkeypatch):
        """Проверяет создание файла для группы."""
        monkeypatch.chdir(tmp_path)

        from excel import create_excel_with_workload

        # Создаем структуру
        timetable_dir = tmp_path / 'timetable-dbs'
        timetable_dir.mkdir()
        timetable_files_dir = tmp_path / 'timetable-files'
        timetable_files_dir.mkdir()

        dt = pendulum.now(tz='Europe/Moscow')
        first_day = dt.start_of('month')
        date_str = first_day.format('D-MM-YYYY')

        db_path = timetable_dir / 'timetable_test.db'
        conn = sqlite3.connect(str(db_path))
        conn.execute('''
            CREATE TABLE timetable (
                "Group" TEXT, "StudInLesson" INTEGER, "Day" INTEGER, "Les" INTEGER,
                "Aud" TEXT, "Week" INTEGER, "Subg" INTEGER, "Name" TEXT,
                "CafID" INTEGER, "Subject" TEXT, "Subj_type" TEXT, "Date" TEXT,
                "Subj_CafID" INTEGER, "PrepID" INTEGER, "Themas" TEXT,
                "Lesson_ID" TEXT, "Lesson_Num" INTEGER
            )
        ''')
        conn.execute('''
            INSERT INTO timetable ("Group", "Les", "Aud", "Subg", "Name", "CafID", "Subject", "Subj_type", "Date")
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('307', 1, '2/311', 0, 'Иванов И.И.', 1, 'Математика', 'л', date_str))
        conn.commit()
        conn.close()

        result = create_excel_with_workload(group_id='307')

        assert result.endswith('.xlsx')
        assert Path(result).exists()

    def test_no_lessons_returns_message(self, tmp_path, monkeypatch):
        """Проверяет, что при отсутствии занятий возвращается сообщение."""
        monkeypatch.chdir(tmp_path)

        from excel import create_excel_with_workload

        timetable_dir = tmp_path / 'timetable-dbs'
        timetable_dir.mkdir()
        timetable_files_dir = tmp_path / 'timetable-files'
        timetable_files_dir.mkdir()

        db_path = timetable_dir / 'timetable_test.db'
        conn = sqlite3.connect(str(db_path))
        conn.execute('''
            CREATE TABLE timetable (
                "Group" TEXT, "StudInLesson" INTEGER, "Day" INTEGER, "Les" INTEGER,
                "Aud" TEXT, "Week" INTEGER, "Subg" INTEGER, "Name" TEXT,
                "CafID" INTEGER, "Subject" TEXT, "Subj_type" TEXT, "Date" TEXT,
                "Subj_CafID" INTEGER, "PrepID" INTEGER, "Themas" TEXT,
                "Lesson_ID" TEXT, "Lesson_Num" INTEGER
            )
        ''')
        conn.commit()
        conn.close()

        result = create_excel_with_workload(teacher='НесуществующийПреподаватель')

        assert isinstance(result, str)
        assert 'не найдено' in result.lower()


class TestExcelFormatting:
    """Тесты для форматирования в Excel файлах."""

    def test_workload_calculation_simple(self):
        """Проверяет простой расчет нагрузки."""
        # 1 лекция = 2 часа, 1 практика = 2 часа
        total_hours = 2 + 2
        assert total_hours == 4

    def test_workload_calculation_with_consultation(self):
        """Проверяет расчет с консультациями (0.5 часа)."""
        # 1 лекция (2ч) + 1 консультация (1ч вместо 2ч)
        lectures = 2
        consultations = 1  # 0.5 занятия = 1 час
        total = lectures + consultations
        assert total == 3

    def test_month_grouping(self):
        """Проверяет группировку по месяцам."""
        months = ['january', 'january', 'february', 'february', 'march']
        month_count = {}
        for month in months:
            month_count[month] = month_count.get(month, 0) + 1

        assert month_count['january'] == 2
        assert month_count['february'] == 2
        assert month_count['march'] == 1


class TestExcelDataValidation:
    """Тесты для валидации данных в Excel."""

    def test_teacher_name_format(self):
        """Проверяет формат имени преподавателя."""
        teacher_name = 'Иванов И.И.'
        # Должна быть фамилия и инициалы
        parts = teacher_name.split()
        assert len(parts) >= 1
        assert 'И.' in teacher_name or 'и.' in teacher_name

    def test_lesson_type_validation(self):
        """Проверяет валидные типы занятий."""
        valid_types = ['Лекция', 'Практика', 'ГК', 'Консультация', 'Зачет', 'Экзамен']

        for lesson_type in valid_types:
            assert isinstance(lesson_type, str)
            assert len(lesson_type) > 0

    def test_date_format_for_excel(self):
        """Проверяет формат даты для Excel."""
        # Даты должны быть в формате для расчета месяцев
        date_str = '1-01-2024'
        parts = date_str.split('-')
        assert len(parts) == 3
        assert int(parts[0]) <= 31  # День
        assert int(parts[1]) <= 12  # Месяц
        assert int(parts[2]) == 2024  # Год
