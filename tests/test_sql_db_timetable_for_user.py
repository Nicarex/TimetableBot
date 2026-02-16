"""Тесты для getting_timetable_for_user, getting_workload_for_user,
getting_workload_excel_for_user, get_all_months_from_timetable_db из sql_db.py."""
import sqlite3
import pytest
from unittest.mock import patch
from pathlib import Path


def _setup_dbs(tmp_path, timetable_rows=None, users=None):
    """Создаёт БД расписания и user_settings для тестов."""
    # Timetable DB
    db_dir = tmp_path / 'timetable-dbs'
    db_dir.mkdir(exist_ok=True)
    timetable_db = db_dir / 'timetable_test.db'
    conn = sqlite3.connect(str(timetable_db))
    conn.execute('''CREATE TABLE timetable (
        "Group" TEXT, "StudInLesson" INTEGER, "Day" INTEGER, "Les" INTEGER,
        "Aud" TEXT, "Week" INTEGER, "Subg" INTEGER, "Name" TEXT,
        "CafID" INTEGER, "Subject" TEXT, "Subj_type" TEXT, "Date" TEXT,
        "Subj_CafID" INTEGER, "PrepID" INTEGER, "Themas" TEXT,
        "Lesson_ID" TEXT, "Lesson_Num" INTEGER)''')
    for r in (timetable_rows or []):
        conn.execute('''INSERT INTO timetable ("Group", "Les", "Aud", "Subg", "Name",
            "CafID", "Subject", "Subj_type", "Date", "Themas") VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (r.get('Group', '307'), r.get('Les', 1), r.get('Aud', '101'),
             r.get('Subg', 0), r.get('Name', 'Иванов'), r.get('CafID', 1),
             r.get('Subject', 'Математика'), r.get('Subj_type', 'л'),
             r.get('Date', '1-01-2024'), r.get('Themas', None)))
    conn.commit()
    conn.close()

    # User settings DB
    dbs_dir = tmp_path / 'dbs'
    dbs_dir.mkdir(exist_ok=True)
    user_db = dbs_dir / 'user_settings.db'
    conn = sqlite3.connect(str(user_db))
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute("""CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL,
        platform_id TEXT NOT NULL, notification INTEGER NOT NULL DEFAULT 1,
        lesson_time INTEGER NOT NULL DEFAULT 1, UNIQUE(platform, platform_id))""")
    conn.execute("""CREATE TABLE user_groups (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        group_id TEXT NOT NULL, PRIMARY KEY (user_id, group_id))""")
    conn.execute("""CREATE TABLE user_teachers (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        teacher TEXT NOT NULL, PRIMARY KEY (user_id, teacher))""")
    for u in (users or []):
        conn.execute('INSERT INTO users (platform, platform_id, notification, lesson_time) VALUES (?,?,?,?)',
                     (u['platform'], u['platform_id'], u.get('notification', 1), u.get('lesson_time', 1)))
        uid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        for t in u.get('teachers', []):
            conn.execute('INSERT INTO user_teachers (user_id, teacher) VALUES (?,?)', (uid, t))
        for g in u.get('groups', []):
            conn.execute('INSERT INTO user_groups (user_id, group_id) VALUES (?,?)', (uid, g))
    conn.commit()
    conn.close()

    # timetable-files dir
    (tmp_path / 'timetable-files').mkdir(exist_ok=True)


# ─── getting_timetable_for_user ───

class TestGettingTimetableForUser:
    def test_no_platform(self):
        from sql_db import getting_timetable_for_user
        result = getting_timetable_for_user()
        assert 'ошибка' in result.lower() or 'Произошла' in result

    def test_no_user(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_dbs(tmp_path)
        from sql_db import getting_timetable_for_user
        result = getting_timetable_for_user(email='nobody@mail.com')
        assert 'Нет сохраненных' in result

    def test_user_no_saved_groups_or_teachers(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_dbs(tmp_path, users=[
            {'platform': 'email', 'platform_id': 'test@mail.com'}
        ])
        from sql_db import getting_timetable_for_user
        result = getting_timetable_for_user(email='test@mail.com')
        assert 'Нет сохраненных' in result

    def test_user_with_teacher(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from timetable import date_request
        monday = date_request(day_of_week=0, for_db='YES')
        _setup_dbs(tmp_path,
            timetable_rows=[{'Name': 'Иванов', 'Date': monday, 'Subject': 'Физика', 'Group': '307', 'Aud': ' 101'}],
            users=[{'platform': 'email', 'platform_id': 'test@mail.com', 'teachers': ['Иванов']}]
        )
        from sql_db import getting_timetable_for_user
        result = getting_timetable_for_user(email='test@mail.com')
        assert 'Иванов' in result or 'Физика' in result

    def test_email_returns_html(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from timetable import date_request
        monday = date_request(day_of_week=0, for_db='YES')
        _setup_dbs(tmp_path,
            timetable_rows=[{'Name': 'Иванов', 'Date': monday, 'Group': '307', 'Aud': ' 101'}],
            users=[{'platform': 'email', 'platform_id': 'test@mail.com', 'teachers': ['Иванов']}]
        )
        from sql_db import getting_timetable_for_user
        result = getting_timetable_for_user(email='test@mail.com')
        # Email возвращает HTML
        assert '<' in result


# ─── getting_workload_for_user ───

class TestGettingWorkloadForUser:
    def test_no_platform(self):
        from sql_db import getting_workload_for_user
        result = getting_workload_for_user()
        assert 'ошибка' in result.lower() or 'Произошла' in result

    def test_no_user(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_dbs(tmp_path)
        from sql_db import getting_workload_for_user
        result = getting_workload_for_user(email='nobody@mail.com')
        assert 'Нет сохраненных' in result

    def test_no_teachers(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_dbs(tmp_path, users=[
            {'platform': 'email', 'platform_id': 'test@mail.com', 'groups': ['307']}
        ])
        from sql_db import getting_workload_for_user
        result = getting_workload_for_user(email='test@mail.com')
        assert 'Нет сохраненных преподавателей' in result


# ─── getting_workload_excel_for_user ───

class TestGettingWorkloadExcelForUser:
    def test_no_platform(self):
        from sql_db import getting_workload_excel_for_user
        result = getting_workload_excel_for_user()
        assert result == []

    def test_no_user(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_dbs(tmp_path)
        from sql_db import getting_workload_excel_for_user
        result = getting_workload_excel_for_user(email='nobody@mail.com')
        assert result == []

    def test_generates_xlsx_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        import pendulum
        dt = pendulum.now(tz='Europe/Moscow')
        first_day = dt.start_of('month')
        date_str = first_day.format('D-MM-YYYY')
        _setup_dbs(tmp_path,
            timetable_rows=[{'Name': 'Иванов', 'Date': date_str, 'Group': '307', 'Aud': '101'}],
            users=[{'platform': 'email', 'platform_id': 'test@mail.com',
                    'teachers': ['Иванов'], 'groups': ['307']}]
        )
        from sql_db import getting_workload_excel_for_user
        result = getting_workload_excel_for_user(email='test@mail.com')
        assert len(result) == 2  # 1 для teacher + 1 для group
        for f in result:
            assert f.endswith('.xlsx')


# ─── get_all_months_from_timetable_db ───

class TestGetAllMonthsFromTimetableDb:
    def test_no_db(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'timetable-dbs').mkdir()
        from sql_db import get_all_months_from_timetable_db
        result = get_all_months_from_timetable_db()
        assert result == []

    def test_returns_sorted_months(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_dbs(tmp_path, timetable_rows=[
            {'Date': '1-03-2024'},
            {'Date': '15-01-2024'},
            {'Date': '5-02-2024'},
            {'Date': '20-01-2024'},  # дубликат месяца
        ])
        from sql_db import get_all_months_from_timetable_db
        result = get_all_months_from_timetable_db()
        assert result == [(1, 2024), (2, 2024), (3, 2024)]

    def test_empty_db(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_dbs(tmp_path, timetable_rows=[])
        from sql_db import get_all_months_from_timetable_db
        result = get_all_months_from_timetable_db()
        assert result == []
