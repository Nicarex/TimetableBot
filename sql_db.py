from other import GROUP_TOKEN, get_latest_file, connection_to_sql, sendMail
import sqlite3
from log import logger
from glob import iglob
from timetable import date_request, timetable
from vk_api import VkApi
from vk_api.utils import get_random_id
from pathlib import Path
import os


# Инициализация
vk_session = VkApi(token=GROUP_TOKEN, api_version='5.131')
vk = vk_session.get_api()


def write_msg_chat(message: str, chat_id: str):
    vk.messages.send(chat_id=int(chat_id), message='➡ ' + message, random_id=get_random_id())


def write_msg_user(message: str, user_id: str):
    vk.messages.send(user_id=int(user_id), message='➡ ' + message, random_id=get_random_id())


# Создание пользовательской базы данных
def create_db_user_settings():
    if Path('user_settings.db').is_file():
        return True
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
    logger.log('SQL', 'User database has been created')


# Создание базы данных пользователей, если её нет
create_db_user_settings()


# Отправляет письмо на почту о том, что расписание изменилось
def send_notifications_email(list_now: list, list_next: list):
    # Подключение к пользовательской базе данных
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    search_teacher = []
    search_group = []
    search_teacher_next = []
    search_group_next = []
    sent_email = []
    sent_email_next = []
    # Поиск на текущую неделю
    if list_now:
        for row in list_now:
            string = '%' + row + '%'
            # Поиск преподавателя
            c.execute("SELECT * FROM email WHERE teacher LIKE ? AND notification = 1", (string,))
            search_teacher += c.fetchall()
            # Поиск группы
            c.execute("SELECT * FROM email WHERE group_id LIKE ? AND notification = 1", (string,))
            search_group += c.fetchall()
    # Поиск на следующую неделю
    if list_next:
        for row in list_next:
            string = '%' + row + '%'
            # Поиск препода
            c.execute("SELECT * FROM email WHERE teacher LIKE ? AND notification = 1", (string,))
            search_teacher_next += c.fetchall()
            # Поиск группы
            c.execute("SELECT * FROM email WHERE group_id LIKE ? AND notification = 1", (string,))
            search_group_next += c.fetchall()
    c.close()
    conn.close()
    if not search_group and not search_teacher and not search_group_next and not search_teacher_next:
        logger.log('SQL', 'Nobody uses it in email')
        return False
    for i in search_teacher:
        if not i['email'] in sent_email:
            sent_email += [i['email']]
            sendMail(to_email=str(i['email']), subject='Новое расписание на текущую неделю', text='Ваше расписание на текущую неделю было изменено\n\n' + getting_timetable_for_user(email=str(i['email'])))
    for i in search_group:
        if not i['email'] in sent_email:
            # Добавление почты в список, чтобы больше не отправлялось на этот адрес
            sent_email += [i['email']]
            sendMail(to_email=str(i['email']), subject='Новое расписание на текущую неделю', text='Ваше расписание на текущую неделю было изменено\n\n' + getting_timetable_for_user(email=str(i['email'])))
    for i in search_teacher_next:
        if not i['email'] in sent_email_next:
            sent_email_next += [i['email']]
            sendMail(to_email=str(i['email']), subject='Новое расписание на следующую неделю', text='Ваше расписание на следущую неделю было изменено\n\n' + getting_timetable_for_user(next='YES', email=str(i['email'])))
    for i in search_group_next:
        if not i['email'] in sent_email_next:
            sent_email_next += [i['email']]
            sendMail(to_email=str(i['email']), subject='Новое расписание на следующую неделю', text='Ваше расписание на следущую неделю было изменено\n\n' + getting_timetable_for_user(next='YES', email=str(i['email'])))
    return True


# Отправляет сообщение в ВК о том, что расписание изменилось
def send_notifications_vk_chat(list_now: list, list_next: list):
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
            answer = str(getting_timetable_for_user(vk_id_chat=i['vk_id'])).split('Cut\n')
            write_msg_chat(message='Расписание на текущую неделю было изменено', chat_id=i['vk_id'])
            for j in answer:
                if j != '':
                    write_msg_chat(message=j, chat_id=i['vk_id'])
    for i in search_teacher:
        if not i['vk_id'] in sent_vk_chat:
            sent_vk_chat += [i['vk_id']]
            answer = str(getting_timetable_for_user(vk_id_chat=i['vk_id'])).split('Cut\n')
            write_msg_chat(message='Расписание на текущую неделю было изменено', chat_id=i['vk_id'])
            for j in answer:
                if j != '':
                    write_msg_chat(message=j, chat_id=i['vk_id'])
    for i in search_group_next:
        if not i['vk_id'] in sent_vk_chat_next:
            sent_vk_chat_next += [i['vk_id']]
            answer = str(getting_timetable_for_user(next='YES', vk_id_chat=i['vk_id'])).split('Cut\n')
            write_msg_chat(message='Расписание на следующую неделю было изменено', chat_id=i['vk_id'])
            for j in answer:
                if j != '':
                    write_msg_chat(message=j, chat_id=i['vk_id'])
    for i in search_teacher_next:
        if not i['vk_id'] in sent_vk_chat_next:
            sent_vk_chat_next += [i['vk_id']]
            answer = str(getting_timetable_for_user(next='YES', vk_id_chat=i['vk_id'])).split('Cut\n')
            write_msg_chat(message='Расписание на следующую неделю было изменено', chat_id=i['vk_id'])
            for j in answer:
                if j != '':
                    write_msg_chat(message=j, chat_id=i['vk_id'])
    return True


# Отправляет сообщение в ВК о том, что расписание изменилось
def send_notifications_vk_user(list_now: list, list_next: list):
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
            answer = str(getting_timetable_for_user(vk_id_user=i['vk_id'])).split('Cut\n')
            write_msg_user(message='Расписание на текущую неделю было изменено', user_id=i['vk_id'])
            for j in answer:
                if j != '':
                    write_msg_user(message=j, user_id=i['vk_id'])
    for i in search_teacher:
        if not i['vk_id'] in sent_vk_user:
            sent_vk_user += [i['vk_id']]
            answer = str(getting_timetable_for_user(vk_id_user=i['vk_id'])).split('Cut\n')
            write_msg_user(message='Расписание на текущую неделю было изменено', user_id=i['vk_id'])
            for j in answer:
                if j != '':
                    write_msg_user(message=j, user_id=i['vk_id'])
    for i in search_group_next:
        if not i['vk_id'] in sent_vk_user_next:
            sent_vk_user_next += [i['vk_id']]
            answer = str(getting_timetable_for_user(next='YES', vk_id_user=i['vk_id'])).split('Cut\n')
            write_msg_user(message='Расписание на следующую неделю было изменено', user_id=i['vk_id'])
            for j in answer:
                if j != '':
                    write_msg_user(message=j, user_id=i['vk_id'])
    for i in search_teacher_next:
        if not i['vk_id'] in sent_vk_user_next:
            sent_vk_user_next += [i['vk_id']]
            answer = str(getting_timetable_for_user(next='YES', vk_id_user=i['vk_id'])).split('Cut\n')
            write_msg_user(message='Расписание на следующую неделю было изменено', user_id=i['vk_id'])
            for j in answer:
                if j != '':
                    write_msg_user(message=j, user_id=i['vk_id'])
    return True


# Получает разницу в двух sql-файлах расписания для отправки разницы пользователям
def getting_the_difference_in_sql_files_and_sending_them():
    """
    Ищет разницу между последним и прошлым расписанием
    Если разница есть, то уведомляет об этом пользователя и отправляет новое расписание
    Если нет, то возвращает False

    Нужно учесть при использовании, что функция не должна быть False
    """
    logger.log('SQL', 'Search the differences in timetables...')
    try:
        # Последняя база данных
        last_db = get_latest_file(path='timetable-dbs/*.db')
        # Предпоследняя база данных
        previous_db = sorted(iglob('timetable-dbs/*.db'), key=os.path.getmtime)[-2]
        logger.log('SQL', 'Previous timetable db is <' + previous_db + '>')
    except IndexError:
        logger.log('SQL', 'No previous sql-file. Skip file comparison for differences in timetables')
        return False
    # Подключение к базам данных расписания
    conn = connection_to_sql(last_db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("ATTACH ? AS db2", (previous_db,))
    c.execute("SELECT * FROM main.timetable EXCEPT SELECT * FROM db2.timetable")
    difference = c.fetchall()
    c.close()
    conn.close()
    if not difference:
        logger.log('SQL', 'No differences in timetables')
        return False
    # Запись разницы в списки
    list_with_send_request = []
    list_with_send_request_next = []
    for row in difference:
        for day in range(0,7):
            if date_request(day_of_week=day, for_db='YES') == str(row['Date']):
                if not row['Name'] in list_with_send_request:
                    list_with_send_request += [row['Name']]
                if not row['Group'] in list_with_send_request:
                    list_with_send_request += [row['Group']]
            elif date_request(day_of_week=day, for_db='YES', next='YES') == str(row['Date']):
                if not row['Name'] in list_with_send_request_next:
                    list_with_send_request_next += [row['Name']]
                if not row['Group'] in list_with_send_request_next:
                    list_with_send_request_next += [row['Group']]
    logger.log('SQL', 'Got the differences. Trying to send them to users')
    if send_notifications_email(list_now=list_with_send_request, list_next=list_with_send_request_next) is True:
        logger.log('SQL', 'Successfully sent the differences by email')
    elif send_notifications_vk_chat(list_now=list_with_send_request, list_next=list_with_send_request_next) is True:
        logger.log('SQL', 'Successfully sent the differences by vk_chat')
    elif send_notifications_vk_user(list_now=list_with_send_request, list_next=list_with_send_request_next) is True:
        logger.log('SQL', 'Successfully sent the differences by vk_user')


# Поиск группы и преподавателя в запросе и добавление их в параметры
def search_group_and_teacher_in_request(request: str, email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    """
    Поступает запрос -> смотрим, существуют ли такие данные в бд расписания
    есть - добавляем в базу данных пользователя, нет - ищем возможные совпадения из бд расписания ->
    -> совпадения есть - отправляем пользователю возможные варианты, нет - отправляем False

    Нужно учесть что функция не должна быть False, для её отображения пользователю
    """
    logger.log('SQL', 'Search request "' + request + '" in groups and teachers...')
    if len(request) <= 2:
        logger.log('SQL', 'Request "' + request + '" <= 2 symbols, skip')
        return 'Запрос должен содержать минимум 3 символа'
    timetable_db = get_latest_file('timetable-dbs/*.db')
    if timetable_db is None:
        logger.error('Cant search groups and teachers in request because no timetable-db exists')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    conn = connection_to_sql(timetable_db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM timetable')
    timetable_rows = c.fetchall()
    matched_group = []
    matched_teacher = []
    # Ищет группы и преподавателей для переданного запроса и сохраняет их в свой список для дальнейшего по ним поиска
    for row in timetable_rows:
        # Преподаватели
        if request.find(row['Name']) != -1 and not row['Name'] in matched_teacher:
            matched_teacher += [row['Name']]
        # Группы
        if request.find(row['Group']) != -1 and not row['Group'] in matched_group:
            matched_group += [row['Group']]
    # Если есть хоть одна распознанная группа или преподаватель
    if matched_group or matched_teacher:
        # Закрываем подключение, так как будем работать с другой бд
        c.close()
        conn.close()
        # Почта
        if email is not None and (vk_id_chat is None and vk_id_user is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM email WHERE email = ?', (email,))
            email_row = c.fetchone()
            # Если запись в бд есть
            if email_row:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if email_row['teacher'] is not None:
                            if email_row['teacher'].find(i) != -1:
                                response_teacher += i + ' '
                if matched_group:
                    for j in matched_group:
                        if email_row['group_id'] is not None:
                            if email_row['group_id'].find(j) != -1:
                                response_group += j + ' '
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
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if str(email_row['teacher']).find(str(i)) == -1:
                            email_row_at_now = c.execute('SELECT * FROM email WHERE email = ?', (email,)).fetchone()[
                                'teacher']
                            if email_row_at_now is not None:
                                c.execute('UPDATE email SET teacher = ? WHERE email = ?',
                                          (email_row_at_now + '\n' + i, email))
                                response_teacher += ' ' + i
                            else:
                                c.execute('UPDATE email SET teacher = ? WHERE email = ?', (i, email))
                                response_teacher += i
                if matched_group:
                    for i in matched_group:
                        if str(email_row['group_id']).find(str(i)) == -1:
                            email_row_at_now = c.execute('SELECT * FROM email WHERE email = ?', (email,)).fetchone()[
                                'group_id']
                            if email_row_at_now is not None:
                                c.execute('UPDATE email SET group_id = ? WHERE email = ?',
                                          (email_row_at_now + '\n' + i, email))
                                response_group += ' ' + i
                            else:
                                c.execute('UPDATE email SET group_id = ? WHERE email = ?', (i, email))
                                response_group += i
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то Enter не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response == '' and response_group != '':
                    response += 'Добавлены группы: ' + response_group
                elif response != '' and response_group != '':
                    response += '\nДобавлены группы: ' + response_group
                # Сохранение изменений и закрытие подключения
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" to email <' + email + '>')
            # Если записей нет для этой почты, то создаем новую
            else:
                logger.log('SQL', 'No values found for email <' + email + '>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                # Обработка строк для добавление в базу данных
                if matched_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            insert_teacher += i
                        else:
                            insert_teacher += i + '\n'
                # Для выставления NULL в базе данных
                else:
                    insert_teacher = None
                if matched_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            insert_group += i
                        else:
                            insert_group += i + '\n'
                # Для выставления NULL в базе данных
                else:
                    insert_group = None
                c.execute('INSERT INTO email (email, group_id, teacher, notification) VALUES (?, ?, ?, 1)',
                          (email, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                # Вывод добавленных преподавателей и групп для пользователя
                if insert_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            response_teacher += i
                        else:
                            response_teacher += i + ' '
                if insert_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            response_group += i
                        else:
                            response_group += i + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Добавлены группы: ' + response_group
                logger.log('SQL', 'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" to email <' + email + '>')
            return response
        # ВК чат
        elif vk_id_chat is not None and (email is None and vk_id_user is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
            vk_chat_row = c.fetchone()
            # Если запись в бд есть
            if vk_chat_row:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if vk_chat_row['teacher'] is not None:
                            if vk_chat_row['teacher'].find(i) != -1:
                                response_teacher += i + ' '
                if matched_group:
                    for j in matched_group:
                        if vk_chat_row['group_id'] is not None:
                            if vk_chat_row['group_id'].find(j) != -1:
                                response_group += j + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Уже сохранены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Уже сохранены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Уже сохранены группы: ' + response_group
                # Поиск значений, которых нет в базе данных и добавление их
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if str(vk_chat_row['teacher']).find(str(i)) == -1:
                            vk_chat_row_at_now = c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,)).fetchone()[
                                'teacher']
                            if vk_chat_row_at_now is not None:
                                c.execute('UPDATE vk_chat SET teacher = ? WHERE vk_id = ?',
                                          (vk_chat_row_at_now + '\n' + i, vk_id_chat))
                                response_teacher += ' ' + i
                            else:
                                c.execute('UPDATE vk_chat SET teacher = ? WHERE vk_id = ?', (i, vk_id_chat))
                                response_teacher += i
                if matched_group:
                    for i in matched_group:
                        if str(vk_chat_row['group_id']).find(str(i)) == -1:
                            vk_chat_row_at_now = c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,)).fetchone()[
                                'group_id']
                            if vk_chat_row_at_now is not None:
                                c.execute('UPDATE vk_chat SET group_id = ? WHERE vk_id = ?',
                                          (vk_chat_row_at_now + '\n' + i, vk_id_chat))
                                response_group += ' ' + i
                            else:
                                c.execute('UPDATE vk_chat SET group_id = ? WHERE vk_id = ?', (i, vk_id_chat))
                                response_group += i
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то Enter не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response == '' and response_group != '':
                    response += 'Добавлены группы: ' + response_group
                elif response != '' and response_group != '':
                    response += '\nДобавлены группы: ' + response_group
                # Сохранение изменений и закрытие подключения
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL',
                           'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" to vk chat <' + vk_id_chat + '>')
            # Если записей нет, то создаем новую
            else:
                logger.log('SQL', 'No values found for vk chat <' + vk_id_chat + '>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                # Обработка строк для добавление в базу данных
                if matched_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            insert_teacher += i
                        else:
                            insert_teacher += i + '\n'
                # Для выставления NULL в базе данных
                else:
                    insert_teacher = None
                if matched_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            insert_group += i
                        else:
                            insert_group += i + '\n'
                # Для выставления NULL в базе данных
                else:
                    insert_group = None
                c.execute('INSERT INTO vk_chat (vk_id, group_id, teacher, notification) VALUES (?, ?, ?, 1)',
                          (vk_id_chat, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                # Вывод добавленных преподавателей и групп для пользователя
                if insert_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            response_teacher += i
                        else:
                            response_teacher += i + ' '
                if insert_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            response_group += i
                        else:
                            response_group += i + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Добавлены группы: ' + response_group
                logger.log('SQL',
                           'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" to vk_chat <' + vk_id_chat + '>')
            return response
        # ВК пользователь
        elif vk_id_user is not None and (email is None and vk_id_chat is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
            vk_user_row = c.fetchone()
            # Если запись в бд есть
            if vk_user_row:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if vk_user_row['teacher'] is not None:
                            if vk_user_row['teacher'].find(i) != -1:
                                response_teacher += i + ' '
                if matched_group:
                    for j in matched_group:
                        if vk_user_row['group_id'] is not None:
                            if vk_user_row['group_id'].find(j) != -1:
                                response_group += j + ' '
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
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if str(vk_user_row['teacher']).find(str(i)) == -1:
                            vk_user_row_at_now = c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,)).fetchone()[
                                'teacher']
                            if vk_user_row_at_now is not None:
                                c.execute('UPDATE vk_user SET teacher = ? WHERE vk_id = ?',
                                          (vk_user_row_at_now + '\n' + i, vk_id_user))
                                response_teacher += ' ' + i
                            else:
                                c.execute('UPDATE vk_user SET teacher = ? WHERE vk_id = ?', (i, vk_id_user))
                                response_teacher += i
                if matched_group:
                    for i in matched_group:
                        if str(vk_user_row['group_id']).find(str(i)) == -1:
                            vk_user_row_at_now = c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,)).fetchone()[
                                'group_id']
                            if vk_user_row_at_now is not None:
                                c.execute('UPDATE vk_user SET group_id = ? WHERE vk_id = ?',
                                          (vk_user_row_at_now + '\n' + i, vk_id_user))
                                response_group += ' ' + i
                            else:
                                c.execute('UPDATE vk_user SET group_id = ? WHERE vk_id = ?', (i, vk_id_user))
                                response_group += i
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то Enter не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response == '' and response_group != '':
                    response += 'Добавлены группы: ' + response_group
                elif response != '' and response_group != '':
                    response += '\nДобавлены группы: ' + response_group
                # Сохранение изменений и закрытие подключения
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL',
                           'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" to vk user <' + vk_id_user + '>')
            # Если записей нет для этой почты, то создаем новую
            else:
                logger.log('SQL', 'No values found for vk user <' + vk_id_user + '>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                # Обработка строк для добавление в базу данных
                if matched_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            insert_teacher += i
                        else:
                            insert_teacher += i + '\n'
                # Для выставления NULL в базе данных
                else:
                    insert_teacher = None
                if matched_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            insert_group += i
                        else:
                            insert_group += i + '\n'
                # Для выставления NULL в базе данных
                else:
                    insert_group = None
                c.execute('INSERT INTO vk_user (vk_id, group_id, teacher, notification) VALUES (?, ?, ?, 1)',
                          (vk_id_user, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                # Вывод добавленных преподавателей и групп для пользователя
                if insert_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            response_teacher += i
                        else:
                            response_teacher += i + ' '
                if insert_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            response_group += i
                        else:
                            response_group += i + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Добавлены группы: ' + response_group
                logger.log('SQL',
                           'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" to vk user <' + vk_id_user + '>')
            return response
        else:
            logger.error('Incorrect request to search groups and teachers')
            return False
    # Если ничего не распознано, то ищем возможные варианты, что хотел написать пользователь
    else:
        logger.log('SQL', 'No recognized groups or teachers. Start search suggestions...')
        """
        Пльзователи могут (и часто делают) написать фамилию с пробелом в инициалах
        Поэтому делаем проверку на количество символов, чтобы определить, что это точно фамилия
        И убираем последние 4 символа, чего должно быть достаточно, чтобы распознать фамилию
        
        Если меньше 6 символов, то это скорее всего группа, поэтому ищем весь запрос
        """
        if len(request) > 5:
            request_mod = '%' + request[:-4] + '%'
        else:
            request_mod = '%' + request + '%'
        # Поиск в базе данных для группы
        c.execute('SELECT * FROM timetable WHERE "Group" LIKE ?', (request_mod,))
        records_group = c.fetchall()
        # Поиск в базе данных для преподавателя
        c.execute('SELECT * FROM timetable WHERE "Name" LIKE ?', (request_mod,))
        records_teacher = c.fetchall()
        c.close()
        conn.close()
        # Перебор полученных значений
        response = ''
        # Если нашлась хоть одна группа
        if records_group is not None:
            for row in records_group:
                if response.find(row['Group']) == -1:
                    response += row['Group'] + '\n'
        # Если есть хоть один преподаватель
        if records_teacher is not None:
            for row in records_teacher:
                if response.find(row['Name']) == -1:
                    response += row['Name'] + '\n'
        # Если есть хоть одно предположение
        if response:
            logger.log('SQL', 'Suggestions found for request "' + request + '"')
            return 'Возможно вы имели ввиду:\n' + response
        else:
            logger.log('SQL', 'No suggestions found for request "' + request + '"')
            return False


# Включение и отключение уведомлений для пользователей
def enable_and_disable_notifications(enable: str = None, disable: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        logger.log('SQL', 'Incoming request to enable or disable notifications for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Если включаем уведомления
        if enable is not None:
            c.execute('UPDATE email SET notification = ? WHERE email = ?', (1, email))
            conn.commit()
            c.close()
            conn.close()
            logger.log('SQL', 'Notifications for email <' + email + '> are enabled')
            return '\nУведомления успешно включены'
        # Если отключаем уведомления
        elif disable is not None:
            c.execute('UPDATE email SET notification = ? WHERE email = ?', (0, email))
            conn.commit()
            c.close()
            conn.close()
            logger.log('SQL', 'Notifications for email <' + email + '> are disabled')
            return '\nУведомления успешно отключены'
        # Параметры неизвестны
        else:
            c.close()
            conn.close()
            logger.error(
                'Incorrect request to enable or disable notifications for email = <' + email + '>. Enable = ' + str(
                    enable) + ' disable = ' + str(disable))
            return '\nПроизошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        logger.log('SQL', 'Incoming request to enable or disable notifications for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Если включаем уведомления
        if enable is not None:
            c.execute('UPDATE vk_chat SET notification = ? WHERE vk_id = ?', (1, vk_id_chat))
            conn.commit()
            c.close()
            conn.close()
            logger.log('SQL', 'Notifications for vk chat <' + vk_id_chat + '> are enabled')
            return 'Уведомления успешно включены'
        # Если отключаем уведомления
        elif disable is not None:
            c.execute('UPDATE vk_chat SET notification = ? WHERE vk_id = ?', (0, vk_id_chat))
            conn.commit()
            c.close()
            conn.close()
            logger.log('SQL', 'Notifications for vk chat <' + vk_id_chat + '> are disabled')
            return 'Уведомления успешно отключены'
        # Параметры неизвестны
        else:
            c.close()
            conn.close()
            logger.error(
                'Incorrect request to enable or disable notifications for vk chat = <' + vk_id_chat + '>. Enable = ' + str(
                    enable) + ' disable = ' + str(disable))
            return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        logger.log('SQL', 'Incoming request to enable or disable notifications for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Если включаем уведомления
        if enable is not None:
            c.execute('UPDATE vk_user SET notification = ? WHERE vk_id = ?', (1, vk_id_user))
            conn.commit()
            c.close()
            conn.close()
            logger.log('SQL', 'Notifications for vk user <' + vk_id_user + '> are enabled')
            return 'Уведомления успешно включены'
        # Если отключаем уведомления
        elif disable is not None:
            c.execute('UPDATE vk_user SET notification = ? WHERE vk_id = ?', (0, vk_id_user))
            conn.commit()
            c.close()
            conn.close()
            logger.log('SQL', 'Notifications for vk user <' + vk_id_user + '> are disabled')
            return 'Уведомления успешно отключены'
        # Параметры неизвестны
        else:
            c.close()
            conn.close()
            logger.error(
                'Incorrect request to enable or disable notifications for vk user = <' + vk_id_user + '>. Enable = ' + str(
                    enable) + ' disable = ' + str(disable))
            return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    else:
        logger.error('Incorrect request to enable or disable notifications. Email, vk chat and vk user are undefined')
        return '\nПроизошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# Удаление сохраненых параметров групп и преподов для пользователей
def delete_all_saved_groups_and_teachers(email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        logger.log('SQL', 'Incoming request to delete all saved groups and teachers for email = <' + email + '>')
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
                logger.log('SQL', 'All saved groups and teachers for email <' + email + '> are deleted')
                return 'Сохраненные группы и преподаватели успешно удалены'
            else:
                logger.log('SQL', 'No saved groups or teachers for email <' + email + '>')
                return 'Нет сохраненных групп или преподавателей для удаления'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No saved groups or teachers for email <' + email + '>')
            return 'Нет сохраненных групп или преподавателей для удаления'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        logger.log('SQL', 'Incoming request to delete all saved groups and teachers for vk chat = <' + vk_id_chat + '>')
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
                logger.log('SQL', 'All saved groups and teachers for vk chat <' + vk_id_chat + '> are deleted')
                return 'Сохраненные группы и преподаватели успешно удалены'
            else:
                logger.log('SQL', 'No saved groups or teachers for vk chat <' + vk_id_chat + '>')
                return 'Нет сохраненных групп или преподавателей для удаления'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No saved groups or teachers for vk chat <' + vk_id_chat + '>')
            return 'Нет сохраненных групп или преподавателей для удаления'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        logger.log('SQL', 'Incoming request to delete all saved groups and teachers for vk user = <' + vk_id_user + '>')
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
                logger.log('SQL', 'All saved groups and teachers for vk user <' + vk_id_user + '> are deleted')
                return 'Сохраненные группы и преподаватели успешно удалены'
            else:
                logger.log('SQL', 'No saved groups or teachers for vk user <' + vk_id_user + '>')
                return 'Нет сохраненных групп или преподавателей для удаления'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No saved groups or teachers for vk user <' + vk_id_user + '>')
            return 'Нет сохраненных групп или преподавателей для удаления'
    else:
        logger.error('Incorrect request to delete saved groups and teachers. Email, vk chat and vk user are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# Отображение текущих настроек
def display_saved_settings(email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        logger.log('SQL', 'Incoming request to display all saved settings for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Нет сохраненных групп и преподавателей\n'
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены преподаватели: ' + teachers_answer + '\n'
            if result['notification'] == 1:
                answer += 'Уведомления включены'
            elif result['notification'] == 0:
                answer += 'Уведомления отключены'
            logger.log('SQL', 'Display saved settings for email <' + email + '>')
            return answer
        else:
            logger.log('SQL', 'No saved settings for email <' + email + '>')
            return 'Для вас нет сохраненных параметров'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        logger.log('SQL', 'Incoming request to display all saved settings for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Нет сохраненных групп и преподавателей\n'
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены преподаватели: ' + teachers_answer + '\n'
            if result['notification'] == 1:
                answer += 'Уведомления включены'
            elif result['notification'] == 0:
                answer += 'Уведомления отключены'
            logger.log('SQL', 'Display saved settings for vk chat <' + vk_id_chat + '>')
            return answer
        else:
            logger.log('SQL', 'No saved settings for vk chat <' + vk_id_chat + '>')
            return 'Нет сохраненных параметров'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        logger.log('SQL', 'Incoming request to display all saved settings for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Нет сохраненных групп и преподавателей\n'
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены преподаватели: ' + teachers_answer + '\n'
            if result['notification'] == 1:
                answer += 'Уведомления включены'
            elif result['notification'] == 0:
                answer += 'Уведомления отключены'
            logger.log('SQL', 'Display saved settings for vk user <' + vk_id_user + '>')
            return answer
        else:
            logger.log('SQL', 'No saved settings for vk user <' + vk_id_user + '>')
            return 'Для вас нет сохраненных параметров'
    else:
        logger.error('Incorrect request to delete saved groups and teachers. Email, vk chat and vk user are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# Получение расписания для пользователя
def getting_timetable_for_user(next: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        logger.log('SQL', 'Incoming timetable request for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        email_row = c.fetchone()
        c.close()
        conn.close()
        if email_row is not None:
            teachers_answer = ''
            groups_answer = ''
            if email_row['group_id'] is None and email_row['teacher'] is None:
                logger.log('SQL', 'No saved groups or teachers for email <' + email + '>')
                return 'Нет сохраненных групп или преподавателей для получения расписания'
            if email_row['teacher'] is not None:
                teachers = str(email_row['teacher']).split('\n')
                for i in teachers:
                    teachers_answer += timetable(teacher=str(i), next=next) + '\n'
            if email_row['group_id'] is not None:
                groups = str(email_row['group_id']).split('\n')
                for i in groups:
                    groups_answer += timetable(group=str(i), next=next) + '\n'
            logger.log('SQL', 'Response to timetable request for email <' + email + '>')
            return groups_answer + teachers_answer
        else:
            logger.log('SQL', 'No saved groups or teachers for email <' + email + '>')
            return 'Нет сохраненных групп или преподавателей для получения расписания'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        logger.log('SQL', 'Incoming timetable request for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        vk_chat_row = c.fetchone()
        c.close()
        conn.close()
        if vk_chat_row is not None:
            teachers_answer = ''
            groups_answer = ''
            if vk_chat_row['group_id'] is None and vk_chat_row['teacher'] is None:
                logger.log('SQL', 'No saved groups or teachers for vk chat <' + vk_id_chat + '>')
                return 'Нет сохраненных групп или преподавателей для получения расписания'
            if vk_chat_row['teacher'] is not None:
                teachers = str(vk_chat_row['teacher']).split('\n')
                for i in teachers:
                    teachers_answer += timetable(teacher=str(i), next=next) + '\n'
            if vk_chat_row['group_id'] is not None:
                groups = str(vk_chat_row['group_id']).split('\n')
                for i in groups:
                    groups_answer += timetable(group=str(i), next=next) + '\n'
            logger.log('SQL', 'Response to timetable request for vk chat <' + vk_id_chat + '>')
            return groups_answer + teachers_answer
        else:
            logger.log('SQL', 'No saved groups or teachers for vk chat <' + vk_id_chat + '>')
            return 'Нет сохраненных групп или преподавателей для получения расписания'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        logger.log('SQL', 'Incoming timetable request for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        vk_user_row = c.fetchone()
        c.close()
        conn.close()
        if vk_user_row is not None:
            teachers_answer = ''
            groups_answer = ''
            if vk_user_row['group_id'] is None and vk_user_row['teacher'] is None:
                logger.log('SQL', 'No saved groups or teachers for vk user <' + vk_id_user + '>')
                return 'Нет сохраненных групп или преподавателей для получения расписания'
            if vk_user_row['teacher'] is not None:
                teachers = str(vk_user_row['teacher']).split('\n')
                for i in teachers:
                    teachers_answer += timetable(teacher=str(i), next=next) + '\n'
            if vk_user_row['group_id'] is not None:
                groups = str(vk_user_row['group_id']).split('\n')
                for i in groups:
                    groups_answer += timetable(group=str(i), next=next) + '\n'
            logger.log('SQL', 'Response to timetable request for vk user <' + vk_id_user + '>')
            return groups_answer + teachers_answer
        else:
            logger.log('SQL', 'No saved groups or teachers for vk user <' + vk_id_user + '>')
            return 'Нет сохраненных групп или преподавателей для получения расписания'
    else:
        logger.error('Incorrect timetable request. Email, vk chat and vk user are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


with logger.catch():
    print(getting_timetable_for_user(email='1'))

