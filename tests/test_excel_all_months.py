"""Тесты для create_excel_with_workload_all_months и вспомогательных функций excel.py."""
import sqlite3
import pytest
from pathlib import Path
import pendulum


def _create_timetable_db(db_path, rows):
    conn = sqlite3.connect(str(db_path))
    conn.execute('''CREATE TABLE timetable (
        "Group" TEXT, "StudInLesson" INTEGER, "Day" INTEGER, "Les" INTEGER,
        "Aud" TEXT, "Week" INTEGER, "Subg" INTEGER, "Name" TEXT,
        "CafID" INTEGER, "Subject" TEXT, "Subj_type" TEXT, "Date" TEXT,
        "Subj_CafID" INTEGER, "PrepID" INTEGER, "Themas" TEXT,
        "Lesson_ID" TEXT, "Lesson_Num" INTEGER)''')
    for r in rows:
        conn.execute('''INSERT INTO timetable ("Group", "Les", "Aud", "Subg", "Name",
            "CafID", "Subject", "Subj_type", "Date") VALUES (?,?,?,?,?,?,?,?,?)''',
            (r.get('Group', '307'), r.get('Les', 1), r.get('Aud', '101'),
             r.get('Subg', 0), r.get('Name', 'Иванов И.И.'), r.get('CafID', 1),
             r.get('Subject', 'Математика'), r.get('Subj_type', 'л'), r.get('Date', '1-01-2024')))
    conn.commit()
    conn.close()


class TestCreateExcelWithWorkloadAllMonths:
    def test_no_teacher_no_group(self):
        from excel import create_excel_with_workload_all_months
        result = create_excel_with_workload_all_months()
        assert 'Не указан' in result

    def test_empty_months_list(self):
        from excel import create_excel_with_workload_all_months
        result = create_excel_with_workload_all_months(teacher='Иванов', all_months=[])
        assert 'Нет доступных' in result

    def test_no_db(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'timetable-dbs').mkdir()
        from excel import create_excel_with_workload_all_months
        result = create_excel_with_workload_all_months(teacher='Иванов', all_months=[(1, 2024)])
        assert 'извинит' in result.lower() or 'не могу' in result.lower()

    def test_creates_xlsx(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()
        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Name': 'Иванов И.И.', 'Date': '15-01-2024', 'Les': 1, 'Subj_type': 'л'},
            {'Name': 'Иванов И.И.', 'Date': '5-02-2024', 'Les': 2, 'Subj_type': 'пз'},
        ])
        from excel import create_excel_with_workload_all_months
        result = create_excel_with_workload_all_months(
            teacher='Иванов И.И.', all_months=[(1, 2024), (2, 2024)])
        assert result.endswith('.xlsx')
        assert Path(result).exists()

    def test_no_lessons_in_any_month(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()
        _create_timetable_db(db_dir / 'timetable_test.db', [])
        from excel import create_excel_with_workload_all_months
        result = create_excel_with_workload_all_months(
            teacher='Иванов И.И.', all_months=[(1, 2024)])
        assert 'Не найдено' in result

    def test_for_group(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()
        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Group': '307', 'Date': '15-01-2024'},
        ])
        from excel import create_excel_with_workload_all_months
        result = create_excel_with_workload_all_months(
            group_id='307', all_months=[(1, 2024)])
        assert result.endswith('.xlsx')


class TestExcelHelpers:
    """Тесты для _resolve_filter, _get_days_of_month."""

    def test_resolve_filter_teacher(self):
        from excel import _resolve_filter
        col, val, label, other_col, other_label = _resolve_filter('Иванов', None)
        assert col == 'Name'
        assert val == 'Иванов'
        assert 'Преподаватель' in label

    def test_resolve_filter_group(self):
        from excel import _resolve_filter
        col, val, label, other_col, other_label = _resolve_filter(None, '307')
        assert col == 'Group'
        assert val == '307'
        assert 'Группа' in label

    def test_get_days_of_month(self):
        from excel import _get_days_of_month
        first_day = pendulum.datetime(2024, 1, 1, tz='Europe/Moscow')
        days = _get_days_of_month(first_day)
        assert len(days) == 31  # Январь

    def test_get_days_of_month_february(self):
        from excel import _get_days_of_month
        first_day = pendulum.datetime(2024, 2, 1, tz='Europe/Moscow')
        days = _get_days_of_month(first_day)
        assert len(days) == 29  # 2024 - високосный год


class TestCreateExcelWithWorkloadMonthYear:
    """Тесты для create_excel_with_workload с параметром month_year."""

    def test_specific_month_year(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()
        _create_timetable_db(db_dir / 'timetable_test.db', [
            {'Name': 'Иванов И.И.', 'Date': '15-03-2024', 'Les': 1, 'Subj_type': 'л'},
        ])
        from excel import create_excel_with_workload
        result = create_excel_with_workload(teacher='Иванов И.И.', month_year=(3, 2024))
        assert result.endswith('.xlsx')
        assert '2024_03' in result

    def test_next_month(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        (tmp_path / 'timetable-files').mkdir()
        _create_timetable_db(db_dir / 'timetable_test.db', [])
        from excel import create_excel_with_workload
        result = create_excel_with_workload(teacher='Иванов И.И.', next='YES')
        # Нет занятий, но файл не создан
        assert 'Не найдено' in result or result.endswith('.xlsx')
