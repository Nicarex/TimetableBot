"""
Скрипт миграции user_settings.db со старой схемы (5 отдельных таблиц)
на новую (единая таблица users + junction-таблицы user_groups, user_teachers).

Запускать ОДИН раз перед обновлением кода.
Создаёт бэкап dbs/user_settings.db.backup перед миграцией.
"""
import shutil
import sqlite3
import sys
from pathlib import Path

DB_PATH = 'dbs/user_settings.db'
BACKUP_PATH = DB_PATH + '.backup'

OLD_TABLES = {
    # table_name: (id_column, platform_name)
    'email': ('email', 'email'),
    'vk_user': ('vk_id', 'vk_user'),
    'vk_chat': ('vk_id', 'vk_chat'),
    'telegram': ('telegram_id', 'telegram'),
    'discord': ('discord_id', 'discord'),
}


def table_exists(cursor, table_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def migrate():
    db = Path(DB_PATH)
    if not db.is_file():
        print(f'Database {DB_PATH} not found. Nothing to migrate.')
        return

    # Проверяем, не мигрирована ли уже БД
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if table_exists(c, 'users'):
        print('Table "users" already exists. Migration appears to be already done.')
        conn.close()
        return

    # Проверяем наличие хотя бы одной старой таблицы
    has_old = any(table_exists(c, t) for t in OLD_TABLES)
    if not has_old:
        print('No old tables found. Nothing to migrate.')
        conn.close()
        return

    conn.close()

    # Бэкап
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f'Backup created: {BACKUP_PATH}')

    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA foreign_keys=ON;')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Создаём новые таблицы
    c.execute("""CREATE TABLE users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        platform        TEXT NOT NULL,
        platform_id     TEXT NOT NULL,
        notification    INTEGER NOT NULL DEFAULT 1,
        lesson_time     INTEGER NOT NULL DEFAULT 1,
        UNIQUE(platform, platform_id))""")

    c.execute("""CREATE TABLE user_groups (
        user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        group_id        TEXT NOT NULL,
        PRIMARY KEY (user_id, group_id))""")

    c.execute("""CREATE TABLE user_teachers (
        user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        teacher         TEXT NOT NULL,
        PRIMARY KEY (user_id, teacher))""")

    c.execute("CREATE INDEX idx_users_notification ON users(notification) WHERE notification = 1")
    c.execute("CREATE INDEX idx_users_platform ON users(platform, platform_id)")

    total_users = 0
    total_groups = 0
    total_teachers = 0

    for table_name, (id_column, platform_name) in OLD_TABLES.items():
        if not table_exists(c, table_name):
            print(f'  Table "{table_name}" not found, skipping.')
            continue

        rows = c.execute(f'SELECT * FROM {table_name}').fetchall()
        print(f'  Migrating "{table_name}": {len(rows)} rows...')

        for row in rows:
            platform_id = row[id_column]
            if platform_id is None or str(platform_id).strip() == '':
                continue

            notification = row['notification'] if row['notification'] is not None else 1
            lesson_time = row['lesson_time'] if row['lesson_time'] is not None else 1

            c.execute(
                'INSERT OR IGNORE INTO users (platform, platform_id, notification, lesson_time) VALUES (?, ?, ?, ?)',
                (platform_name, str(platform_id), notification, lesson_time))

            user = c.execute(
                'SELECT id FROM users WHERE platform = ? AND platform_id = ?',
                (platform_name, str(platform_id))).fetchone()
            if user is None:
                continue
            uid = user['id']
            total_users += 1

            # Миграция групп
            group_val = row['group_id']
            if group_val is not None and str(group_val).strip():
                groups = str(group_val).replace('\r', '').split('\n')
                for g in groups:
                    g = g.strip()
                    if g:
                        c.execute('INSERT OR IGNORE INTO user_groups (user_id, group_id) VALUES (?, ?)', (uid, g))
                        total_groups += 1

            # Миграция преподавателей
            teacher_val = row['teacher']
            if teacher_val is not None and str(teacher_val).strip():
                teachers = str(teacher_val).replace('\r', '').split('\n')
                for t in teachers:
                    t = t.strip()
                    if t:
                        c.execute('INSERT OR IGNORE INTO user_teachers (user_id, teacher) VALUES (?, ?)', (uid, t))
                        total_teachers += 1

    # Удаляем старые таблицы
    for table_name in OLD_TABLES:
        if table_exists(c, table_name):
            c.execute(f'DROP TABLE {table_name}')
            print(f'  Dropped old table "{table_name}"')

    conn.commit()
    c.close()
    conn.close()

    print(f'\nMigration complete!')
    print(f'  Users: {total_users}')
    print(f'  Group entries: {total_groups}')
    print(f'  Teacher entries: {total_teachers}')
    print(f'  Backup: {BACKUP_PATH}')


if __name__ == '__main__':
    migrate()
