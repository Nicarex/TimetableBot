"""Тесты для migrate_schema.py."""
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch


class TestMigrateSchema:

    def _create_old_schema(self, db_path):
        """Создаёт БД со старой схемой (5 отдельных таблиц)."""
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        # Старые таблицы
        for table, id_col in [('email', 'email'), ('vk_user', 'vk_id'),
                               ('vk_chat', 'vk_id'), ('telegram', 'telegram_id'),
                               ('discord', 'discord_id')]:
            conn.execute(f'''CREATE TABLE {table} (
                {id_col} TEXT, group_id TEXT, teacher TEXT,
                notification INTEGER DEFAULT 1, lesson_time INTEGER DEFAULT 1)''')
        conn.commit()
        return conn

    def test_table_exists_helper(self, tmp_path):
        from migrate_schema import table_exists
        db_path = tmp_path / 'test.db'
        conn = sqlite3.connect(str(db_path))
        conn.execute('CREATE TABLE foo (id INTEGER)')
        c = conn.cursor()
        assert table_exists(c, 'foo') is True
        assert table_exists(c, 'bar') is False
        conn.close()

    def test_migrate_no_file(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'dbs').mkdir()
        with patch('migrate_schema.DB_PATH', str(tmp_path / 'dbs' / 'user_settings.db')):
            from migrate_schema import migrate
            migrate()
        captured = capsys.readouterr()
        assert 'not found' in captured.out.lower() or 'Nothing to migrate' in captured.out

    def test_migrate_already_done(self, tmp_path, monkeypatch, capsys):
        db_path = tmp_path / 'user_settings.db'
        conn = sqlite3.connect(str(db_path))
        conn.execute('CREATE TABLE users (id INTEGER)')
        conn.commit()
        conn.close()

        with patch('migrate_schema.DB_PATH', str(db_path)):
            from migrate_schema import migrate
            migrate()
        captured = capsys.readouterr()
        assert 'already' in captured.out.lower()

    def test_migrate_from_old_schema(self, tmp_path, monkeypatch, capsys):
        db_path = tmp_path / 'user_settings.db'
        conn = self._create_old_schema(db_path)

        # Добавляем данные в старую схему
        conn.execute("INSERT INTO email VALUES ('test@mail.com', '307', 'Иванов И.И.', 1, 1)")
        conn.execute("INSERT INTO telegram VALUES ('123456', '308', 'Петров П.П.', 0, 1)")
        conn.execute("INSERT INTO vk_user VALUES ('789', NULL, NULL, 1, 0)")
        conn.commit()
        conn.close()

        backup_path = str(db_path) + '.backup'
        with patch('migrate_schema.DB_PATH', str(db_path)), \
             patch('migrate_schema.BACKUP_PATH', backup_path):
            from migrate_schema import migrate
            migrate()

        captured = capsys.readouterr()
        assert 'complete' in captured.out.lower()

        # Проверяем результат миграции
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Таблица users создана
        from migrate_schema import table_exists
        assert table_exists(c, 'users') is True

        # Старые таблицы удалены
        assert table_exists(c, 'email') is False
        assert table_exists(c, 'telegram') is False

        # Данные мигрированы
        users = c.execute('SELECT * FROM users ORDER BY id').fetchall()
        assert len(users) >= 2

        # Проверяем email пользователя
        email_user = c.execute(
            "SELECT * FROM users WHERE platform='email' AND platform_id='test@mail.com'").fetchone()
        assert email_user is not None
        assert email_user['notification'] == 1

        # Проверяем преподавателей
        teachers = c.execute(
            'SELECT teacher FROM user_teachers WHERE user_id=?', (email_user['id'],)).fetchall()
        assert any(t['teacher'] == 'Иванов И.И.' for t in teachers)

        # Проверяем группы
        groups = c.execute(
            'SELECT group_id FROM user_groups WHERE user_id=?', (email_user['id'],)).fetchall()
        assert any(g['group_id'] == '307' for g in groups)

        # Проверяем бэкап
        assert Path(backup_path).exists()

        conn.close()

    def test_migrate_skips_empty_ids(self, tmp_path, capsys):
        db_path = tmp_path / 'user_settings.db'
        conn = self._create_old_schema(db_path)
        conn.execute("INSERT INTO email VALUES ('', '307', 'Иванов', 1, 1)")
        conn.execute("INSERT INTO email VALUES (NULL, '308', 'Петров', 1, 1)")
        conn.execute("INSERT INTO email VALUES ('valid@mail.com', '309', 'Сидоров', 1, 1)")
        conn.commit()
        conn.close()

        backup_path = str(db_path) + '.backup'
        with patch('migrate_schema.DB_PATH', str(db_path)), \
             patch('migrate_schema.BACKUP_PATH', backup_path):
            from migrate_schema import migrate
            migrate()

        conn = sqlite3.connect(str(db_path))
        users = conn.execute('SELECT * FROM users').fetchall()
        # Только valid@mail.com должен быть мигрирован
        assert len(users) == 1
        conn.close()

    def test_migrate_multiline_groups(self, tmp_path, capsys):
        """Проверяет миграцию групп, разделённых \\n."""
        db_path = tmp_path / 'user_settings.db'
        conn = self._create_old_schema(db_path)
        conn.execute("INSERT INTO email VALUES ('test@mail.com', '307\n308\n309', 'Иванов', 1, 1)")
        conn.commit()
        conn.close()

        backup_path = str(db_path) + '.backup'
        with patch('migrate_schema.DB_PATH', str(db_path)), \
             patch('migrate_schema.BACKUP_PATH', backup_path):
            from migrate_schema import migrate
            migrate()

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT id FROM users WHERE platform='email'").fetchone()
        groups = conn.execute('SELECT group_id FROM user_groups WHERE user_id=?',
                              (user['id'],)).fetchall()
        group_ids = [g['group_id'] for g in groups]
        assert '307' in group_ids
        assert '308' in group_ids
        assert '309' in group_ids
        conn.close()

    def test_no_old_tables(self, tmp_path, capsys):
        """БД существует, но нет ни старых, ни новых таблиц."""
        db_path = tmp_path / 'user_settings.db'
        conn = sqlite3.connect(str(db_path))
        conn.execute('CREATE TABLE other_table (id INTEGER)')
        conn.commit()
        conn.close()

        with patch('migrate_schema.DB_PATH', str(db_path)):
            from migrate_schema import migrate
            migrate()
        captured = capsys.readouterr()
        assert 'Nothing to migrate' in captured.out
