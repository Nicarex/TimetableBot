import sqlite3


# Подключение к БД
def connection_to_sqlite():
    conn = None
    try:
        conn = sqlite3.connect('useful_info.db')
    except sqlite3.Error as error:
        print('Failed to read data from sqlite table', error)
    return conn


# Создание таблиц
def create_db():
    # Таблица для студентов на почте
    conn = connection_to_sqlite()
    conn.execute("""CREATE TABLE IF NOT EXISTS students_email (
                email           TEXT,
                group_id        TEXT,
                UNIQUE(email, group_id)
                ON CONFLICT REPLACE);
                """)

    # Таблица для учителей на почте
    conn.execute("""CREATE TABLE IF NOT EXISTS teachers_email (
                email           TEXT,
                teacher_id      TEXT,
                UNIQUE(email, teacher_id)
                ON CONFLICT REPLACE);
                """)

    # Таблица для студентов в ВК
    conn.execute("""CREATE TABLE IF NOT EXISTS students_vk (
                vk_id           INT,
                group_id        TEXT,
                UNIQUE(vk_id, group_id)
                ON CONFLICT REPLACE);
                """)

    # Таблица для учителей в ВК
    conn.execute("""CREATE TABLE IF NOT EXISTS teachers_vk (
                vk_id           INT,
                teacher_id      TEXT,
                UNIQUE(vk_id,teacher_id)
                ON CONFLICT REPLACE);
                """)

    conn.commit()  # Сохранение изменений
    conn.close()  # Закрытие подключения


# Добавление записи в таблицу
def add_values(table, first_value, second_value):
    conn = connection_to_sqlite()
    # В таблице table добавляем first_value и second_value
    conn.execute('INSERT INTO "{}" VALUES (?, ?)'.format(table.replace('"', '""')), (first_value, second_value))
    conn.commit()
    conn.close()


# Находит все значения в таблице table с значением value и возвращает их в виде словаря
def read_values_all_email(table, value):
    conn = connection_to_sqlite()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM "{}" WHERE email = ?'.format(table.replace('"', '""')), [value])
    dictionary = cursor.fetchall()
    cursor.close()
    conn.close()
    return dictionary


# Создает БД, если не существует
create_db()