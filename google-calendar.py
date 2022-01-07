from logger import logger
from other import connection_to_sql, get_latest_file
from sqlite3 import Row
import time

from gcsa.google_calendar import GoogleCalendar
from gcsa.event import Event
import pendulum

import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


def create_calendar_service(client_secret_file: str, token_file: str):
    client_secret_file = client_secret_file
    api_service_name = 'calendar'
    api_version = 'v3'
    scopes = [scope for scope in ['https://www.googleapis.com/auth/calendar'][0]]
    cred = None
    with open(token_file, 'rb') as token:
            cred = pickle.load(token)
    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes)
            cred = flow.run_local_server()
        with open(token_file, 'wb') as token:
            pickle.dump(cred, token)
    try:
        service = build(api_service_name, api_version, credentials=cred)
        print(api_service_name, api_version, 'service created successfully')
        return service
    except Exception as e:
        print(e)
        print(f'Failed to create service instance for {api_service_name}')
        return None


# Импорт расписания из бд расписания в Google календарь
def import_timetable_to_calendar(teacher: str = None, group_id: str = None):
    """
    Ищем все записи для преподавателя или группы в бд расписания
    Сортируем полученные записи по неделе, дню и номеру занятия
    И по дате записи добавляем их в календарь
    Когда все отсортированные записи закончатся, возвращаем True
    Если недошли до последней записи, то возвращаем False
    """
    logger.log('CALENDAR', 'Request to make timetable in Google calendar')
    # Получение записей из бд расписания
    db_timetable = get_latest_file('timetable-dbs/timetable*.db')
    if db_timetable is None:
        logger.error('Cant import timetable to calendar because no db-files in timetable-dbs directory')
        return False
    conn = connection_to_sql(db_timetable)
    conn.row_factory = Row
    c = conn.cursor()
    if teacher is not None and group_id is None:
        timetable_rows = c.execute('SELECT * FROM timetable WHERE "Name" = ? ORDER BY "Week", "Day", "Les", "Subg"', (teacher,)).fetchall()
        # timetable_rows = iter(timetable_rows)
        c.close()
        conn.close()
    elif group_id is not None and teacher is None:
        timetable_rows = c.execute('SELECT * FROM timetable WHERE "Group" = ? ORDER BY "Week", "Day", "Les", "Subg"', (group_id,)).fetchall()
        # timetable_rows = iter(timetable_rows)
        c.close()
        conn.close()
    else:
        logger.error('Incorrect request to import timetable to calendar. Teacher and group_id are None')
        c.close()
        conn.close()
        return False

    # print(len(timetable_rows))

    # Добавление записей в календарь
    # calendar = GoogleCalendar(credentials_path='calendar-config.json', token_path='calendar-token.pickle')
    logger.log('CALENDAR', 'Successfully authorized')
    for index, elem in enumerate(timetable_rows):
        # Дата
        date = pendulum.from_format(string=str(elem['Date']), fmt='D-MM-YYYY')
        date = date.format(fmt='D / MM / YYYY')
        if elem['Les'] == 1:
            start = date[9:00]
            end = date[10:30]
        elif elem['Les'] == 2:
            start = date[10:45]
            end = date[12:15]
        elif elem['Les'] == 3:
            start = date[12:30]
            end = date[14:00]
        elif elem['Les'] == 4:
            start = date[14:45]
            end = date[16:15]
        elif elem['Les'] == 5:
            start = date[16:25]
            end = date[17:55]
        else:
            logger.error('Incorrect lesson value = ' + str(elem['Les']))
            return False

        # Строка с расписанием
        if teacher is not None and group_id is None:
            # Если есть следующий элемент списка
            if not index+1 > len(timetable_rows):
                # Если дата следующего элемента не равна дате текущего, то есть существует только одна запись для этого дня
                if timetable_rows[index+1]['Date'] != elem['Date']:

        elif group_id is not None and teacher is None:
            pass
        else:
            pass



        # event = Event(
        #     'Строка с расписанием',
        #     start=start,
        #     end=end
        # )
    logger.log('CALENDAR', 'Stop')



with logger.catch():
    import_timetable_to_calendar(teacher='Синдеев С.А.')


# Создание календаря для преподавателя или группы
def create_shared_calendar(teacher: str = None, group_id: str = None):
    """
    Получаем на вход преподавателя или группу, для которого нужно создать календарь
    Проверяем, существует ли уже календарь для переданного значения с id и url:

    Если нет, то создаем запись в бд календарей с преподавателем или группой ->
    запрашиваем создание календаря, по завершении добавляем id календаря в бд календарей ->
    делаем созданный календарь общим, по завершении добавляем общий url календаря в бд календарей
    Если на каком-то из этапов пришел неправильный ответ от гугла ->
    удаляем созданную запись в бд и возвращаем False

    Если да, то возвращаем False, так как календарь уже создан или в процессе создания
    """
    logger.log('CALENDAR', 'Request to create Google calendar')

    # Проверка на существование календаря
    calendar_db = 'calendars_list.db'
    conn = connection_to_sql(calendar_db)
    conn.row_factory = Row
    c = conn.cursor()
    if teacher is not None and group_id is None:
        calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
        if calendar_row:
            # Если запись с фамилией создана, но остальные параметры не указаны, то, по идее, календарь в процессе создания
            if calendar_row['teacher'] == teacher and (calendar_row['calendar_id'] is None or calendar_row['calendar_url'] is None):
                logger.log('CALENDAR', 'Calendar creation in progress. Skip')
                c.close()
                conn.close()
                return False
            # Если календарь уже создан с id и url
            if calendar_row['teacher'] == teacher and calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                logger.log('CALENDAR', 'Calendar has been already created. Skip')
                c.close()
                conn.close()
                return False
        else:
            logger.log('CALENDAR', 'Create new entry for teacher = "' + teacher + '"')
            c.execute('INSERT INTO calendars (teacher) VALUES (?)', (teacher,))
            conn.commit()
            c.close()
            conn.close()
    elif group_id is not None and teacher is None:
        calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group_id,)).fetchone()
        if calendar_row:
            # Если запись с группой создана, но остальные параметры не указаны, то, по идее, календарь в процессе создания
            if calendar_row['group_id'] == group_id and (calendar_row['calendar_id'] is None or calendar_row['calendar_url'] is None):
                logger.log('CALENDAR', 'Calendar creation in progress. Skip')
                c.close()
                conn.close()
                return False
            # Если календарь уже создан с id и url
            if calendar_row['group_id'] == group_id and calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                logger.log('CALENDAR', 'Calendar has been already created. Skip')
                c.close()
                conn.close()
                return False
        logger.log('CALENDAR', 'Create new entry for group = "' + group_id + '"')
        c.execute('INSERT INTO calendars (group_id) VALUES (?)', (group_id,))
        conn.commit()
        c.close()
        conn.close()
    else:
        logger.error('Incorrect request to create calendar. Teacher and group_id are None')
        c.close()
        conn.close()
        return False

    # Создание календаря
    create_body = {}
    sql_query = ''
    if teacher is not None:
        # Преподаватель
        create_body = {
            'description':      'Расписание занятий для преподавателя ' + teacher,
            'summary':          teacher,
            'timeZone':         'Europe/Moscow'
        }
        sql_query = ' WHERE teacher = "' + teacher + '"'
    elif group_id is not None:
        # Группа
        create_body = {
            'description':      'Расписание занятий для группы ' + group_id,
            'summary':          group_id,
            'timeZone':         'Europe/Moscow'
        }
        sql_query = ' WHERE group_id = "' + group_id + '"'
    try:
        service = create_calendar_service(client_secret_file='calendar-config.json', token_file='calendar-token.pickle')

        # Создание календаря
        response_calendar = service.calendars().insert(body=create_body).execute()
        if response_calendar['id']:
            conn = connection_to_sql(calendar_db)
            c = conn.cursor()
            sql_query_create = 'UPDATE calendars SET calendar_id = ?' + sql_query
            c.execute(sql_query_create, (str(response_calendar['id']), ))
            conn.commit()
            c.close()
            conn.close()
            logger.log('CALENDAR', 'Request to create calendar in Google - successful')

            # Включение общего доступа
            acl_body = {
                'role':         'reader',
                'scope': {
                    'type':     'default'
                }
            }
            response_acl = service.acl().insert(calendarId=response_calendar['id'], body=acl_body).execute()
            if response_acl['scope']['type'] == 'default' and response_acl['role'] == 'reader':
                conn = connection_to_sql(calendar_db)
                c = conn.cursor()
                sql_query_acl = 'UPDATE calendars SET calendar_url = ?' + sql_query
                shared_url = 'https://calendar.google.com/calendar/ical/' + str(response_calendar['id']).replace('@', '%40') + '/public/basic.ics'
                c.execute(sql_query_acl, (shared_url, ))
                conn.commit()
                c.close()
                conn.close()
                logger.log('CALENDAR', 'Request to change calendar in Google to shared - successful')
    except KeyboardInterrupt:
        logger.log('CALENDAR', 'Calendar creation has been stopped by Ctrl+C')
        c.close()
        conn.close()
        return 'EXIT'
    except:
        logger.error('Error happened while create calendar in Google')
        c.close()
        conn.close()
        time.sleep(60)





def search_calendar_url_in_db(email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    """
    Ищет ссылку на календарь для сохраненных пользовательских значений
    Если есть - возвращает ссылку
    Нет - отправляет False
    """
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        pass
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        pass
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        pass
    else:
        logger.error('Incorrect request to show calendar url to user. Email, vk chat and vk user are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, повторите позже'


# Отправляет в ответ ссылка на календарь
def show_calendar_url_to_user(email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    """
    Пользователь запрашивает календарь
    Смотрим, от какого сервиса пришел запрос
    На основе ответа ищем, какие сохраненные преподаватели и группы есть у пользователя
    Сравниваем данные у пользователя с сохраненными календарями
    Если календарь уже сохранен в бд, то отправляем ссылку на календарь пользователю
    Если календарь запрошен впервые, то создаем новый календарь, делаем его общим, сохраняем данные об календаре в бд
    Заполняем новый календарь текущим расписанием и отправлем ссылку пользователю
    """
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        pass
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        pass
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        pass
    else:
        logger.error('Incorrect request to show calendar url to user. Email, vk chat and vk user are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, повторите позже'







