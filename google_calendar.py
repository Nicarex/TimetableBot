from logger import logger
from other import connection_to_sql, get_latest_file
from sqlite3 import Row
import time
import random

from socket import gaierror
from http.client import RemoteDisconnected
from httplib2.error import ServerNotFoundError
from googleapiclient.errors import HttpError

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


# Удаление всех записей из календаря
def delete_all_events_in_calendar(teacher: str = None, group_id: str = None):
    if teacher is not None and group_id is None:
        logger.log('CALENDAR', f'Request to delete all events for teacher = "{str(teacher)}"')
        conn = connection_to_sql(name='calendars_list.db')
        conn.row_factory = Row
        c = conn.cursor()
        calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
        c.close()
        conn.close()
        if calendar_row:
            calendar = GoogleCalendar(calendar=str(calendar_row['calendar_id']), credentials_path='calendar-config.json', token_path='calendar-token.pickle')
            calendar.clear()
            logger.log('CALENDAR', f'Calendar for teacher = {str(teacher)} has been cleared')
        else:
            logger.log('CALENDAR', f'Calendar doesnt exist for teacher = {str(teacher)}')
            return False
    elif group_id is not None and teacher is None:
        logger.log('CALENDAR', f'Request to delete all events for group = "{str(group_id)}"')
        conn = connection_to_sql(name='calendars_list.db')
        conn.row_factory = Row
        c = conn.cursor()
        calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group_id,)).fetchone()
        c.close()
        conn.close()
        if calendar_row:
            calendar = GoogleCalendar(calendar=str(calendar_row['calendar_id']), credentials_path='calendar-config.json', token_path='calendar-token.pickle')
            calendar.clear()
            logger.log('CALENDAR', f'Calendar for group = {str(group_id)} has been cleared')
        else:
            logger.log('CALENDAR', f'Calendar doesnt exist for group = {str(group_id)}')
            return False
    else:
        logger.error('Incorrect request to delete all events in calendar. Teacher and group_id are None')
        return False


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
            # Удаление всех записей из календаря
            calendar.clear()
            return False
        except gaierror or RemoteDisconnected:
            logger.error('Internet was disconnected while import timetable to calendar. Wait 60 seconds...')
            time.sleep(60)
        except ServerNotFoundError:
            logger.error('Cant import timetable to calendar because internet is disconnected')
            return False
        except HttpError as err:
            if err.status_code == 403 or err.status_code == 429:
                wait_seconds_to_retry = random.randint(1, 10)
                time.sleep(wait_seconds_to_retry)
                logger.log('CALENDAR', f'Too many requests to Google in one minute - Rate Limit Exceeded, wait <{str(wait_seconds_to_retry)}> seconds to retry')
            else:
                raise
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
            shared_url = f"https://calendar.google.com/calendar/ical/{str(response_calendar['id']).replace('@', '%40')}/public/basic.ics"
            c.execute(sql_query_acl, (shared_url,))
            conn.commit()
            c.close()
            conn.close()
            logger.log('CALENDAR', 'Request to change calendar in Google to shared - successful')
        else:
            logger.error('Request to change calendar in Google to shared - failed')
            delete_calendar_in_google(teacher=teacher, group_id=group_id)
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
    except HttpError as err:
        if err.status_code == 403 or err.status_code == 429:
            wait_seconds_to_retry = random.randint(1, 10)
            time.sleep(wait_seconds_to_retry)
            logger.log('CALENDAR',
                       f'Too many requests to Google in one minute - Rate Limit Exceeded, wait <{str(wait_seconds_to_retry)}> seconds to retry')
        else:
            raise


# Отправляет в ответ ссылку на календарь
def show_calendar_url_to_user(email: str = None, vk_id_chat: str = None, vk_id_user: str = None):
    """
    Пользователь запрашивает календарь.
    Смотрим, от какого сервиса пришел запрос.
    На основе ответа ищем, какие сохраненные преподаватели и группы есть у пользователя.
    Сравниваем данные у пользователя с сохраненными календарями.
    Если календарь уже сохранен в бд, то отправляем ссылку на календарь пользователю.
    Если календарь запрошен впервые, то создаем новый календарь и заполняем его расписанием, отправляем пользователю ссылку.

    Если у пользователя несколько сохраненных значений, то возвращаем ссылки сразу на все календари.
    """
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None):
        logger.log('CALENDAR', f'Request to show calendar urls for email = <{str(email)}>')
        # Подключение к пользовательской бд
        conn = connection_to_sql(name='user_settings.db')
        conn.row_factory = Row
        c = conn.cursor()
        email_row = c.execute('SELECT * FROM email WHERE email = ?', (email,)).fetchone()
        c.close()
        conn.close()
        if email_row:
            # Проверка на сохраненные параметры для пользователя
            if email_row['teacher'] is None and email_row['group_id'] is None:
                logger.log('CALENDAR', f"Cant show calendar because no saved teachers and groups for email = <{str(email)}>")
                return 'Невозможно отобразить календарь, так как для вас нет сохраненных преподавателей или групп'
            teachers_list = []
            groups_list = []
            if email_row['teacher'] is not None:
                teachers_list = str(email_row['teacher'])
                teachers_list = teachers_list.replace('\r', '')
                teachers_list = teachers_list.split('\n')
            if email_row['group_id'] is not None:
                groups_list = str(email_row['group_id'])
                groups_list = groups_list.replace('\r', '')
                groups_list = groups_list.split('\n')
            # Проверка на текущую обработку запроса для пользователя
            conn = connection_to_sql(name='calendars_list.db')
            conn.row_factory = Row
            c = conn.cursor()
            processing_check = c.execute('SELECT * FROM user_processing WHERE email = ?', (email,)).fetchone()
            # Если запись есть в бд, то запрос для пользователя уже обрабатывается в данный момент
            if processing_check:
                logger.log('CALENDAR', f'The request is already being processed at now for email = <{str(email)}>')
                c.close()
                conn.close()
                return 'Ваш запрос уже обрабатывается, пожалуйста, подождите...'
            # Если запрос сейчас не обрабатывается
            else:
                c.execute('INSERT INTO user_processing (email) VALUES (?)', (email,))
                conn.commit()

            # Удаление пользователя из обработки в случае ошибки
            def delete_user_from_processing(email: str):
                conn = connection_to_sql(name='calendars_list.db')
                conn.row_factory = Row
                c = conn.cursor()
                c.execute('DELETE FROM user_processing WHERE email = ?', (email,))
                conn.commit()
                c.close()
                conn.close()
                logger.log('CALENDAR', f"Email <{str(email)}> has been deleted from user processing")
            answer = ''
            # Обработка календарей
            if teachers_list:
                for teacher in teachers_list:
                    calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
                    # Если календарь уже создан
                    if calendar_row:
                        if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                            if answer == '':
                                answer += f'Преподаватель {str(calendar_row["teacher"])}: {str(calendar_row["calendar_url"])}'
                            elif answer != '':
                                answer += f'\nПреподаватель {str(calendar_row["teacher"])}: {str(calendar_row["calendar_url"])}'
                    else:
                        result = create_shared_calendar_and_add_timetable(teacher=teacher)
                        if result is not False:
                            calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
                            if calendar_row:
                                if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                                    if answer == '':
                                        answer += f'Преподаватель {str(calendar_row["teacher"])}: {str(calendar_row["calendar_url"])}'
                                    elif answer != '':
                                        answer += f'\nПреподаватель {str(calendar_row["teacher"])}: {str(calendar_row["calendar_url"])}'
                            else:
                                logger.error('Cant show calendar url because calendar url not exists after successful creation')
                                c.close()
                                conn.close()
                                delete_user_from_processing(email=email)
                                return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
                        else:
                            logger.error('Cant show calendar url because error happened while create calendar')
                            c.close()
                            conn.close()
                            delete_user_from_processing(email=email)
                            return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
            if groups_list:
                for group in groups_list:
                    calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group,)).fetchone()
                    # Если календарь уже создан
                    if calendar_row:
                        if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                            if answer == '':
                                answer += f'Группа {str(calendar_row["group_id"])}: {str(calendar_row["calendar_url"])}'
                            elif answer != '':
                                answer += f'\nГруппа {str(calendar_row["group_id"])}: {str(calendar_row["calendar_url"])}'
                    else:
                        result = create_shared_calendar_and_add_timetable(group_id=group)
                        if result is not False:
                            calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group,)).fetchone()
                            if calendar_row:
                                if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                                    if answer == '':
                                        answer += f'Группа {str(calendar_row["group_id"])}: {str(calendar_row["calendar_url"])}'
                                    elif answer != '':
                                        answer += f'\nГруппа {str(calendar_row["group_id"])}: {str(calendar_row["calendar_url"])}'
                            else:
                                logger.error('Cant show calendar url because calendar url not exists after successful creation')
                                c.close()
                                conn.close()
                                delete_user_from_processing(email=email)
                                return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
                        else:
                            logger.error('Cant show calendar url because error happened while create calendar')
                            c.close()
                            conn.close()
                            delete_user_from_processing(email=email)
                            return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
            c.close()
            conn.close()
            if answer != '':
                answer += '\n\nНа всякий случай, напоминаю, что копировать нужно только ссылку, которая находится после двоеточия. Копировать ФИО преподавателя или номер группы не следует.\nПодробнее о настройке календаря можно прочитать в инструкции'
                delete_user_from_processing(email=email)
                return answer
            elif answer == '':
                logger.error('Cant show calendar url because answer is empty')
                delete_user_from_processing(email=email)
                return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
        else:
            logger.log('CALENDAR', f'No saved settings for email <{str(email)}>. Skip')
            return 'Для вас нет сохраненных параметров. Добавьте сначала преподавателя или группу.'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None):
        logger.log('CALENDAR', f'Request to show calendar urls for vk chat = <{str(vk_id_chat)}>')
        # Подключение к пользовательской бд
        conn = connection_to_sql(name='user_settings.db')
        conn.row_factory = Row
        c = conn.cursor()
        vk_chat_row = c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,)).fetchone()
        c.close()
        conn.close()
        if vk_chat_row:
            # Проверка на сохраненные параметры для пользователя
            if vk_chat_row['teacher'] is None and vk_chat_row['group_id'] is None:
                logger.log('CALENDAR', f"Cant show calendar because no saved teachers and groups for vk chat = <{str(vk_id_chat)}>")
                return 'Невозможно отобразить календарь, так как нет сохраненных преподавателей или групп'
            teachers_list = []
            groups_list = []
            if vk_chat_row['teacher'] is not None:
                teachers_list = str(vk_chat_row['teacher'])
                teachers_list = teachers_list.replace('\r', '')
                teachers_list = teachers_list.split('\n')
            if vk_chat_row['group_id'] is not None:
                groups_list = str(vk_chat_row['group_id'])
                groups_list = groups_list.replace('\r', '')
                groups_list = groups_list.split('\n')
            # Проверка на текущую обработку запроса для пользователя
            conn = connection_to_sql(name='calendars_list.db')
            conn.row_factory = Row
            c = conn.cursor()
            processing_check = c.execute('SELECT * FROM user_processing WHERE vk_id_chat = ?', (vk_id_chat,)).fetchone()
            # Если запись есть в бд, то запрос для пользователя уже обрабатывается в данный момент
            if processing_check:
                logger.log('CALENDAR', f'The request is already being processed at now for vk chat = <{str(vk_id_chat)}>')
                c.close()
                conn.close()
                return 'Запрос уже обрабатывается, пожалуйста, подождите...'
            # Если запрос сейчас не обрабатывается
            else:
                c.execute('INSERT INTO user_processing (vk_id_chat) VALUES (?)', (vk_id_chat,))
                conn.commit()

            # Удаление пользователя из обработки в случае ошибки
            def delete_user_from_processing(vk_id_chat: str):
                conn = connection_to_sql(name='calendars_list.db')
                conn.row_factory = Row
                c = conn.cursor()
                c.execute('DELETE FROM user_processing WHERE vk_id_chat = ?', (vk_id_chat,))
                conn.commit()
                c.close()
                conn.close()
                logger.log('CALENDAR', f"Vk chat <{str(vk_id_chat)}> has been deleted from user processing")

            answer = ''
            # Обработка календарей
            if teachers_list:
                for teacher in teachers_list:
                    calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
                    # Если календарь уже создан
                    if calendar_row:
                        if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                            if answer == '':
                                answer += f'Преподаватель {str(calendar_row["teacher"])}: {str(calendar_row["calendar_url"])}'
                            elif answer != '':
                                answer += f'\nПреподаватель {str(calendar_row["teacher"])}: {str(calendar_row["calendar_url"])}'
                    else:
                        result = create_shared_calendar_and_add_timetable(teacher=teacher)
                        if result is not False:
                            calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
                            if calendar_row:
                                if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                                    if answer == '':
                                        answer += f'Преподаватель {str(calendar_row["teacher"])}: {str(calendar_row["calendar_url"])}'
                                    elif answer != '':
                                        answer += f'\nПреподаватель {str(calendar_row["teacher"])}: {str(calendar_row["calendar_url"])}'
                            else:
                                logger.error(
                                    'Cant show calendar url because calendar url not exists after successful creation')
                                c.close()
                                conn.close()
                                delete_user_from_processing(vk_id_chat=vk_id_chat)
                                return 'При выполнении запроса произошла ошибка, пожалуйста, попробуйте позже'
                        else:
                            logger.error('Cant show calendar url because error happened while create calendar')
                            c.close()
                            conn.close()
                            delete_user_from_processing(vk_id_chat=vk_id_chat)
                            return 'При выполнении запроса произошла ошибка, пожалуйста, попробуйте позже'
            if groups_list:
                for group in groups_list:
                    calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group,)).fetchone()
                    # Если календарь уже создан
                    if calendar_row:
                        if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                            if answer == '':
                                answer += f'Группа {str(calendar_row["group_id"])}: {str(calendar_row["calendar_url"])}'
                            elif answer != '':
                                answer += f'\nГруппа {str(calendar_row["group_id"])}: {str(calendar_row["calendar_url"])}'
                    else:
                        result = create_shared_calendar_and_add_timetable(group_id=group)
                        if result is not False:
                            calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group,)).fetchone()
                            if calendar_row:
                                if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                                    if answer == '':
                                        answer += f'Группа {str(calendar_row["group_id"])}: {str(calendar_row["calendar_url"])}'
                                    elif answer != '':
                                        answer += f'\nГруппа {str(calendar_row["group_id"])}: {str(calendar_row["calendar_url"])}'
                            else:
                                logger.error(
                                    'Cant show calendar url because calendar url not exists after successful creation')
                                c.close()
                                conn.close()
                                delete_user_from_processing(vk_id_chat=vk_id_chat)
                                return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
                        else:
                            logger.error('Cant show calendar url because error happened while create calendar')
                            c.close()
                            conn.close()
                            delete_user_from_processing(vk_id_chat=vk_id_chat)
                            return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
            c.close()
            conn.close()
            if answer != '':
                answer += '\n\nНа всякий случай, напоминаю, что копировать нужно только ссылку, которая находится после двоеточия. Копировать ФИО преподавателя или номер группы не следует.\nПодробнее о настройке календаря можно прочитать в инструкции'
                delete_user_from_processing(vk_id_chat=vk_id_chat)
                return answer
            elif answer == '':
                logger.error('Cant show calendar url because answer is empty')
                delete_user_from_processing(vk_id_chat=vk_id_chat)
                return 'При выполнении вашего произошла ошибка, пожалуйста, попробуйте позже'
        else:
            logger.log('CALENDAR', f'No saved settings for vk chat <{str(vk_id_chat)}>. Skip')
            return 'Нет сохраненных параметров. Добавьте сначала преподавателя или группу.'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None):
        logger.log('CALENDAR', f'Request to show calendar urls for vk user = <{str(vk_id_user)}>')
        # Подключение к пользовательской бд
        conn = connection_to_sql(name='user_settings.db')
        conn.row_factory = Row
        c = conn.cursor()
        vk_user_row = c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,)).fetchone()
        c.close()
        conn.close()
        if vk_user_row:
            # Проверка на сохраненные параметры для пользователя
            if vk_user_row['teacher'] is None and vk_user_row['group_id'] is None:
                logger.log('CALENDAR', f"Cant show calendar because no saved teachers and groups for vk user = <{str(vk_id_user)}>")
                return 'Невозможно отобразить календарь, так как для вас нет сохраненных преподавателей или групп'
            teachers_list = []
            groups_list = []
            if vk_user_row['teacher'] is not None:
                teachers_list = str(vk_user_row['teacher'])
                teachers_list = teachers_list.replace('\r', '')
                teachers_list = teachers_list.split('\n')
            if vk_user_row['group_id'] is not None:
                groups_list = str(vk_user_row['group_id'])
                groups_list = groups_list.replace('\r', '')
                groups_list = groups_list.split('\n')
            # Проверка на текущую обработку запроса для пользователя
            conn = connection_to_sql(name='calendars_list.db')
            conn.row_factory = Row
            c = conn.cursor()
            processing_check = c.execute('SELECT * FROM user_processing WHERE vk_id_user = ?', (vk_id_user,)).fetchone()
            # Если запись есть в бд, то запрос для пользователя уже обрабатывается в данный момент
            if processing_check:
                logger.log('CALENDAR', f'The request is already being processed at now for vk user = <{str(vk_id_user)}>')
                c.close()
                conn.close()
                return 'Ваш запрос уже обрабатывается, пожалуйста, подождите...'
            # Если запрос сейчас не обрабатывается
            else:
                c.execute('INSERT INTO user_processing (vk_id_user) VALUES (?)', (vk_id_user,))
                conn.commit()

            # Удаление пользователя из обработки в случае ошибки
            def delete_user_from_processing(vk_id_user: str):
                conn = connection_to_sql(name='calendars_list.db')
                conn.row_factory = Row
                c = conn.cursor()
                c.execute('DELETE FROM user_processing WHERE vk_id_user = ?', (vk_id_user,))
                conn.commit()
                c.close()
                conn.close()
                logger.log('CALENDAR', f"Vk user <{str(vk_id_user)}> has been deleted from user processing")

            answer = ''
            # Обработка календарей
            if teachers_list:
                for teacher in teachers_list:
                    calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
                    # Если календарь уже создан
                    if calendar_row:
                        if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                            if answer == '':
                                answer += f'Преподаватель {str(calendar_row["teacher"])}: "{str(calendar_row["calendar_url"])}"'
                            elif answer != '':
                                answer += f'\nПреподаватель {str(calendar_row["teacher"])}: "{str(calendar_row["calendar_url"])}"'
                    else:
                        result = create_shared_calendar_and_add_timetable(teacher=teacher)
                        if result is not False:
                            calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
                            if calendar_row:
                                if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                                    if answer == '':
                                        answer += f'Преподаватель {str(calendar_row["teacher"])}: "{str(calendar_row["calendar_url"])}"'
                                    elif answer != '':
                                        answer += f'\nПреподаватель {str(calendar_row["teacher"])}: "{str(calendar_row["calendar_url"])}"'
                            else:
                                logger.error(
                                    'Cant show calendar url because calendar url not exists after successful creation')
                                c.close()
                                conn.close()
                                delete_user_from_processing(vk_id_user=vk_id_user)
                                return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
                        else:
                            logger.error('Cant show calendar url because error happened while create calendar')
                            c.close()
                            conn.close()
                            delete_user_from_processing(vk_id_user=vk_id_user)
                            return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
            if groups_list:
                for group in groups_list:
                    calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group,)).fetchone()
                    # Если календарь уже создан
                    if calendar_row:
                        if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                            if answer == '':
                                answer += f'Группа {str(calendar_row["group_id"])}: "{str(calendar_row["calendar_url"])}"'
                            elif answer != '':
                                answer += f'\nГруппа {str(calendar_row["group_id"])}: "{str(calendar_row["calendar_url"])}"'
                    else:
                        result = create_shared_calendar_and_add_timetable(group_id=group)
                        if result is not False:
                            calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group,)).fetchone()
                            if calendar_row:
                                if calendar_row['calendar_id'] is not None and calendar_row['calendar_url'] is not None:
                                    if answer == '':
                                        answer += f'Группа {str(calendar_row["group_id"])}: "{str(calendar_row["calendar_url"])}"'
                                    elif answer != '':
                                        answer += f'\nГруппа {str(calendar_row["group_id"])}: "{str(calendar_row["calendar_url"])}"'
                            else:
                                logger.error(
                                    'Cant show calendar url because calendar url not exists after successful creation')
                                c.close()
                                conn.close()
                                delete_user_from_processing(vk_id_user=vk_id_user)
                                return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
                        else:
                            logger.error('Cant show calendar url because error happened while create calendar')
                            c.close()
                            conn.close()
                            delete_user_from_processing(vk_id_user=vk_id_user)
                            return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
            c.close()
            conn.close()
            if answer != '':
                answer += '\n\nНа всякий случай, напоминаю, что копировать нужно только ссылку (она находится после двоеточия в кавычках). Копировать кавычки, ФИО преподавателя или номер группы не следует.\nПодробнее о настройке календаря можно прочитать в инструкции'
                delete_user_from_processing(vk_id_user=vk_id_user)
                return answer
            elif answer == '':
                logger.error('Cant show calendar url because answer is empty')
                delete_user_from_processing(vk_id_user=vk_id_user)
                return 'При выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
        else:
            logger.log('CALENDAR', f'No saved settings for vk user <{str(vk_id_user)}>. Skip')
            return 'Для вас нет сохраненных параметров. Добавьте сначала преподавателя или группу.'
    else:
        logger.error('Incorrect request to show calendar url to user. Email, vk chat and vk user are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, повторите позже'


# with logger.catch():
#     print(show_calendar_url_to_user(vk_id_user='TEST'))
