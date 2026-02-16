"""Тесты для функций настроек пользователя в sql_db.py:
enable_and_disable_notifications, enable_and_disable_lesson_time,
delete_all_saved_groups_and_teachers, display_saved_settings,
search_group_and_teacher_in_request, create_db_user_settings, create_db_calendars_list.
"""
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


def _setup_user_settings_db(db_path):
    """Создаёт БД user_settings.db с правильной схемой."""
    conn = sqlite3.connect(str(db_path))
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL, platform_id TEXT NOT NULL,
        notification INTEGER NOT NULL DEFAULT 1,
        lesson_time INTEGER NOT NULL DEFAULT 1,
        UNIQUE(platform, platform_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS user_groups (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        group_id TEXT NOT NULL, PRIMARY KEY (user_id, group_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS user_teachers (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        teacher TEXT NOT NULL, PRIMARY KEY (user_id, teacher))""")
    conn.commit()
    return conn


def _add_user(conn, platform, platform_id, notification=1, lesson_time=1, teachers=None, groups=None):
    """Добавляет пользователя и его настройки."""
    conn.execute('INSERT INTO users (platform, platform_id, notification, lesson_time) VALUES (?, ?, ?, ?)',
                 (platform, platform_id, notification, lesson_time))
    uid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    for t in (teachers or []):
        conn.execute('INSERT INTO user_teachers (user_id, teacher) VALUES (?, ?)', (uid, t))
    for g in (groups or []):
        conn.execute('INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)', (uid, g))
    conn.commit()
    return uid


# ─── enable_and_disable_notifications ───

class TestEnableDisableNotifications:
    def _patch_conn(self, tmp_path, **user_kwargs):
        db_path = tmp_path / 'dbs' / 'user_settings.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _setup_user_settings_db(db_path)
        _add_user(conn, **user_kwargs)
        conn.close()
        return db_path

    def test_enable_already_enabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._patch_conn(tmp_path, platform='email', platform_id='test@mail.com', notification=1)
        from sql_db import enable_and_disable_notifications
        result = enable_and_disable_notifications(enable='YES', email='test@mail.com')
        assert 'уже включены' in result

    def test_disable_already_disabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._patch_conn(tmp_path, platform='email', platform_id='test@mail.com', notification=0)
        from sql_db import enable_and_disable_notifications
        result = enable_and_disable_notifications(disable='YES', email='test@mail.com')
        assert 'уже отключены' in result

    def test_enable_notifications(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._patch_conn(tmp_path, platform='email', platform_id='test@mail.com', notification=0)
        from sql_db import enable_and_disable_notifications
        result = enable_and_disable_notifications(enable='YES', email='test@mail.com')
        assert 'успешно включены' in result

    def test_disable_notifications(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._patch_conn(tmp_path, platform='email', platform_id='test@mail.com', notification=1)
        from sql_db import enable_and_disable_notifications
        result = enable_and_disable_notifications(disable='YES', email='test@mail.com')
        assert 'успешно отключены' in result

    def test_no_user_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_path = tmp_path / 'dbs' / 'user_settings.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _setup_user_settings_db(db_path)
        conn.close()
        from sql_db import enable_and_disable_notifications
        result = enable_and_disable_notifications(enable='YES', email='nonexistent@mail.com')
        assert 'Невозможно' in result or 'не найдено' in result

    def test_no_platform_specified(self):
        from sql_db import enable_and_disable_notifications
        result = enable_and_disable_notifications(enable='YES')
        assert 'ошибка' in result.lower() or 'Произошла' in result


# ─── enable_and_disable_lesson_time ───

class TestEnableDisableLessonTime:
    def _patch_conn(self, tmp_path, **user_kwargs):
        db_path = tmp_path / 'dbs' / 'user_settings.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _setup_user_settings_db(db_path)
        _add_user(conn, **user_kwargs)
        conn.close()

    def test_enable_already_enabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._patch_conn(tmp_path, platform='telegram', platform_id='123', lesson_time=1)
        from sql_db import enable_and_disable_lesson_time
        result = enable_and_disable_lesson_time(enable='YES', telegram='123')
        assert 'уже включено' in result

    def test_disable_lesson_time(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._patch_conn(tmp_path, platform='telegram', platform_id='123', lesson_time=1)
        from sql_db import enable_and_disable_lesson_time
        result = enable_and_disable_lesson_time(disable='YES', telegram='123')
        assert 'успешно отключено' in result

    def test_enable_lesson_time(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._patch_conn(tmp_path, platform='telegram', platform_id='123', lesson_time=0)
        from sql_db import enable_and_disable_lesson_time
        result = enable_and_disable_lesson_time(enable='YES', telegram='123')
        assert 'успешно включено' in result


# ─── delete_all_saved_groups_and_teachers ───

class TestDeleteAllSavedGroupsAndTeachers:
    def test_delete_with_data(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_path = tmp_path / 'dbs' / 'user_settings.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _setup_user_settings_db(db_path)
        _add_user(conn, platform='email', platform_id='test@mail.com',
                  teachers=['Иванов'], groups=['307'])
        conn.close()
        from sql_db import delete_all_saved_groups_and_teachers
        result = delete_all_saved_groups_and_teachers(email='test@mail.com')
        assert 'успешно удалены' in result

    def test_delete_no_data(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_path = tmp_path / 'dbs' / 'user_settings.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _setup_user_settings_db(db_path)
        _add_user(conn, platform='email', platform_id='test@mail.com')
        conn.close()
        from sql_db import delete_all_saved_groups_and_teachers
        result = delete_all_saved_groups_and_teachers(email='test@mail.com')
        assert 'Нет сохраненных' in result

    def test_delete_no_user(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_path = tmp_path / 'dbs' / 'user_settings.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _setup_user_settings_db(db_path)
        conn.close()
        from sql_db import delete_all_saved_groups_and_teachers
        result = delete_all_saved_groups_and_teachers(email='nobody@mail.com')
        assert 'Невозможно удалить' in result

    def test_delete_no_platform(self):
        from sql_db import delete_all_saved_groups_and_teachers
        result = delete_all_saved_groups_and_teachers()
        assert 'Невозможно' in result


# ─── display_saved_settings ───

class TestDisplaySavedSettings:
    def test_display_with_data(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_path = tmp_path / 'dbs' / 'user_settings.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _setup_user_settings_db(db_path)
        _add_user(conn, platform='email', platform_id='test@mail.com',
                  notification=1, lesson_time=1, teachers=['Иванов'], groups=['307'])
        conn.close()
        from sql_db import display_saved_settings
        result = display_saved_settings(email='test@mail.com')
        assert 'Иванов' in result
        assert '307' in result
        assert 'Уведомления включены' in result
        assert 'времени занятий включено' in result

    def test_display_disabled_settings(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_path = tmp_path / 'dbs' / 'user_settings.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _setup_user_settings_db(db_path)
        _add_user(conn, platform='email', platform_id='test@mail.com',
                  notification=0, lesson_time=0)
        conn.close()
        from sql_db import display_saved_settings
        result = display_saved_settings(email='test@mail.com')
        assert 'отключены' in result
        assert 'отключено' in result

    def test_display_no_saved(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_path = tmp_path / 'dbs' / 'user_settings.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _setup_user_settings_db(db_path)
        _add_user(conn, platform='email', platform_id='test@mail.com')
        conn.close()
        from sql_db import display_saved_settings
        result = display_saved_settings(email='test@mail.com')
        assert 'Нет сохраненных' in result

    def test_display_no_user(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_path = tmp_path / 'dbs' / 'user_settings.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _setup_user_settings_db(db_path)
        conn.close()
        from sql_db import display_saved_settings
        result = display_saved_settings(email='nobody@mail.com')
        assert 'нет сохраненных' in result.lower()

    def test_display_no_platform(self):
        from sql_db import display_saved_settings
        result = display_saved_settings()
        assert 'ошибка' in result.lower() or 'Произошла' in result


# ─── create_db_user_settings / create_db_calendars_list ───

class TestCreateDatabases:
    def test_create_user_settings_db(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'dbs').mkdir()
        from sql_db import create_db_user_settings
        create_db_user_settings()
        assert (tmp_path / 'dbs' / 'user_settings.db').exists()

    def test_create_user_settings_db_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'dbs').mkdir()
        from sql_db import create_db_user_settings
        create_db_user_settings()
        result = create_db_user_settings()
        assert result is True  # файл уже существует

    def test_create_calendars_db(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'dbs').mkdir()
        from sql_db import create_db_calendars_list
        create_db_calendars_list()
        assert (tmp_path / 'dbs' / 'calendars_list.db').exists()

    def test_create_calendars_db_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'dbs').mkdir()
        from sql_db import create_db_calendars_list
        create_db_calendars_list()
        result = create_db_calendars_list()
        assert result is True


# ─── search_group_and_teacher_in_request ───

class TestSearchGroupAndTeacherInRequest:
    def test_short_request_returns_false(self):
        from sql_db import search_group_and_teacher_in_request
        result = search_group_and_teacher_in_request(request='аб', email='test@mail.com')
        assert result is False

    def test_no_timetable_db(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'timetable-dbs').mkdir()
        from sql_db import search_group_and_teacher_in_request
        result = search_group_and_teacher_in_request(request='Иванов И.И.', email='test@mail.com')
        assert 'ошибка' in result.lower() or 'Произошла' in result

    def test_match_and_save_teacher(self, tmp_path, monkeypatch):
        """Находит преподавателя в БД и сохраняет его для пользователя."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        dbs_dir = tmp_path / 'dbs'
        dbs_dir.mkdir()

        # Создаём БД расписания
        timetable_conn = sqlite3.connect(str(db_dir / 'timetable_test.db'))
        timetable_conn.execute('''CREATE TABLE timetable (
            "Group" TEXT, "Name" TEXT, "Les" INTEGER, "Date" TEXT,
            "Aud" TEXT, "Subg" INTEGER, "Subject" TEXT, "Subj_type" TEXT,
            "CafID" INTEGER, "Themas" TEXT)''')
        timetable_conn.execute(
            'INSERT INTO timetable VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('307', 'Иванов И.И.', 1, '1-01-2024', '101', 0, 'Математика', 'л', 1, None))
        timetable_conn.commit()
        timetable_conn.close()

        # Создаём БД пользователей
        _setup_user_settings_db(dbs_dir / 'user_settings.db')

        # Сбрасываем кэш
        from sql_db import _timetable_cache
        _timetable_cache['db_path'] = None

        from sql_db import search_group_and_teacher_in_request
        result = search_group_and_teacher_in_request(request='Иванов И.И.', email='test@mail.com')
        assert 'Добавлены преподаватели' in result
        assert 'Иванов' in result

    def test_match_and_save_group(self, tmp_path, monkeypatch):
        """Находит группу и сохраняет для пользователя."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        dbs_dir = tmp_path / 'dbs'
        dbs_dir.mkdir()

        timetable_conn = sqlite3.connect(str(db_dir / 'timetable_test.db'))
        timetable_conn.execute('''CREATE TABLE timetable (
            "Group" TEXT, "Name" TEXT, "Les" INTEGER, "Date" TEXT,
            "Aud" TEXT, "Subg" INTEGER, "Subject" TEXT, "Subj_type" TEXT,
            "CafID" INTEGER, "Themas" TEXT)''')
        timetable_conn.execute(
            'INSERT INTO timetable VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('307', 'Иванов И.И.', 1, '1-01-2024', '101', 0, 'Математика', 'л', 1, None))
        timetable_conn.commit()
        timetable_conn.close()

        _setup_user_settings_db(dbs_dir / 'user_settings.db')

        from sql_db import _timetable_cache
        _timetable_cache['db_path'] = None

        from sql_db import search_group_and_teacher_in_request
        result = search_group_and_teacher_in_request(request='307', email='test@mail.com')
        assert 'Добавлены группы' in result
        assert '307' in result

    def test_already_saved_teacher(self, tmp_path, monkeypatch):
        """Повторное добавление преподавателя -> уже сохранен."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        dbs_dir = tmp_path / 'dbs'
        dbs_dir.mkdir()

        timetable_conn = sqlite3.connect(str(db_dir / 'timetable_test.db'))
        timetable_conn.execute('''CREATE TABLE timetable (
            "Group" TEXT, "Name" TEXT, "Les" INTEGER, "Date" TEXT,
            "Aud" TEXT, "Subg" INTEGER, "Subject" TEXT, "Subj_type" TEXT,
            "CafID" INTEGER, "Themas" TEXT)''')
        timetable_conn.execute(
            'INSERT INTO timetable VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('307', 'Иванов И.И.', 1, '1-01-2024', '101', 0, 'Математика', 'л', 1, None))
        timetable_conn.commit()
        timetable_conn.close()

        user_conn = _setup_user_settings_db(dbs_dir / 'user_settings.db')
        _add_user(user_conn, platform='email', platform_id='test@mail.com',
                  teachers=['Иванов И.И.'])
        user_conn.close()

        from sql_db import _timetable_cache
        _timetable_cache['db_path'] = None

        from sql_db import search_group_and_teacher_in_request
        result = search_group_and_teacher_in_request(request='Иванов И.И.', email='test@mail.com')
        assert 'уже сохранен' in result.lower() or 'Для вас уже' in result

    def test_no_match_returns_suggestions_or_false(self, tmp_path, monkeypatch):
        """Нет совпадений -> подсказки или False."""
        monkeypatch.chdir(tmp_path)
        db_dir = tmp_path / 'timetable-dbs'
        db_dir.mkdir()
        dbs_dir = tmp_path / 'dbs'
        dbs_dir.mkdir()

        timetable_conn = sqlite3.connect(str(db_dir / 'timetable_test.db'))
        timetable_conn.execute('''CREATE TABLE timetable (
            "Group" TEXT, "Name" TEXT, "Les" INTEGER, "Date" TEXT,
            "Aud" TEXT, "Subg" INTEGER, "Subject" TEXT, "Subj_type" TEXT,
            "CafID" INTEGER, "Themas" TEXT)''')
        timetable_conn.execute(
            'INSERT INTO timetable VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('307', 'Иванов И.И.', 1, '1-01-2024', '101', 0, 'Математика', 'л', 1, None))
        timetable_conn.commit()
        timetable_conn.close()

        _setup_user_settings_db(dbs_dir / 'user_settings.db')

        from sql_db import _timetable_cache
        _timetable_cache['db_path'] = None

        from sql_db import search_group_and_teacher_in_request
        result = search_group_and_teacher_in_request(request='НесуществующийТекст', email='test@mail.com')
        assert result is False or 'Возможно вы имели ввиду' in str(result)
