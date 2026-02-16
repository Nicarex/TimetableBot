"""Тесты для timetable(), workload(), show_all_types_of_lessons_in_db() из timetable.py."""
import sqlite3
import pytest
from unittest.mock import patch
from pathlib import Path


def _create_timetable_db(db_path, rows):
    """Создаёт БД расписания с заданными строками.
    rows: list of dict с ключами Group, Les, Aud, Subg, Name, CafID, Subject, Subj_type, Date, Themas, Week, Day.
    """
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
    for r in rows:
        conn.execute('''
            INSERT INTO timetable ("Group", "Les", "Aud", "Subg", "Name", "CafID",
                                   "Subject", "Subj_type", "Date", "Themas", "Week", "Day")
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r.get('Group', '307'), r.get('Les', 1), r.get('Aud', '2/311'),
            r.get('Subg', 0), r.get('Name', 'Иванов И.И.'), r.get('CafID', 1),
            r.get('Subject', 'Математика'), r.get('Subj_type', 'л'),
            r.get('Date', '1-01-2024'), r.get('Themas', None),
            r.get('Week', 1), r.get('Day', 1),
        ))
    conn.commit()
    conn.close()


class TestTimetableFunction:
    """Тесты для функции timetable()."""

    def test_no_db_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'timetable-dbs').mkdir()
        (tmp_path / 'timetable-files').mkdir()
        from timetable import timetable
        result = timetable(teacher='Иванов И.И.')
        assert 'извинит' in result.lower() or 'не могу' in result.lower()

    def test_no_teacher_and_no_group_returns_false(self, tmp_path, monkeypatch):
        """Без teacher и group_id возвращается False (или ошибка если нет БД)."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()
        # Нужна БД чтобы дойти до проверки teacher/group
        conn = __import__('sqlite3').connect(str(db_dir / 'timetable_test.db'))
        conn.execute('''CREATE TABLE timetable ("Group" TEXT, "Name" TEXT, "Les" INTEGER,
            "Date" TEXT, "Aud" TEXT, "Subg" INTEGER, "Subject" TEXT, "Subj_type" TEXT,
            "CafID" INTEGER, "Themas" TEXT, "Week" INTEGER, "Day" INTEGER,
            "StudInLesson" INTEGER, "Subj_CafID" INTEGER, "PrepID" INTEGER,
            "Lesson_ID" TEXT, "Lesson_Num" INTEGER)''')
        conn.commit()
        conn.close()
        from timetable import timetable
        result = timetable()
        assert result is False

    def test_teacher_no_lessons_current_week(self, tmp_path, monkeypatch):
        """Преподаватель без занятий на текущую неделю."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()
        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Name': 'Петров П.П.', 'Date': '1-01-2020'},
        ])
        from timetable import timetable
        result = timetable(teacher='Иванов И.И.')
        assert 'Не найдено занятий' in result
        assert 'Преподаватель Иванов И.И.' in result

    def test_group_no_lessons_current_week(self, tmp_path, monkeypatch):
        """Группа без занятий на текущую неделю."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()
        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Group': '999', 'Date': '1-01-2020'},
        ])
        from timetable import timetable
        result = timetable(group_id='307')
        assert 'Не найдено занятий' in result
        assert 'Группа 307' in result

    def test_teacher_with_lessons(self, tmp_path, monkeypatch):
        """Преподаватель с занятиями на текущую неделю."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()

        from timetable import date_request
        monday_date = date_request(day_of_week=0, for_db='YES')

        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Name': 'Иванов И.И.', 'Date': monday_date, 'Les': 1,
             'Subject': 'Математика', 'Subj_type': 'л', 'Group': '307', 'Aud': ' 2/311'},
        ])
        from timetable import timetable
        result = timetable(teacher='Иванов И.И.')
        assert 'Преподаватель Иванов И.И.' in result
        assert 'Математика' in result
        assert '307' in result

    def test_group_with_lessons(self, tmp_path, monkeypatch):
        """Группа с занятиями на текущую неделю."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()

        from timetable import date_request
        monday_date = date_request(day_of_week=0, for_db='YES')

        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Group': '307', 'Date': monday_date, 'Les': 1,
             'Subject': 'Физика', 'Subj_type': 'пз', 'Name': 'Петров П.П.', 'Aud': ' 3/101'},
        ])
        from timetable import timetable
        result = timetable(group_id='307')
        assert 'Группа 307' in result
        assert 'Физика' in result
        assert 'Петров П.П.' in result

    def test_teacher_with_lesson_time_hidden(self, tmp_path, monkeypatch):
        """Расписание без отображения времени."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()

        from timetable import date_request
        monday_date = date_request(day_of_week=0, for_db='YES')

        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Name': 'Иванов И.И.', 'Date': monday_date, 'Les': 1,
             'Subject': 'Математика', 'Subj_type': 'л', 'Group': '307', 'Aud': ' 2/311'},
        ])
        from timetable import timetable
        result_with_time = timetable(teacher='Иванов И.И.')
        result_without_time = timetable(teacher='Иванов И.И.', lesson_time='YES')
        # Без времени строка должна быть короче
        assert len(result_without_time) <= len(result_with_time)

    def test_teacher_with_themas(self, tmp_path, monkeypatch):
        """Преподаватель с темой занятия."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()

        from timetable import date_request
        monday_date = date_request(day_of_week=0, for_db='YES')

        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Name': 'Иванов И.И.', 'Date': monday_date, 'Les': 1,
             'Subject': 'Математика', 'Subj_type': 'л', 'Group': '307',
             'Aud': ' 2/311', 'Themas': 'Интегралы'},
        ])
        from timetable import timetable
        result = timetable(teacher='Иванов И.И.')
        assert 'Интегралы' in result

    def test_not_enough_dbs_for_previous(self, tmp_path, monkeypatch):
        """use_previous_timetable_db с одной БД."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()
        _create_timetable_db(db_dir / 'timetable_test.db', [])
        from timetable import timetable
        result = timetable(teacher='Иванов И.И.', use_previous_timetable_db='YES')
        assert 'Недостаточно' in result


class TestWorkloadFunction:
    """Тесты для функции workload()."""

    def test_no_db_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'timetable-dbs').mkdir()
        from timetable import workload
        result = workload(teacher='Иванов И.И.')
        assert 'извинит' in result.lower() or 'не могу' in result.lower()

    def test_workload_no_lessons(self, tmp_path, monkeypatch):
        """Нагрузка для преподавателя без занятий."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        _create_timetable_db(db_dir / 'timetable_test.db', [])
        from timetable import workload
        result = workload(teacher='Иванов И.И.')
        assert 'Преподаватель Иванов И.И.' in result
        assert '0 ч.' in result

    def test_workload_with_lessons(self, tmp_path, monkeypatch):
        """Нагрузка с занятиями в текущем месяце."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()

        from timetable import date_request
        import pendulum
        dt = pendulum.now(tz='Europe/Moscow')
        first_day = dt.start_of('month')
        date_str = first_day.format('D-MM-YYYY')

        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Name': 'Иванов И.И.', 'Date': date_str, 'Les': 1, 'Subj_type': 'л'},
            {'Name': 'Иванов И.И.', 'Date': date_str, 'Les': 2, 'Subj_type': 'пз'},
        ])
        from timetable import workload
        result = workload(teacher='Иванов И.И.')
        assert 'Преподаватель Иванов И.И.' in result
        assert '4 ч.' in result  # 2 пары * 2 часа
        assert 'Типы занятий' in result

    def test_workload_consultation_half_counted(self, tmp_path, monkeypatch):
        """ГК/Консультация/Проверка считаются за 0.5 занятия (1 час)."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()

        import pendulum
        dt = pendulum.now(tz='Europe/Moscow')
        first_day = dt.start_of('month')
        date_str = first_day.format('D-MM-YYYY')

        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Name': 'Иванов И.И.', 'Date': date_str, 'Les': 1, 'Subj_type': 'ГК'},
            {'Name': 'Иванов И.И.', 'Date': date_str, 'Les': 2, 'Subj_type': 'Консультация'},
        ])
        from timetable import workload
        result = workload(teacher='Иванов И.И.')
        assert '2 ч.' in result  # 2 * 0.5 * 2 = 2 часа


class TestShowAllTypesOfLessons:
    """Тесты для функции show_all_types_of_lessons_in_db()."""

    def test_no_db_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'timetable-dbs').mkdir()
        from timetable import show_all_types_of_lessons_in_db
        result = show_all_types_of_lessons_in_db()
        assert 'извинит' in result.lower() or 'не могу' in result.lower()

    def test_shows_types(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Subj_type': 'л', 'Date': '1-01-2024'},
            {'Subj_type': 'л', 'Date': '2-01-2024'},
            {'Subj_type': 'пз', 'Date': '1-01-2024'},
        ])
        from timetable import show_all_types_of_lessons_in_db
        result = show_all_types_of_lessons_in_db()
        assert 'Типы занятий' in result
        assert 'л - 2' in result
        assert 'пз - 1' in result
