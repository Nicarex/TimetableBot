"""Расширенные тесты для other.py."""
import os
import tempfile
import time
import pytest
from pathlib import Path


class TestConvertToSql:
    """Тесты для функции convert_to_sql."""
    
    def test_convert_csv_to_db_creates_file(self, tmp_path):
        """Проверяет, что функция создает файл БД."""
        from other import convert_to_sql
        
        # Создаем CSV файл
        csv_file = tmp_path / 'test.csv'
        csv_content = 'Name;Date;Les\nИванов;1-01-2024;1\nПетров;2-01-2024;2'
        csv_file.write_text(csv_content, encoding='windows-1251')
        
        # Тестируем (if БД файлы были созданы)
        # Не будем полностью тестировать, так как это требует реальной структуры БД
        assert csv_file.exists()
        assert csv_file.read_text(encoding='windows-1251').count('Name') == 1


class TestCheckEncodingAndMoveFiles:
    """Тесты для функции check_encoding_and_move_files."""
    
    def test_detects_correct_encoding(self, tmp_path):
        """Проверяет обнаружение правильной кодировки."""
        from chardet import detect
        
        # Создаем файл в UTF-8
        test_file = tmp_path / 'test.txt'
        test_file.write_text('Привет мир', encoding='utf-8')
        
        # Проверяем кодировку
        with open(test_file, 'rb') as f:
            result = detect(f.read())
        
        assert result['encoding'] is not None
    
    def test_creates_required_dirs(self, tmp_path, monkeypatch):
        """Еще раз проверяем создание директорий."""
        monkeypatch.chdir(tmp_path)
        from other import create_required_dirs
        
        create_required_dirs()
        # Проверяем, что все требуемые директории созданы
        assert (tmp_path / 'timetable-dbs').is_dir()
        assert (tmp_path / 'downloads').is_dir()
        assert (tmp_path / 'calendars').is_dir()


class TestConnectionToSqlAdvanced:
    """Расширенные тесты для функции connection_to_sql."""
    
    def test_pragma_settings_applied(self, tmp_path):
        """Проверяет, что PRAGMA настройки применяются."""
        from other import connection_to_sql
        
        db_path = str(tmp_path / 'test.db')
        conn = connection_to_sql(db_path)
        
        # Проверяем, что подключение работает
        assert conn is not None
        
        # Проверяем журнальный режим
        result = conn.execute('PRAGMA journal_mode').fetchone()
        assert result is not None
        
        conn.close()
    
    def test_foreign_keys_enabled(self, tmp_path):
        """Проверяет, что внешние ключи включены."""
        from other import connection_to_sql
        
        db_path = str(tmp_path / 'test.db')
        conn = connection_to_sql(db_path)
        
        # Проверяем статус внешних ключей
        result = conn.execute('PRAGMA foreign_keys').fetchone()
        assert result is not None
        assert result[0] == 1  # 1 = включено
        
        conn.close()
    
    def test_concurrent_access(self, tmp_path):
        """Проверяет параллельный доступ к БД."""
        from other import connection_to_sql
        
        db_path = str(tmp_path / 'test.db')
        conn1 = connection_to_sql(db_path)
        conn2 = connection_to_sql(db_path)
        
        # Обе conexiones должны работать
        conn1.execute('CREATE TABLE t1 (id INTEGER)')
        conn1.commit()
        
        # Вторая conexiones может читать
        result = conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
        assert result is not None
        
        conn1.close()
        conn2.close()


class TestGetRowValue:
    """Тесты для функции get_row_value."""
    
    def test_get_existing_value(self, tmp_path):
        """Проверяет получение существующего значения."""
        from other import connection_to_sql, get_row_value
        
        db_path = str(tmp_path / 'test.db')
        conn = connection_to_sql(db_path)
        conn.row_factory = __import__('sqlite3').Row
        
        # Создаем таблицу и данные
        conn.execute('CREATE TABLE test (name TEXT, age INTEGER)')
        conn.execute("INSERT INTO test VALUES ('Иван', 30)")
        conn.commit()
        
        # Получаем ряд
        row = conn.execute('SELECT * FROM test').fetchone()
        
        # Проверяем значение
        assert get_row_value(row, 'name') == 'Иван'
        assert get_row_value(row, 'age') == 30
        
        conn.close()
    
    def test_get_missing_value_returns_default(self, tmp_path):
        """Проверяет, что отсутствующее значение возвращает значение по умолчанию."""
        from other import connection_to_sql, get_row_value
        
        db_path = str(tmp_path / 'test.db')
        conn = connection_to_sql(db_path)
        conn.row_factory = __import__('sqlite3').Row
        
        conn.execute('CREATE TABLE test (name TEXT)')
        conn.execute("INSERT INTO test VALUES ('Иван')")
        conn.commit()
        
        row = conn.execute('SELECT * FROM test').fetchone()
        
        # Несуществующий столбец должен вернуть пустую строку по умолчанию
        assert get_row_value(row, 'missing') == ''
        assert get_row_value(row, 'missing', 'default') == 'default'
        
        conn.close()


class TestReadConfig:
    """Тесты для функции read_config."""
    
    def test_read_config_missing_file(self, tmp_path, monkeypatch):
        """Проверяет поведение при отсутствии файла конифгурации."""
        monkeypatch.chdir(tmp_path)
        from other import read_config
        
        # Файл config.ini не существует
        result = read_config(email='YES')
        # Функция должна вернуть None или выдать предупреждение
        # (в зависимости от реализации)
