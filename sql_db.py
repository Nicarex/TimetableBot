import sqlite3
from log import logger
from main import get_latest_file, connection_to_sql
from glob import glob
from timetable import date_request
from mail import sendMail


# Создание таблиц
def create_db():
    # Таблица для почты
    conn = connection_to_sql(name='user_settings.db')
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS email(
                email           TEXT,
                group_id        TEXT,
                teacher         TEXT,
                notification    INTEGER,
                date_send       TEXT,
                time_send       TEXT);
                """)

    # Таблица для ВК пользователей
    conn.execute("""CREATE TABLE IF NOT EXISTS vk_user (
                vk_id           TEXT,
                group_id        TEXT,
                teacher         TEXT,
                notification    INTEGER,
                date_send       TEXT,
                time_send       TEXT)
                """)

    # Таблица для ВК чатов
    conn.execute("""CREATE TABLE IF NOT EXISTS vk_chat (
                vk_id           TEXT,
                group_id        TEXT,
                teacher         TEXT,
                notification    INTEGER,
                date_send       TEXT,
                time_send       TEXT)
                """)
    conn.commit()  # Сохранение изменений
    c.close()
    conn.close()  # Закрытие подключения


create_db()


def suggestions_about_request_in_timetable_db(request: str):
    logger.debug('Received a request for suggestions "' + request + '"')
    if len(request) <= 2:
        logger.debug('Request <= 2 symbols, skip')
        return 'Введите минимум 3 символа для показа возможных вариантов'
    db_timetable = get_latest_file('timetable-dbs/timetable*.db')
    if db_timetable is None:
        logger.error('Cant search suggestions because no db-files in timetable-dbs directory')
        return None
    conn = connection_to_sql(db_timetable)
    conn.row_factory = sqlite3.Row
    # Запись + символы для поиска справа
    request = '%' + request + '%'
    # Поиск в базе данных для группы
    c = conn.cursor()
    c.execute('SELECT * FROM timetable WHERE "Group" LIKE ?', (request,))
    records_group = c.fetchall()
    c.close()
    # Поиск в базе данных для преподавателя
    c = conn.cursor()
    c.execute('SELECT * FROM timetable WHERE "Name" LIKE ?', (request,))
    records_teacher = c.fetchall()
    c.close()
    conn.close()
    # Перебор полученных значений
    response = ''
    for row in records_group:
        if response.find(row['Group']) == -1:
            response += row['Group'] + '\n'
    for row in records_teacher:
        if response.find(row['Name']) == -1:
            response += row['Name'] + '\n'
    if response:
        logger.debug('Suggestions found')
        return response
    else:
        logger.debug('No suggestions found')
        return None


# Отправляет письмо на почту о том, что расписание изменилось
def send_notification_email(list_now: list, list_next: list):
    # Подключение к пользовательской базе данных
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Списки для получения записей с почтой
    search_group = []
    search_teacher = []
    search_group_next = []
    search_teacher_next = []
    sent_email = []
    sent_email_next = []
    # Поиск на текущую неделю
    for row in list_now:
        string = '%' + row + '%'
        # Поиск группы
        c.execute("SELECT * FROM email WHERE group_id LIKE ? AND notification = 1", (string,))
        search_group += c.fetchall()
        # Поиск препода
        c.execute("SELECT * FROM email WHERE teacher LIKE ? AND notification = 1", (string,))
        search_teacher += c.fetchall()
    # Поиск на следующую неделю
    for row in list_next:
        string = '%' + row + '%'
        # Поиск группы
        c.execute("SELECT * FROM email WHERE group_id LIKE ? AND notification = 1", (string,))
        search_group_next += c.fetchall()
        # Поиск препода
        c.execute("SELECT * FROM email WHERE teacher LIKE ? AND notification = 1", (string,))
        search_teacher_next += c.fetchall()
    c.close()
    conn.close()
    if not search_group and not search_teacher and not search_group_next and not search_teacher_next:
        logger.trace('Nobody uses it in email')
        return False
    for i in search_group:
        if not i['email'] in sent_email:
            # Добавление почты в список, чтобы больше не отправлялось на этот адрес
            sent_email += [i['email']]
            sendMail(to_email=i['email'], subject='Новое расписание на текущую неделю', text='Ваше расписание на текущую неделю было изменено\n*тут расписание*')
    for i in search_teacher:
        if not i['email'] in sent_email:
            sent_email += [i['email']]
            sendMail(to_email=i['email'], subject='Новое расписание на текущую неделю', text='Ваше расписание на текущую неделю было изменено\n*тут расписание*')
    for i in search_group_next:
        if not i['email'] in sent_email_next:
            sent_email_next += [i['email']]
            sendMail(to_email=i['email'], subject='Новое расписание на следующую неделю', text='Ваше расписание на текущую неделю было изменено\n*тут расписание*')
    for i in search_teacher_next:
        if not i['email'] in sent_email_next:
            sent_email_next += [i['email']]
            sendMail(to_email=i['email'], subject='Новое расписание на следующую неделю', text='Ваше расписание на текущую неделю было изменено\n*тут расписание*')
    return True


def send_notification_vk_chat(list_now: list, list_next: list):
    # Подключение к пользовательской базе данных
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Списки для получения записей с почтой
    search_group = []
    search_teacher = []
    search_group_next = []
    search_teacher_next = []
    sent_vk_chat = []
    sent_vk_chat_next = []
    # Поиск на текущую неделю
    for row in list_now:
        string = '%' + row + '%'
        # Поиск группы
        c.execute("SELECT * FROM vk_chat WHERE group_id LIKE ? AND notification = 1", (string,))
        search_group += c.fetchall()
        # Поиск препода
        c.execute("SELECT * FROM vk_chat WHERE teacher LIKE ? AND notification = 1", (string,))
        search_teacher += c.fetchall()
    # Поиск на следующую неделю
    for row in list_next:
        string = '%' + row + '%'
        # Поиск группы
        c.execute("SELECT * FROM vk_chat WHERE group_id LIKE ? AND notification = 1", (string,))
        search_group_next += c.fetchall()
        # Поиск препода
        c.execute("SELECT * FROM vk_chat WHERE teacher LIKE ? AND notification = 1", (string,))
        search_teacher_next += c.fetchall()
    c.close()
    conn.close()
    if not search_group and not search_teacher and not search_group_next and not search_teacher_next:
        logger.trace('Nobody uses it in vk_chat')
        return False
    for i in search_group:
        if not i['vk_id'] in sent_vk_chat:
            sent_vk_chat += [i['vk_id']]
            """
            Отправка в беседу в ВК
            """
    for i in search_teacher:
        if not i['vk_id'] in sent_vk_chat:
            sent_vk_chat += [i['vk_id']]
            """
            Отправка в беседу в ВК
            """
    for i in search_group_next:
        if not i['vk_id'] in sent_vk_chat_next:
            sent_vk_chat_next += [i['vk_id']]
            """
            Отправка в беседу в ВК
            """
    for i in search_teacher_next:
        if not i['vk_id'] in sent_vk_chat_next:
            sent_vk_chat_next += [i['vk_id']]
            """
            Отправка в беседу в ВК
            """
    return True


def send_notification_vk_user(list_now: list, list_next: list):
    # Подключение к пользовательской базе данных
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Списки для получения записей с почтой
    search_group = []
    search_teacher = []
    search_group_next = []
    search_teacher_next = []
    sent_vk_user = []
    sent_vk_user_next = []
    # Поиск на текущую неделю
    for row in list_now:
        string = '%' + row + '%'
        # Поиск группы
        c.execute("SELECT * FROM vk_user WHERE group_id LIKE ? AND notification = 1", (string,))
        search_group += c.fetchall()
        # Поиск препода
        c.execute("SELECT * FROM vk_user WHERE teacher LIKE ? AND notification = 1", (string,))
        search_teacher += c.fetchall()
    # Поиск на следующую неделю
    for row in list_next:
        string = '%' + row + '%'
        # Поиск группы
        c.execute("SELECT * FROM vk_user WHERE group_id LIKE ? AND notification = 1", (string,))
        search_group_next += c.fetchall()
        # Поиск препода
        c.execute("SELECT * FROM vk_user WHERE teacher LIKE ? AND notification = 1", (string,))
        search_teacher_next += c.fetchall()
    c.close()
    conn.close()
    if not search_group and not search_teacher and not search_group_next and not search_teacher_next:
        logger.trace('Nobody uses it in vk_user')
        return False
    for i in search_group:
        if not i['vk_id'] in sent_vk_user:
            sent_vk_user += [i['vk_id']]
            """
            Отправка в беседу в ВК
            """
    for i in search_teacher:
        if not i['vk_id'] in sent_vk_user:
            sent_vk_user += [i['vk_id']]
            """
            Отправка в беседу в ВК
            """
    for i in search_group_next:
        if not i['vk_id'] in sent_vk_user_next:
            sent_vk_user_next += [i['vk_id']]
            """
            Отправка в беседу в ВК
            """
    for i in search_teacher_next:
        if not i['vk_id'] in sent_vk_user_next:
            sent_vk_user_next += [i['vk_id']]
            """
            Отправка в беседу в ВК
            """
    return True


# Получает разницу в двух sql-файлах расписания
# Для отправки разницы пользователям
def getting_the_difference_in_sql_files_and_sending_them():
    logger.trace('Search the differences in timetables...')
    # Последняя база данных
    new_db = get_latest_file(path='timetable-dbs/*.db')
    # Предпоследняя база данных
    try:
        previous_db = glob(pathname='timetable-dbs/*.db')[-2]
        logger.debug('Previous sql-file is <' + previous_db + '>')
    except IndexError:
        logger.warning('No previous sql-file. Skip file comparison for difference')
        return False
    # Подключение к базам данных расписания
    conn = connection_to_sql(new_db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("ATTACH ? AS db2", (previous_db,))
    c.execute("SELECT * FROM main.timetable EXCEPT SELECT * FROM db2.timetable")
    results = c.fetchall()
    c.close()
    conn.close()
    if not results:
        logger.trace('No differences in timetables')
        return None
    # Подключение к пользовательской базе данных
    list_with_send_request = []
    list_with_send_request_next = []
    for row in results:
        # print(row['Group'], row['Name'])
        for day in range(0,7):
            if date_request(day_of_week=day, for_db='YES') == row['Date']:
                if not row['Name'] in list_with_send_request:
                    list_with_send_request += [row['Name']]
                if not row['Group'] in list_with_send_request:
                    list_with_send_request += [row['Group']]
            elif date_request(day_of_week=day, for_db='YES', next='YES') == row['Date']:
                if not row['Name'] in list_with_send_request_next:
                    list_with_send_request_next += [row['Name']]
                if not row['Group'] in list_with_send_request_next:
                    list_with_send_request_next += [row['Group']]
    logger.trace('Got the differences. Trying to send them')
    if send_notification_email(list_now=list_with_send_request, list_next=list_with_send_request_next) is True:
        logger.trace('Successfully sent the differences by email')
    elif send_notification_vk_chat(list_now=list_with_send_request, list_next=list_with_send_request_next) is True:
        logger.trace('Successfully sent the differences by vk_chat')
    elif send_notification_vk_user(list_now=list_with_send_request, list_next=list_with_send_request_next) is True:
        logger.trace('Successfully sent the differences by vk_user')


# with logger.catch():
#     getting_the_difference_in_sql_files_and_sending_them()

