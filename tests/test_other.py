"""Тесты для функций из other.py."""
import os
import tempfile
import time
import pytest


class TestGetLatestFile:
    def test_returns_latest(self, tmp_path):
        # Создаём файлы с разным mtime
        f1 = tmp_path / 'file1.db'
        f2 = tmp_path / 'file2.db'
        f1.write_text('old')
        time.sleep(0.05)
        f2.write_text('new')
        from other import get_latest_file
        result = get_latest_file(str(tmp_path / '*.db'))
        assert os.path.basename(result) == 'file2.db'

    def test_returns_none_when_empty(self, tmp_path):
        from other import get_latest_file
        result = get_latest_file(str(tmp_path / '*.db'))
        assert result is None

    def test_single_file(self, tmp_path):
        f = tmp_path / 'only.db'
        f.write_text('data')
        from other import get_latest_file
        result = get_latest_file(str(tmp_path / '*.db'))
        assert os.path.basename(result) == 'only.db'


class TestCreateRequiredDirs:
    def test_creates_all_directories(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from other import create_required_dirs
        create_required_dirs()
        for d in ['timetable-dbs', 'timetable-files', 'downloads', 'log', 'calendars']:
            assert (tmp_path / d).is_dir()

    def test_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from other import create_required_dirs
        create_required_dirs()
        create_required_dirs()  # вызов повторно не должен падать
        assert (tmp_path / 'calendars').is_dir()


class TestConnectionToSql:
    def test_creates_connection(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        from other import connection_to_sql
        conn = connection_to_sql(db_path)
        assert conn is not None
        conn.close()

    def test_connection_works(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        from other import connection_to_sql
        conn = connection_to_sql(db_path)
        conn.execute('CREATE TABLE t (id INTEGER)')
        conn.execute('INSERT INTO t VALUES (42)')
        conn.commit()
        row = conn.execute('SELECT * FROM t').fetchone()
        assert row[0] == 42
        conn.close()
