import sqlite3


# Подключение к БД
def connection_to_sqlite(name):
    conn = None
    try:
        conn = sqlite3.connect(database=name)
    except sqlite3.Error as error:
        print('Failed to read data from sqlite table', error)
    return conn


# Создание таблиц
def create_db():
    # Таблица для студентов на почте
    conn = connection_to_sqlite(name='user_settings.db')
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
    conn.execute("""CREATE TABLE IF NOT EXISTS vk_user_student (
                vk_id           INT,
                group_id        TEXT,
                UNIQUE(vk_id, group_id)
                ON CONFLICT REPLACE);
                """)

    # Таблица для студентов в ВК
    conn.execute("""CREATE TABLE IF NOT EXISTS vk_chat_student (
                vk_id           INT,
                group_id        TEXT,
                UNIQUE(vk_id, group_id)
                ON CONFLICT REPLACE);
                """)

    # Таблица для студентов в ВК
    conn.execute("""CREATE TABLE IF NOT EXISTS vk_user_teacher (
                vk_id           INT,
                teacher_id        TEXT,
                UNIQUE(vk_id, teacher_id)
                ON CONFLICT REPLACE);
                """)

    # Таблица для учителей в ВК
    conn.execute("""CREATE TABLE IF NOT EXISTS vk_chat_teacher (
                vk_id           INT,
                teacher_id      TEXT,
                UNIQUE(vk_id,teacher_id)
                ON CONFLICT REPLACE);
                """)

    conn.commit()  # Сохранение изменений
    conn.close()  # Закрытие подключения


# Добавление записи в таблицу для почты
def add_values_email(table, first_value, second_value):
    conn = connection_to_sqlite(name='user_settings.db')
    # В таблице table добавляем first_value и second_value
    conn.execute('INSERT INTO "{}" VALUES (?, ?)'.format(table.replace('"', '""')), (first_value, second_value))
    conn.commit()
    conn.close()


# Добавляет записи в таблицу для ВК
def add_values_vk(table, value, user_id_event=None, chat_id_event=None):
    first_value = ''
    second_value = value
    if user_id_event is not None: first_value = int(user_id_event.obj.message['peer_id'])
    if chat_id_event is not None: first_value = int(chat_id_event.chat_id)
    conn = connection_to_sqlite(name='user_settings.db')
    # В таблице table добавляем first_value и second_value
    conn.execute('INSERT INTO "{}" VALUES (?, ?)'.format(table.replace('"', '""')), (first_value, second_value))
    conn.commit()
    conn.close()


# Находит все значения в таблице table с значением value и возвращает их в виде словаря
def read_values_all_email(table, sender):
    conn = connection_to_sqlite(name='user_settings.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM "{}" WHERE email = ?'.format(table.replace('"', '""')), [sender])
    dictionary = cursor.fetchall()
    cursor.close()
    conn.close()
    return dictionary


# Передает значения из таблицы для ВК
def read_values_all_vk(table, user_id_event=None, chat_id_event=None):
    if user_id_event is not None: value = int(user_id_event.obj.message['peer_id'])
    if chat_id_event is not None: value = int(chat_id_event.chat_id)
    conn = connection_to_sqlite(name='user_settings.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM "{}" WHERE vk_id = ?'.format(table.replace('"', '""')), [value])
    dictionary = cursor.fetchall()
    cursor.close()
    conn.close()
    return dictionary


# Удаляет все строки в table с email=value
def delete_values_all_email(table, sender):
    conn = connection_to_sqlite(name='user_settings.db')
    conn.execute('DELETE FROM "{}" WHERE email = ?'.format(table.replace('"', '""')), [sender])
    conn.commit()
    conn.close()


# Удаляет все строки в table с vk=value
def delete_values_all_vk(table, user_id_event=None, chat_id_event=None):
    if user_id_event is not None: value = int(user_id_event.obj.message['peer_id'])
    elif chat_id_event is not None: value = int(chat_id_event.chat_id)
    else: print('Неверно передан параметр в delete_values_all_vk')
    conn = connection_to_sqlite(name='user_settings.db')
    conn.execute('DELETE FROM "{}" WHERE vk_id = ?'.format(table.replace('"', '""')), [value])
    conn.commit()
    conn.close()


# Проверяет, существует ли хоть одна запись для ВК
def if_record_exist_vk(event, user=None, chat=None):
    if user is not None:
        if read_values_all_vk('vk_user_student', user_id_event=event) != [] or read_values_all_vk('vk_user_teacher', user_id_event=event) != []:
            return 'YES'
    elif chat is not None:
        if read_values_all_vk('vk_chat_student', chat_id_event=event) != [] or read_values_all_vk('vk_chat_teacher', chat_id_event=event) != []:
            return 'YES'
    else:
        return 'NO'


# Существует ли хоть одна запись для email
def if_record_exist_email(sender):
    if read_values_all_email('students_email', sender) != [] or read_values_all_email('teachers_email', sender) != []:
        return 'YES'
    else:
        return 'NO'


# Создает БД, если не существует
create_db()
