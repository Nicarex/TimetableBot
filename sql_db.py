import sqlite3
from log import logger
from main import get_latest_file, connection_to_sql, sendMail
from glob import glob
from timetable import date_request, timetable


# Создание пользовательской базы данных
def create_db_user_settings():
    # Таблица для почты
    conn = connection_to_sql(name='user_settings.db')
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS email(
                email           TEXT,
                group_id        TEXT,
                teacher         TEXT,
                notification    INTEGER);
                """)

    # Таблица для ВК пользователей
    conn.execute("""CREATE TABLE IF NOT EXISTS vk_user (
                vk_id           TEXT,
                group_id        TEXT,
                teacher         TEXT,
                notification    INTEGER);
                """)

    # Таблица для ВК чатов
    conn.execute("""CREATE TABLE IF NOT EXISTS vk_chat (
                vk_id           TEXT,
                group_id        TEXT,
                teacher         TEXT,
                notification    INTEGER);
                """)
    conn.commit()  # Сохранение изменений
    c.close()
    conn.close()  # Закрытие подключения


# Создание базы данных пользователей, если её нет
create_db_user_settings()


# Предположения о группах и преподавателях на основе запроса пользователя
def suggestions_about_request_in_timetable_db(request: str):
    logger.debug('Received a request for suggestions "' + request + '"')
    if len(request) <= 2:
        logger.debug('Request <= 2 symbols, skip')
        return 'Введите минимум 3 символа для показа возможных вариантов'
    db_timetable = get_latest_file('timetable-dbs/timetable*.db')
    if db_timetable is None:
        logger.error('Cant search suggestions because no db-files in timetable-dbs directory')
        return False
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
        logger.debug('Nobody uses it in email')
        return False
    for i in search_group:
        if not i['email'] in sent_email:
            # Добавление почты в список, чтобы больше не отправлялось на этот адрес
            sent_email += [i['email']]
            sendMail(to_email=i['email'], subject='Новое расписание на текущую неделю', text='Ваше расписание на текущую неделю было изменено\n\n' + getting_timetable_for_user(email=i['email']))
    for i in search_teacher:
        if not i['email'] in sent_email:
            sent_email += [i['email']]
            sendMail(to_email=i['email'], subject='Новое расписание на текущую неделю', text='Ваше расписание на текущую неделю было изменено\n\n' + getting_timetable_for_user(email=i['email']))
    for i in search_group_next:
        if not i['email'] in sent_email_next:
            sent_email_next += [i['email']]
            sendMail(to_email=i['email'], subject='Новое расписание на следующую неделю', text='Ваше расписание на следущую неделю было изменено\n\n' + getting_timetable_for_user(next='YES', email=i['email']))
    for i in search_teacher_next:
        if not i['email'] in sent_email_next:
            sent_email_next += [i['email']]
            sendMail(to_email=i['email'], subject='Новое расписание на следующую неделю', text='Ваше расписание на следущую неделю было изменено\n\n' + getting_timetable_for_user(next='YES', email=i['email']))
    return True


# Отправляет сообщение в ВК о том, что расписание изменилось
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
        logger.debug('Nobody uses it in vk_chat')
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


# Отправляет сообщение в ВК о том, что расписание изменилось
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
        logger.debug('Nobody uses it in vk_user')
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


# Получает разницу в двух sql-файлах расписания для отправки разницы пользователям
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
        logger.debug('No differences in timetables')
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


# Поиск группы и преподавателя в запросе и добавление их в параметры
def search_group_and_teacher_in_request(request: str, email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    logger.trace('Search groups and teachers in request...')
    if request is None or request == '':
        logger.trace('Request for search is empty')
        return 'Параметров не найдено, так как ваше сообщение пустое'
    timetable_db = get_latest_file('timetable-dbs/*.db')
    if timetable_db is None:
        logger.error('Cant search groups and teachers in request because no timetable-db exists')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    results_group = []
    results_teacher = []
    conn = connection_to_sql(timetable_db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM timetable')
    results = c.fetchall()
    # Ищет группы и преподавателей для переданного запроса и сохраняет их в свой список для дальнейшего по ним поиска
    for row in results:
        if request.find(row['Name']) != -1 and not row['Name'] in results_teacher:
            results_teacher += [row['Name']]
        if request.find(row['Group']) != -1 and not row['Group'] in results_group:
            results_group += [row['Group']]
    c.close()
    conn.close()
    # Если есть хоть одна распознанная группа или преподаватель
    if results_group or results_teacher:
        # Обработка для почты
        if email is not None and (vk_id_chat is None and vk_id_user is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM email WHERE email = ?', (email,))
            result = c.fetchone()
            # Если запись есть
            if result:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_group = ''
                response_teacher = ''
                for i in results_teacher:
                    if result['teacher'] is not None:
                        if result['teacher'].find(i) != -1:
                            response_teacher += i + ' '
                for i in results_group:
                    if result['group_id'] is not None:
                        if result['group_id'].find(i) != -1:
                            response_group += i + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Для вашего email уже сохранены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Для вашего email уже сохранены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вашего email уже сохранены группы: ' + response_group
                # Поиск значений, которых нет в базе данных и добавление их
                response_group = ''
                response_teacher = ''
                for i in results_teacher:
                    if result['teacher'] is not None:
                        if result['teacher'].find(i) == -1:
                            record_that_was = c.execute('SELECT * FROM email WHERE email = ?', (email,)).fetchone()['teacher']
                            c.execute('UPDATE email SET teacher = ? WHERE email = ?', (record_that_was + i + '\n', email))
                            response_teacher += i + ' '
                    elif result['teacher'] is None:
                        record_that_was = c.execute('SELECT * FROM email WHERE email = ?', (email,)).fetchone()['teacher']
                        if record_that_was is None:
                            c.execute('UPDATE email SET teacher = ? WHERE email = ?', (i + '\n', email))
                            response_teacher += i + ' '
                        else:
                            c.execute('UPDATE email SET teacher = ? WHERE email = ?', (i + '\n', email))
                            response_teacher += i + ' '
                for i in results_group:
                    if result['group_id'] is not None:
                        if result['group_id'].find(i) == -1:
                            record_that_was = c.execute('SELECT * FROM email WHERE email = ?', (email,)).fetchone()['group_id']
                            c.execute('UPDATE email SET group_id = ? WHERE email = ?', (record_that_was + i + '\n', email))
                            response_group += i + ' '
                    elif result['group_id'] is None:
                        record_that_was = c.execute('SELECT * FROM email WHERE email = ?', (email,)).fetchone()['group_id']
                        if record_that_was is None:
                            c.execute('UPDATE email SET group_id = ? WHERE email = ?', (i + '\n', email))
                            response_group += i + ' '
                        else:
                            c.execute('UPDATE email SET group_id = ? WHERE email = ?', (record_that_was + i + '\n', email))
                            response_group += i + ' '
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДля вашего email добавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДля вашего email добавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДля вашего email добавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то ничего не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Для вашего email добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вашего email добавлены группы: ' + response_group
                conn.commit()
                c.close()
                conn.close()
            # Если записей нет для этой почты, то создаем новую
            else:
                logger.trace('No values found for email <' + email + '>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                if results_teacher:
                    for i in results_teacher:
                        response_teacher += i + ' '
                if results_group:
                    for i in results_group:
                        response_group += i + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Для вашего email добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Для вашего email добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вашего email добавлены группы: ' + response_group
                # Обработка строк для добавление в базу данных
                if results_teacher:
                    for i in results_teacher:
                        insert_teacher += i + '\n'
                if results_group:
                    for i in results_group:
                        insert_group += i + '\n'
                # Для добавления NULL в базе данных
                if insert_group == '':
                    insert_group = None
                if insert_teacher == '':
                    insert_teacher = None
                c.execute('INSERT INTO email (email, group_id, teacher, notification) VALUES (?, ?, ?, 1)', (email, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                logger.trace('New entry has been created for email <' + email + '>')
            return response
        elif vk_id_chat is not None and (email is None and vk_id_user is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
            result = c.fetchone()
            # Если запись есть
            if result:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_group = ''
                response_teacher = ''
                for i in results_teacher:
                    if result['teacher'] is not None:
                        if result['teacher'].find(i) != -1:
                            response_teacher += i + ' '
                for i in results_group:
                    if result['group_id'] is not None:
                        if result['group_id'].find(i) != -1:
                            response_group += i + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вас уже сохранены группы: ' + response_group
                # Поиск значений, которых нет в базе данных и добавление их
                response_group = ''
                response_teacher = ''
                for i in results_teacher:
                    if result['teacher'] is not None:
                        if result['teacher'].find(i) == -1:
                            record_that_was = c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,)).fetchone()['teacher']
                            c.execute('UPDATE vk_chat SET teacher = ? WHERE vk_id = ?', (record_that_was + i + '\n', vk_id_chat))
                            response_teacher += i + ' '
                    elif result['teacher'] is None:
                        record_that_was = c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,)).fetchone()['teacher']
                        if record_that_was is None:
                            c.execute('UPDATE vk_chat SET teacher = ? WHERE vk_id = ?', (i + '\n', vk_id_chat))
                            response_teacher += i + ' '
                        else:
                            c.execute('UPDATE vk_chat SET teacher = ? WHERE vk_id = ?', (i + '\n', vk_id_chat))
                            response_teacher += i + ' '
                for i in results_group:
                    if result['group_id'] is not None:
                        if result['group_id'].find(i) == -1:
                            record_that_was = c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,)).fetchone()['group_id']
                            c.execute('UPDATE vk_chat SET group_id = ? WHERE vk_id = ?', (record_that_was + i + '\n', vk_id_chat))
                            response_group += i + ' '
                    elif result['group_id'] is None:
                        record_that_was = c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,)).fetchone()['group_id']
                        if record_that_was is None:
                            c.execute('UPDATE vk_chat SET group_id = ? WHERE vk_id = ?', (i + '\n', vk_id_chat))
                            response_group += i + ' '
                        else:
                            c.execute('UPDATE vk_chat SET group_id = ? WHERE vk_id = ?', (record_that_was + i + '\n', vk_id_chat))
                            response_group += i + ' '
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДля вас добавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДля вас добавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДля вас добавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то ничего не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Для вас добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вас добавлены группы: ' + response_group
                conn.commit()
                c.close()
                conn.close()
            # Если записей нет для этой почты, то создаем новую
            else:
                logger.trace('No values found for vk_chat <' + vk_id_chat + '>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                if results_teacher:
                    for i in results_teacher:
                        response_teacher += i + ' '
                if results_group:
                    for i in results_group:
                        response_group += i + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Для вас добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Для вас добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вас добавлены группы: ' + response_group
                # Обработка строк для добавление в базу данных
                if results_teacher:
                    for i in results_teacher:
                        insert_teacher += i + '\n'
                if results_group:
                    for i in results_group:
                        insert_group += i + '\n'
                # Для добавления NULL в базе данных
                if insert_group == '':
                    insert_group = None
                if insert_teacher == '':
                    insert_teacher = None
                c.execute('INSERT INTO vk_chat (vk_id, group_id, teacher, notification) VALUES (?, ?, ?, 1)', (vk_id_chat, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                logger.trace('New entry has been created for vk_chat <' + vk_id_chat + '>')
            return response
        elif vk_id_user is not None and (email is None and vk_id_chat is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
            result = c.fetchone()
            # Если запись есть
            if result:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_group = ''
                response_teacher = ''
                for i in results_teacher:
                    if result['teacher'] is not None:
                        if result['teacher'].find(i) != -1:
                            response_teacher += i + ' '
                for i in results_group:
                    if result['group_id'] is not None:
                        if result['group_id'].find(i) != -1:
                            response_group += i + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вас уже сохранены группы: ' + response_group
                # Поиск значений, которых нет в базе данных и добавление их
                response_group = ''
                response_teacher = ''
                for i in results_teacher:
                    if result['teacher'] is not None:
                        if result['teacher'].find(i) == -1:
                            record_that_was = \
                            c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,)).fetchone()['teacher']
                            c.execute('UPDATE vk_user SET teacher = ? WHERE vk_id = ?',
                                      (record_that_was + i + '\n', vk_id_user))
                            response_teacher += i + ' '
                    elif result['teacher'] is None:
                        record_that_was = c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,)).fetchone()['teacher']
                        if record_that_was is None:
                            c.execute('UPDATE vk_user SET teacher = ? WHERE vk_id = ?', (i + '\n', vk_id_user))
                            response_teacher += i + ' '
                        else:
                            c.execute('UPDATE vk_user SET teacher = ? WHERE vk_id = ?', (i + '\n', vk_id_user))
                            response_teacher += i + ' '
                for i in results_group:
                    if result['group_id'] is not None:
                        if result['group_id'].find(i) == -1:
                            record_that_was = \
                            c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,)).fetchone()['group_id']
                            c.execute('UPDATE vk_user SET group_id = ? WHERE vk_id = ?',
                                      (record_that_was + i + '\n', vk_id_user))
                            response_group += i + ' '
                    elif result['group_id'] is None:
                        record_that_was = c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,)).fetchone()[
                            'group_id']
                        if record_that_was is None:
                            c.execute('UPDATE vk_user SET group_id = ? WHERE vk_id = ?', (i + '\n', vk_id_user))
                            response_group += i + ' '
                        else:
                            c.execute('UPDATE vk_user SET group_id = ? WHERE vk_id = ?',
                                      (record_that_was + i + '\n', vk_id_user))
                            response_group += i + ' '
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДля вас добавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДля вас добавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДля вас добавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то ничего не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Для вас добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вас добавлены группы: ' + response_group
                conn.commit()
                c.close()
                conn.close()
            # Если записей нет для этой почты, то создаем новую
            else:
                logger.trace('No values found for vk_user <' + vk_id_user + '>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                if results_teacher:
                    for i in results_teacher:
                        response_teacher += i + ' '
                if results_group:
                    for i in results_group:
                        response_group += i + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Для вас добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Для вас добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вас добавлены группы: ' + response_group
                # Обработка строк для добавление в базу данных
                if results_teacher:
                    for i in results_teacher:
                        insert_teacher += i + '\n'
                if results_group:
                    for i in results_group:
                        insert_group += i + '\n'
                # Для добавления NULL в базе данных
                if insert_group == '':
                    insert_group = None
                if insert_teacher == '':
                    insert_teacher = None
                c.execute('INSERT INTO vk_user (vk_id, group_id, teacher, notification) VALUES (?, ?, ?, 1)',
                          (vk_id_user, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                logger.trace('New entry has been created for vk_user <' + vk_id_user + '>')
            return response
        else:
            logger.error('Incorrect request to search groups and teachers')
            return False
    # Если ничего не распознанно
    else:
        logger.trace('No recognized groups or teachers')
        return False


# Включение и отключение уведомлений для пользователей
def enable_and_disable_notifications(enable: str = None, disable: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        logger.trace('Incoming request to enable or disable notifications for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Если включаем уведомления
        if enable is not None:
            c.execute('UPDATE email SET notification = ? WHERE email = ?', (1, email))
            logger.trace('Notifications for email <' + email + '> are enabled')
            conn.commit()
            c.close()
            conn.close()
            return '\nУведомления успешно включены'
        # Если отключаем уведомления
        elif disable is not None:
            c.execute('UPDATE email SET notification = ? WHERE email = ?', (0, email))
            logger.trace('Notifications for email <' + email + '> are disabled')
            conn.commit()
            c.close()
            conn.close()
            return '\nУведомления успешно отключены'
        # Параметры неизвестны
        else:
            logger.error('Incorrect request to enable or disable notifications for email = <' + email + '>. Enable = ' + str(enable) + ' disable = ' + str(disable))
            c.close()
            conn.close()
            return '\nПроизошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        logger.trace('Incoming request to enable or disable notifications for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Если включаем уведомления
        if enable is not None:
            c.execute('UPDATE vk_chat SET notification = ? WHERE vk_id = ?', (1, vk_id_chat))
            logger.trace('Notifications for vk chat <' + vk_id_chat + '> are enabled')
            conn.commit()
            c.close()
            conn.close()
            return 'Уведомления успешно включены'
        # Если отключаем уведомления
        elif disable is not None:
            c.execute('UPDATE vk_chat SET notification = ? WHERE vk_id = ?', (0, vk_id_chat))
            logger.trace('Notifications for vk chat <' + vk_id_chat + '> are disabled')
            conn.commit()
            c.close()
            conn.close()
            return 'Уведомления успешно отключены'
        # Параметры неизвестны
        else:
            logger.error('Incorrect request to enable or disable notifications for vk chat = <' + vk_id_chat + '>. Enable = ' + str(enable) + ' disable = ' + str(disable))
            c.close()
            conn.close()
            return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        logger.trace('Incoming request to enable or disable notifications for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Если включаем уведомления
        if enable is not None:
            c.execute('UPDATE vk_user SET notification = ? WHERE vk_id = ?', (1, vk_id_user))
            logger.trace('Notifications for vk user <' + vk_id_user + '> are enabled')
            conn.commit()
            c.close()
            conn.close()
            return 'Уведомления успешно включены'
        # Если отключаем уведомления
        elif disable is not None:
            c.execute('UPDATE vk_user SET notification = ? WHERE vk_id = ?', (0, vk_id_user))
            logger.trace('Notifications for vk user <' + vk_id_user + '> are disabled')
            conn.commit()
            c.close()
            conn.close()
            return 'Уведомления успешно отключены'
        # Параметры неизвестны
        else:
            logger.error('Incorrect request to enable or disable notifications for vk user = <' + vk_id_user + '>. Enable = ' + str(enable) + ' disable = ' + str(disable))
            c.close()
            conn.close()
            return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    else:
        logger.error('Incorrect request to enable or disable notifications. Email, vk chat and vk user are undefined')
        return '\nПроизошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# Удаление сохраненых параметров групп и преподов для пользователей
def delete_all_saved_groups_and_teachers(email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        logger.trace('Incoming request to delete all saved groups and teachers for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        result = c.fetchone()
        if result is not None:
            if result['group_id'] is not None or result['teacher'] is not None:
                c.execute('UPDATE email SET group_id = ? WHERE email = ?', (None, email))
                c.execute('UPDATE email SET teacher = ? WHERE email = ?', (None, email))
                conn.commit()
                c.close()
                conn.close()
                logger.trace('All saved groups and teachers for email <' + email + '> are deleted')
                return 'Сохраненные параметры групп и преподавателей успешно удалены'
            else:
                logger.trace('No saved groups or teachers for email <' + email + '>')
                return 'Для вас нет сохраненных групп или преподавателей для отправки'
        else:
            c.close()
            conn.close()
            logger.trace('No saved groups or teachers for email <' + email + '>')
            return 'Для вас нет сохраненных групп или преподавателей для отправки'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        logger.trace('Incoming request to delete all saved groups and teachers for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        result = c.fetchone()
        if result is not None:
            if result['group_id'] is not None or result['teacher'] is not None:
                c.execute('UPDATE vk_chat SET group_id = ? WHERE vk_id = ?', (None, vk_id_chat))
                c.execute('UPDATE vk_chat SET teacher = ? WHERE vk_id = ?', (None, vk_id_chat))
                conn.commit()
                c.close()
                conn.close()
                logger.trace('All saved groups and teachers for vk chat <' + vk_id_chat + '> are deleted')
                return 'Сохраненные параметры групп и преподавателей успешно удалены'
            else:
                logger.trace('No saved groups or teachers for vk chat <' + vk_id_chat + '>')
                return 'Для вас нет сохраненных групп или преподавателей для отправки'
        else:
            c.close()
            conn.close()
            logger.trace('No saved groups or teachers for vk chat <' + vk_id_chat + '>')
            return 'Для вас нет сохраненных групп или преподавателей для отправки'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        logger.trace('Incoming request to delete all saved groups and teachers for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        result = c.fetchone()
        if result is not None:
            if result['group_id'] is not None or result['teacher'] is not None:
                c.execute('UPDATE vk_user SET group_id = ? WHERE vk_id = ?', (None, vk_id_user))
                c.execute('UPDATE vk_user SET teacher = ? WHERE vk_id = ?', (None, vk_id_user))
                conn.commit()
                c.close()
                conn.close()
                logger.trace('All saved groups and teachers for vk user <' + vk_id_user + '> are deleted')
                return 'Сохраненные параметры групп и преподавателей успешно удалены'
            else:
                logger.trace('No saved groups or teachers for vk user <' + vk_id_user + '>')
                return 'Для вас нет сохраненных групп или преподавателей для отправки'
        else:
            c.close()
            conn.close()
            logger.trace('No saved groups or teachers for vk user <' + vk_id_user + '>')
            return 'Для вас нет сохраненных групп или преподавателей для отправки'
    else:
        logger.error('Incorrect request to delete saved groups and teachers. Email, vk chat and vk user are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# Отображение текущих настроек
def display_saved_settings(email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        logger.trace('Incoming request to display all saved settings for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены следующие группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены следующие преподаватели: ' + teachers_answer + '\n'
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Нет сохраненных групп и преподавателей\n'
            if str(result['notification']) == '1':
                answer += 'Уведомления включены'
            elif str(result['notification']) == '0':
                answer += 'Уведомления отключены'
            return answer
        else:
            logger.trace('No saved groups or teachers for email <' + email + '>')
            return 'Для вас нет сохраненных параметров'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        logger.trace('Incoming request to display all saved settings for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены следующие группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены следующие преподаватели: ' + teachers_answer + '\n'
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Нет сохраненных групп и преподавателей\n'
            if str(result['notification']) == '1':
                answer += 'Уведомления включены'
            elif str(result['notification']) == '0':
                answer += 'Уведомления отключены'
            return answer
        else:
            logger.trace('No saved groups or teachers for vk chat <' + vk_id_chat + '>')
            return 'Нет сохраненных параметров'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        logger.trace('Incoming request to display all saved settings for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены следующие группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены следующие преподаватели: ' + teachers_answer + '\n'
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Для вас нет сохраненных групп и преподавателей\n'
            if str(result['notification']) == '1':
                answer += 'Уведомления включены'
            elif str(result['notification']) == '0':
                answer += 'Уведомления отключены'
            return answer
        else:
            logger.trace('No saved groups or teachers for vk user <' + vk_id_user + '>')
            return 'Нет сохраненных параметров'
    else:
        logger.error('Incorrect request to delete saved groups and teachers. Email, vk chat and vk user are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# Получение расписания для пользователя
def getting_timetable_for_user(next: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        logger.debug('Incoming timetable request for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            groups_answer = ''
            teachers_answer = ''
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                for i in groups:
                    if i != '':
                        groups_answer += timetable(group=str(i), next=next) + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                for i in teachers:
                    if i != '':
                        teachers_answer += timetable(teacher=str(i), next=next) + '\n'
            if result['group_id'] is None and result['teacher'] is None:
                answer = 'Нет сохраненных групп и преподавателей\n'
            return groups_answer + teachers_answer + answer
        else:
            logger.debug('No saved groups or teachers for email <' + email + '>')
            return 'Для вас нет сохраненных параметров'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        logger.debug('Incoming timetable request for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            groups_answer = ''
            teachers_answer = ''
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                for i in groups:
                    if i != '':
                        groups_answer += timetable(group=str(i), next=next) + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                for i in teachers:
                    if i != '':
                        teachers_answer += timetable(teacher=str(i), next=next) + '\n'
            if result['group_id'] is None and result['teacher'] is None:
                answer = 'Нет сохраненных групп и преподавателей\n'
            return groups_answer + teachers_answer + answer
        else:
            logger.debug('No saved groups or teachers for vk chat <' + vk_id_chat + '>')
            return 'Нет сохраненных параметров'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        logger.debug('Incoming timetable request for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            groups_answer = ''
            teachers_answer = ''
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                for i in groups:
                    if i != '':
                        groups_answer += timetable(group=str(i), next=next) + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                for i in teachers:
                    if i != '':
                        teachers_answer += timetable(teacher=str(i), next=next) + '\n'
            if result['group_id'] is None and result['teacher'] is None:
                answer = 'Нет сохраненных групп и преподавателей\n'
            return groups_answer + teachers_answer + answer
        else:
            logger.debug('No saved groups or teachers for vk user <' + vk_id_user + '>')
            return 'Для вас нет сохраненных параметров'
    else:
        logger.error('Incorrect timetable request. Email, vk chat and vk user are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'

# with logger.catch():
#     print(enable_and_disable_notifications(enable='YES', vk_id_user='1'))

