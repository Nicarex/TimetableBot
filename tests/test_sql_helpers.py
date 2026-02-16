"""Тесты для вспомогательных функций sql_db.py."""
import sqlite3
import pytest

from sql_db import (
    _build_saved_response,
    _build_added_response,
    _get_user,
    _get_user_teachers,
    _get_user_groups,
)
from other import get_row_value


# --- _build_saved_response ---

class TestBuildSavedResponse:
    def test_both_teachers_and_groups(self):
        result = _build_saved_response('Иванов ', 'А-101 ', is_chat=False)
        assert 'преподаватели: Иванов' in result
        assert 'группы: А-101' in result

    def test_only_teachers(self):
        result = _build_saved_response('Иванов ', '', is_chat=False)
        assert 'преподаватели: Иванов' in result
        assert 'групп' not in result

    def test_only_groups(self):
        result = _build_saved_response('', 'А-101 ', is_chat=False)
        assert 'группы: А-101' in result
        assert 'преподават' not in result

    def test_empty(self):
        result = _build_saved_response('', '', is_chat=False)
        assert result == ''

    def test_chat_mode_labels(self):
        result = _build_saved_response('Иванов ', 'А-101 ', is_chat=True)
        assert 'Преподаватели уже сохранены:' in result
        assert 'Группы уже сохранены:' in result

    def test_non_chat_mode_labels(self):
        result = _build_saved_response('Иванов ', '', is_chat=False)
        assert 'Для вас уже сохранены преподаватели:' in result


# --- _build_added_response ---

class TestBuildAddedResponse:
    def test_with_existing_and_new(self):
        result = _build_added_response('Уже сохранено', 'Петров', 'Б-202')
        assert 'Уже сохранено' in result
        assert 'Добавлены преподаватели: Петров' in result
        assert 'Добавлены группы: Б-202' in result
        assert '\n\n' in result

    def test_no_existing(self):
        result = _build_added_response('', 'Петров', 'Б-202')
        assert result.startswith('Добавлены преподаватели: Петров')

    def test_only_teachers_added(self):
        result = _build_added_response('', 'Петров', '')
        assert 'Добавлены преподаватели: Петров' in result
        assert 'группы' not in result

    def test_only_groups_added(self):
        result = _build_added_response('', '', 'Б-202')
        assert 'Добавлены группы: Б-202' in result
        assert 'преподават' not in result

    def test_nothing_added(self):
        result = _build_added_response('Existing', '', '')
        assert result == 'Existing'

    def test_empty_everything(self):
        result = _build_added_response('', '', '')
        assert result == ''


# --- _get_user, _get_user_teachers, _get_user_groups ---

class TestUserHelpers:
    def setup_method(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            platform_id TEXT NOT NULL,
            notification INTEGER NOT NULL DEFAULT 1,
            lesson_time INTEGER NOT NULL DEFAULT 1,
            UNIQUE(platform, platform_id))""")
        self.conn.execute("""CREATE TABLE user_groups (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            group_id TEXT NOT NULL,
            PRIMARY KEY (user_id, group_id))""")
        self.conn.execute("""CREATE TABLE user_teachers (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            teacher TEXT NOT NULL,
            PRIMARY KEY (user_id, teacher))""")
        self.conn.execute(
            "INSERT INTO users (platform, platform_id) VALUES ('email', 'test@mail.com')")
        self.conn.execute(
            "INSERT INTO user_teachers (user_id, teacher) VALUES (1, 'Иванов А.Б.')")
        self.conn.execute(
            "INSERT INTO user_teachers (user_id, teacher) VALUES (1, 'Петров В.Г.')")
        self.conn.execute(
            "INSERT INTO user_groups (user_id, group_id) VALUES (1, '307')")
        self.conn.commit()
        self.cursor = self.conn.cursor()

    def teardown_method(self):
        self.conn.close()

    def test_get_user_found(self):
        user = _get_user(self.cursor, 'email', 'test@mail.com')
        assert user is not None
        assert user['platform_id'] == 'test@mail.com'

    def test_get_user_not_found(self):
        user = _get_user(self.cursor, 'email', 'nonexistent@mail.com')
        assert user is None

    def test_get_user_teachers(self):
        teachers = _get_user_teachers(self.cursor, 1)
        assert set(teachers) == {'Иванов А.Б.', 'Петров В.Г.'}

    def test_get_user_teachers_empty(self):
        self.conn.execute("INSERT INTO users (platform, platform_id) VALUES ('vk_user', '123')")
        self.conn.commit()
        teachers = _get_user_teachers(self.cursor, 2)
        assert teachers == []

    def test_get_user_groups(self):
        groups = _get_user_groups(self.cursor, 1)
        assert groups == ['307']

    def test_get_user_groups_empty(self):
        self.conn.execute("INSERT INTO users (platform, platform_id) VALUES ('vk_user', '123')")
        self.conn.commit()
        groups = _get_user_groups(self.cursor, 2)
        assert groups == []


# --- get_row_value ---

class TestGetRowValue:
    def test_existing_column(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE t (a TEXT, b TEXT)')
        conn.execute("INSERT INTO t VALUES ('hello', 'world')")
        row = conn.execute('SELECT * FROM t').fetchone()
        assert get_row_value(row, 'a') == 'hello'
        assert get_row_value(row, 'b') == 'world'
        conn.close()

    def test_missing_column(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE t (a TEXT)')
        conn.execute("INSERT INTO t VALUES ('hello')")
        row = conn.execute('SELECT * FROM t').fetchone()
        assert get_row_value(row, 'nonexistent', 'default') == 'default'
        conn.close()
