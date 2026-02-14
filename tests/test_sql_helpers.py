"""Тесты для вспомогательных функций sql_db.py."""
import sqlite3
import pytest

from sql_db import (
    _build_saved_response,
    _build_added_response,
    _find_already_saved,
    _update_column_values,
    _prepare_insert_values,
    get_row_value,
)


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
        assert '\n\n' in result  # separator between existing and added

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


# --- _find_already_saved ---

class TestFindAlreadySaved:
    def test_finds_existing(self):
        result = _find_already_saved(['Иванов А.Б.', 'Петров В.Г.'], 'Иванов А.Б.\nСидоров')
        assert 'Иванов А.Б.' in result
        assert 'Петров' not in result

    def test_none_saved(self):
        result = _find_already_saved(['Иванов'], None)
        assert result == ''

    def test_empty_matched(self):
        result = _find_already_saved([], 'Иванов')
        assert result == ''

    def test_all_match(self):
        result = _find_already_saved(['A', 'B'], 'A\nB')
        assert 'A' in result
        assert 'B' in result

    def test_none_match(self):
        result = _find_already_saved(['X', 'Y'], 'A\nB')
        assert result == ''


# --- _prepare_insert_values ---

class TestPrepareInsertValues:
    def test_single_item(self):
        db_val, display_val = _prepare_insert_values(['Иванов'])
        assert db_val == 'Иванов'
        assert display_val == 'Иванов'

    def test_multiple_items(self):
        db_val, display_val = _prepare_insert_values(['Иванов', 'Петров'])
        assert db_val == 'Иванов\nПетров'
        assert display_val == 'Иванов Петров'

    def test_empty_list(self):
        db_val, display_val = _prepare_insert_values([])
        assert db_val is None
        assert display_val == ''


# --- _update_column_values ---

class TestUpdateColumnValues:
    def setup_method(self):
        """Создаём in-memory SQLite базу для тестов."""
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('CREATE TABLE test_table (id TEXT, teacher TEXT, group_id TEXT)')
        self.cursor = self.conn.cursor()

    def teardown_method(self):
        self.conn.close()

    def test_adds_new_value_to_existing(self):
        self.conn.execute("INSERT INTO test_table VALUES ('user1', 'Иванов', NULL)")
        self.conn.commit()
        result = _update_column_values(
            self.cursor, 'test_table', 'teacher', 'id', 'user1',
            ['Петров'], 'Иванов')
        self.conn.commit()
        assert 'Петров' in result
        row = self.conn.execute("SELECT teacher FROM test_table WHERE id='user1'").fetchone()
        assert 'Иванов\nПетров' == row['teacher']

    def test_skips_already_existing(self):
        self.conn.execute("INSERT INTO test_table VALUES ('user1', 'Иванов', NULL)")
        self.conn.commit()
        result = _update_column_values(
            self.cursor, 'test_table', 'teacher', 'id', 'user1',
            ['Иванов'], 'Иванов')
        assert result == ''

    def test_adds_to_null_column(self):
        self.conn.execute("INSERT INTO test_table VALUES ('user1', NULL, NULL)")
        self.conn.commit()
        result = _update_column_values(
            self.cursor, 'test_table', 'teacher', 'id', 'user1',
            ['Иванов'], None)
        self.conn.commit()
        assert 'Иванов' in result
        row = self.conn.execute("SELECT teacher FROM test_table WHERE id='user1'").fetchone()
        assert row['teacher'] == 'Иванов'

    def test_empty_matched_items(self):
        self.conn.execute("INSERT INTO test_table VALUES ('user1', 'Иванов', NULL)")
        self.conn.commit()
        result = _update_column_values(
            self.cursor, 'test_table', 'teacher', 'id', 'user1',
            [], 'Иванов')
        assert result == ''


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
