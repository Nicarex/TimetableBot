from logger import logger
from other import connection_to_sql, get_latest_file
from sqlite3 import Row
import time

from socket import gaierror
from http.client import RemoteDisconnected
from httplib2.error import ServerNotFoundError

from gcsa.google_calendar import GoogleCalendar
from gcsa.event import Event
import pendulum

import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


# Создание сервиса календаря
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
        return service
    except Exception as e:
        logger.error(f'Failed to create service instance for {str(api_service_name)}, error: "{str(e)}"')
        return None


# Импорт расписания из бд расписания в Google календарь
def import_timetable_to_calendar(teacher: str = None, group_id: str = None):
    """
    Ищем все записи для преподавателя или группы в бд расписания.
    Сортируем полученные записи по неделе, дню и номеру занятия.
    И по дате записи добавляем их в календарь.
    Когда все отсортированные записи закончатся, возвращаем True.
    Если недошли до последней записи, то возвращаем False
    """
    logger.log('CALENDAR', f'Request to make timetable in Google calendar for teacher = "{str(teacher)}" or group = "{str(group_id)}"')
    # Получение записей из бд расписания
    db_timetable = get_latest_file('timetable-dbs/timetable*.db')
    if db_timetable is None:
        logger.error('Cant import timetable to calendar because no db-files in timetable-dbs directory')
        return False
    conn = connection_to_sql(db_timetable)
    conn.row_factory = Row
    c = conn.cursor()
    if teacher is not None and group_id is None:
        timetable_rows = c.execute('SELECT * FROM timetable WHERE "Name" = ? ORDER BY "Week", "Day", "Les", "Group", "Subg"', (teacher,)).fetchall()
        c.close()
        conn.close()
        conn = connection_to_sql(name='calendars_list.db')
        conn.row_factory = Row
        c = conn.cursor()
        calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
        c.close()
        conn.close()
        if not calendar_row:
            logger.error(f'Cant import timetable to calendar because no calendar exist for teacher = "{teacher}"')
            return False
    elif group_id is not None and teacher is None:
        timetable_rows = c.execute('SELECT * FROM timetable WHERE "Group" = ? ORDER BY "Week", "Day", "Les", "Subg"', (group_id,)).fetchall()
        c.close()
        conn.close()
        conn = connection_to_sql(name='calendars_list.db')
        conn.row_factory = Row
        c = conn.cursor()
        calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group_id,)).fetchone()
        c.close()
        conn.close()
        if not calendar_row:
            logger.error(f'Cant import timetable to calendar because no calendar exist for group = "{group_id}"')
            return False
    else:
        logger.error('Incorrect request to import timetable to calendar. Teacher and group_id are None')
        c.close()
        conn.close()
        return False
    # Добавление записей в календарь
    calendar = GoogleCalendar(calendar=str(calendar_row['calendar_id']), credentials_path='calendar-config.json', token_path='calendar-token.pickle')
    exclude_row = []
    logger.log('CALENDAR', f'Start import timetable to calendar = <{str(calendar_row["calendar_id"])}>')
    for index, elem in enumerate(timetable_rows):
        # Пропуск строки, если она есть в переменной
        if exclude_row:
            if elem in exclude_row:
                continue
        # Дата
        if str(elem['Les']) == '1':
            start_time = pendulum.from_format(string=f"{str(elem['Date'])} 09:00", fmt='D-MM-YYYY HH:mm', tz='Europe/Moscow')
            end_time = pendulum.from_format(string=f"{str(elem['Date'])} 10:30", fmt='D-MM-YYYY HH:mm', tz='Europe/Moscow')
        elif str(elem['Les']) == '2':
            start_time = pendulum.from_format(string=f"{str(elem['Date'])} 10:45", fmt='D-MM-YYYY HH:mm', tz='Europe/Moscow')
            end_time = pendulum.from_format(string=f"{str(elem['Date'])} 12:15", fmt='D-MM-YYYY HH:mm', tz='Europe/Moscow')
        elif str(elem['Les']) == '3':
            start_time = pendulum.from_format(string=f"{str(elem['Date'])} 12:30", fmt='D-MM-YYYY HH:mm', tz='Europe/Moscow')
            end_time = pendulum.from_format(string=f"{str(elem['Date'])} 14:00", fmt='D-MM-YYYY HH:mm', tz='Europe/Moscow')
        elif str(elem['Les']) == '4':
            start_time = pendulum.from_format(string=f"{str(elem['Date'])} 14:45", fmt='D-MM-YYYY HH:mm', tz='Europe/Moscow')
            end_time = pendulum.from_format(string=f"{str(elem['Date'])} 16:15", fmt='D-MM-YYYY HH:mm', tz='Europe/Moscow')
        elif str(elem['Les']) == '5':
            start_time = pendulum.from_format(string=f"{str(elem['Date'])} 16:25", fmt='D-MM-YYYY HH:mm', tz='Europe/Moscow')
            end_time = pendulum.from_format(string=f"{str(elem['Date'])} 17:55", fmt='D-MM-YYYY HH:mm', tz='Europe/Moscow')
        else:
            logger.error('Incorrect lesson value = ' + str(elem['Les']))
            return False
        # Формирование строки с расписанием
        timetable_string = ''
        if teacher is not None and group_id is None:
            # Строка в зависимости от темы
            if elem['Themas'] is not None:
                timetable_string = f'({str(elem["Subj_type"])}) {str(elem["Themas"])} {str(elem["Subject"])}{str(elem["Aud"])} {str(elem["Group"])} гр.'
            elif elem['Themas'] is None:
                timetable_string = f'({str(elem["Subj_type"])}) {str(elem["Subject"])}{str(elem["Aud"])} {str(elem["Group"])} гр.'

            # Обработка нескольких групп на одном занятии
            for i in range(1, 11):
                # Если есть такой элемент в списке
                if index+i < len(timetable_rows):
                    if str(timetable_rows[index+i]['Date']) == str(elem['Date']) and str(timetable_rows[index+i]['Les']) == str(elem['Les']):
                        timetable_string += f" {str(timetable_rows[index+i]['Group'])} гр."
                        exclude_row += [timetable_rows[index+i]]
        elif group_id is not None and teacher is None:
            # Строка в зависимости от темы
            if elem['Themas'] is not None:
                timetable_string = f'({str(elem["Subj_type"])}) {str(elem["Themas"])} {str(elem["Subject"])}{str(elem["Aud"])}'
            elif elem['Themas'] is None:
                timetable_string = f'({str(elem["Subj_type"])}) {str(elem["Subject"])}{str(elem["Aud"])}'
            # Обработка нескольких подгрупп для одной группы
            for i in range(1, 8):
                # Если есть такой элемент в списке
                if index + i < len(timetable_rows):
                    if str(timetable_rows[index+i]['Date']) == str(elem['Date']) and str(timetable_rows[index+i]['Les']) == str(elem['Les']):
                        if str(timetable_rows[index+i]['Aud']) != str(elem['Aud']):
                            timetable_string += f"{str(timetable_rows[index+i]['Aud'])}"
                        exclude_row += [timetable_rows[index+i]]
        # Создание события для календаря
        event = Event(
            summary=timetable_string,
            start=start_time,
            end=end_time)
        # Добавление события в календарь
        try:
            calendar.add_event(event)
        except KeyboardInterrupt:
            logger.log('CALENDAR', f'Import timetable to calendar has been stopped by Ctrl+C')
            calendar.clear()
            return False
        except gaierror or RemoteDisconnected:
            logger.error('Internet was disconnected while import timetable to calendar. Wait 60 seconds...')
            time.sleep(60)
        except ServerNotFoundError:
            logger.error('Cant import timetable to calendar because internet is disconnected')
            return False
    logger.log('CALENDAR', f'Import timetable to calendar = <{str(calendar_row["calendar_id"])}> has been finished')


# Создание календаря для преподавателя или группы
def create_shared_calendar_and_add_timetable(teacher: str = None, group_id: str = None):
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

    # Удаление записи в бд календарей в случае ошибки
    def delete_row_in_calendar_db(teacher: str = None, group_id: str = None):
        conn = connection_to_sql(name='calendars_list.db')
        conn.row_factory = Row
        c = conn.cursor()
        if teacher is not None:
            c.execute('DELETE FROM calendars WHERE teacher = ?', (teacher,))
        elif group_id is not None:
            c.execute('DELETE FROM calendars WHERE group_id = ?', (group_id,))
        conn.commit()
        c.close()
        conn.close()
        logger.log('CALENDAR', f'Successful delete row in calendar db for teacher = "{str(teacher)}" or group = "{str(group_id)}"')

    # Удаление календаря в Google, если он был создан
    def delete_calendar_in_google(teacher: str = None, group_id: str = None):
        conn = connection_to_sql(name='calendars_list.db')
        conn.row_factory = Row
        c = conn.cursor()
        if teacher is not None:
            calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
        elif group_id is not None:
            calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group_id,)).fetchone()
        else:
            return False
        c.close()
        conn.close()
        if calendar_row:
            if calendar_row['calendar_id'] is not None:
                # Авторизация
                service = create_calendar_service(client_secret_file='calendar-config.json', token_file='calendar-token.pickle')
                service.calendars().delete(calendarId=str(calendar_row['calendar_id'])).execute()
                logger.log('CALENDAR', f'Successful delete calendar in Google for teacher = "{str(teacher)}" or group = "{str(group_id)}"')
    # Выполнение API запросов
    try:
        # Авторизация
        service = create_calendar_service(client_secret_file='calendar-config.json', token_file='calendar-token.pickle')
        # Создание календаря
        create_body = {}
        sql_query = ''
        if teacher is not None:
            # Преподаватель
            create_body = {
                'description': 'Расписание занятий для преподавателя ' + teacher,
                'summary': teacher,
                'timeZone': 'Europe/Moscow'
            }
            sql_query = f'WHERE teacher = "{teacher}"'
        elif group_id is not None:
            # Группа
            create_body = {
                'description': 'Расписание занятий для группы ' + group_id,
                'summary': group_id,
                'timeZone': 'Europe/Moscow'
            }
            sql_query = f'WHERE group_id = "{group_id}"'
        response_calendar = service.calendars().insert(body=create_body).execute()
        # Проверка ответа на правильность
        if response_calendar['id']:
            conn = connection_to_sql(calendar_db)
            c = conn.cursor()
            sql_query_create = f'UPDATE calendars SET calendar_id = ? {sql_query}'
            c.execute(sql_query_create, (str(response_calendar['id']), ))
            conn.commit()
            c.close()
            conn.close()
            logger.log('CALENDAR', 'Request to create calendar in Google - successful')
        else:
            logger.error('Request to create calendar in Google - failed')
            delete_row_in_calendar_db(teacher=teacher, group_id=group_id)
            return False
        # Включение общего доступа
        acl_body = {
            'role': 'reader',
            'scope': {
                'type': 'default'
            }
        }
        response_acl = service.acl().insert(calendarId=response_calendar['id'], body=acl_body).execute()
        # Проверка ответа на правильность
        if response_acl['scope']['type'] == 'default' and response_acl['role'] == 'reader':
            conn = connection_to_sql(calendar_db)
            c = conn.cursor()
            sql_query_acl = 'UPDATE calendars SET calendar_url = ?' + sql_query
            shared_url = f"https://calendar.google.com/calendar/ical/{str(response_calendar['id']).replace('@', '%40')}'/public/basic.ics"
            c.execute(sql_query_acl, (shared_url,))
            conn.commit()
            c.close()
            conn.close()
            logger.log('CALENDAR', 'Request to change calendar in Google to shared - successful')
        else:
            logger.error('Request to change calendar in Google to shared - failed')
            delete_row_in_calendar_db(teacher=teacher, group_id=group_id)
            return False
        # Заполнение календаря расписанием
        result = import_timetable_to_calendar(teacher=teacher, group_id=group_id)
        if result is False:
            logger.error('Cant create calendar because import timetable to calendar is failed')
            delete_calendar_in_google(teacher=teacher, group_id=group_id)
            delete_row_in_calendar_db(teacher=teacher, group_id=group_id)
    except KeyboardInterrupt:
        logger.log('CALENDAR', 'Calendar creation has been stopped by Ctrl+C')
        delete_calendar_in_google(teacher=teacher, group_id=group_id)
        delete_row_in_calendar_db(teacher=teacher, group_id=group_id)
        return False
    except gaierror or RemoteDisconnected:
        logger.error('Internet was disconnected while create calendar. Wait 60 seconds...')
        time.sleep(60)
    except ServerNotFoundError:
        logger.error('Cant create calendar because internet is disconnected')
        delete_row_in_calendar_db(teacher=teacher, group_id=group_id)
        return False


# with logger.catch():
    # create_shared_calendar(teacher='Синдеев С.А.')
    # create_shared_calendar_and_add_timetable(group_id='316')


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
    Пользователь запрашивает календарь.
    Смотрим, от какого сервиса пришел запрос.
    На основе ответа ищем, какие сохраненные преподаватели и группы есть у пользователя.
    Сравниваем данные у пользователя с сохраненными календарями.
    Если календарь уже сохранен в бд, то отправляем ссылку на календарь пользователю.
    Если календарь запрошен впервые, то создаем новый календарь, делаем его общим, сохраняем данные об календаре в бд.
    Заполняем новый календарь текущим расписанием и отправляем ссылку пользователю.
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







