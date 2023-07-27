from logger import logger
from other import connection_to_sql, get_latest_file, read_config
from sqlite3 import Row
from github import Github
from urllib import request
import time
from icalendar import Calendar, Event
import pendulum


github_token = read_config(github='YES')


def create_calendar_file_with_timetable(teacher: str = None, group_id: str = None):
    if teacher is not None and group_id is None:
        # Добавление описания в календарь
        cal = Calendar()
        cal.add('prodid', '-//Generated by TimetableBot(git: nicarex).//RU')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', f'{teacher}')
        cal.add('x-wr-timezone', 'Europe/Moscow')
        cal.add('x-wr-caldesc', f'Расписание занятий для преподавателя {teacher}')
        cal.add('refresh-interval;value=duration', 'PT6H')
        cal.add('x-published-ttl', 'PT6H')
        # Получение расписания занятий из бд расписания
        db_timetable = get_latest_file('timetable-dbs/timetable*.db')
        if db_timetable is None:
            logger.error('Cant import timetable to calendar because no db-files in timetable-dbs directory')
            return False
        conn = connection_to_sql(db_timetable)
        conn.row_factory = Row
        c = conn.cursor()
        timetable_rows = c.execute(
            'SELECT * FROM timetable WHERE "Name" = ? ORDER BY "Week", "Day", "Les", "Group", "Subg"',
            (teacher,)).fetchall()
        c.close()
        conn.close()
        # Добавление занятий в календарь
        exclude_row = []
        logger.log('CALENDAR', f'Start import timetable to calendar for teacher = <{teacher}>')
        for index, elem in enumerate(timetable_rows):
            # Пропуск строки, если она есть в переменной
            if exclude_row:
                if elem in exclude_row:
                    continue
            # Создание нового события
            event = Event()
            # Дата со временем
            timezone = 'Europe/Moscow'
            if str(elem['Les']) == '1':
                now = pendulum.now(tz=timezone).format('YYYYMMDDTHHmmss')
                start_time = pendulum.from_format(string=f"{str(elem['Date'])} 09:00", fmt='D-MM-YYYY HH:mm', tz=timezone).format('YYYYMMDDTHHmmss')
                end_time = pendulum.from_format(string=f"{str(elem['Date'])} 10:30", fmt='D-MM-YYYY HH:mm', tz=timezone).format('YYYYMMDDTHHmmss')
            elif str(elem['Les']) == '2':
                now = pendulum.now(tz=timezone).format('YYYYMMDDTHHmmss')
                start_time = pendulum.from_format(string=f"{str(elem['Date'])} 10:45", fmt='D-MM-YYYY HH:mm', tz=timezone).format('YYYYMMDDTHHmmss')
                end_time = pendulum.from_format(string=f"{str(elem['Date'])} 12:15", fmt='D-MM-YYYY HH:mm', tz=timezone).format('YYYYMMDDTHHmmss')
            elif str(elem['Les']) == '3':
                now = pendulum.now(tz=timezone).format('YYYYMMDDTHHmmss')
                start_time = pendulum.from_format(string=f"{str(elem['Date'])} 12:30", fmt='D-MM-YYYY HH:mm', tz=timezone).format('YYYYMMDDTHHmmss')
                end_time = pendulum.from_format(string=f"{str(elem['Date'])} 14:00", fmt='D-MM-YYYY HH:mm', tz=timezone).format('YYYYMMDDTHHmmss')
            elif str(elem['Les']) == '4':
                now = pendulum.now(tz=timezone).format('YYYYMMDDTHHmmss')
                start_time = pendulum.from_format(string=f"{str(elem['Date'])} 14:40", fmt='D-MM-YYYY HH:mm', tz=timezone).format('YYYYMMDDTHHmmss')
                end_time = pendulum.from_format(string=f"{str(elem['Date'])} 16:10", fmt='D-MM-YYYY HH:mm', tz=timezone).format('YYYYMMDDTHHmmss')
            elif str(elem['Les']) == '5':
                now = pendulum.now(tz=timezone).format('YYYYMMDDTHHmmss')
                start_time = pendulum.from_format(string=f"{str(elem['Date'])} 16:25", fmt='D-MM-YYYY HH:mm', tz=timezone).format('YYYYMMDDTHHmmss')
                end_time = pendulum.from_format(string=f"{str(elem['Date'])} 17:55", fmt='D-MM-YYYY HH:mm', tz=timezone).format('YYYYMMDDTHHmmss')
            else:
                logger.error(f'Incorrect lesson value = <{str(elem["Les"])}>')
                return False
            # Добавление дат в событие
            event['dtstart'] = start_time
            event['dtend'] = end_time
            event['dtstamp'] = now
            event['created'] = now
            event['last-modified'] = now
            # Уникальный идентификатор события
            uid = f'{start_time}@{now}@{teacher}'
            event.add('uid', str(uid))
            # Уровень занятости
            event['transp'] = 'OPAQUE'
            # Формирование строки с расписанием
            timetable_string = ''
            # Строка в зависимости от темы
            if elem['Themas'] is not None:
                timetable_string = f'({str(elem["Subj_type"])}) {str(elem["Themas"])} {str(elem["Subject"])}{str(elem["Aud"])} {str(elem["Group"])} гр.'
            elif elem['Themas'] is None:
                timetable_string = f'({str(elem["Subj_type"])}) {str(elem["Subject"])}{str(elem["Aud"])} {str(elem["Group"])} гр.'
            groups_for_description = ''
            # Обработка нескольких групп на одном занятии
            for i in range(1, 11):
                # Если есть такой элемент в списке
                if index + i < len(timetable_rows):
                    if str(timetable_rows[index + i]['Date']) == str(elem['Date']) and str(
                            timetable_rows[index + i]['Les']) == str(elem['Les']):
                        timetable_string += f" {str(timetable_rows[index + i]['Group'])} гр."
                        groups_for_description += f' {str(timetable_rows[index + i]["Group"])}'
                        exclude_row += [timetable_rows[index + i]]
            # Добавление описания в событие
            event.add('summary', f'{timetable_string}')
            if elem['Themas'] is not None:
                event.add('description', f'Тип занятия: {str(elem["Subj_type"])}\nТема: {str(elem["Themas"])}\nПредмет: {str(elem["Subject"])}\nАудитория:{str(elem["Aud"])}\nГруппы: {str(elem["Group"])}{str(groups_for_description)}')
            else:
                event.add('description',
                          f'Тип занятия: {str(elem["Subj_type"])}\nПредмет: {str(elem["Subject"])}\nАудитория:{str(elem["Aud"])}\nГруппы: {str(elem["Group"])}{str(groups_for_description)}')
            cal.add_component(event)
        with open(f'calendars/{teacher}.ics', 'wb') as file:
            file.write(cal.to_ical())
        logger.log('CALENDAR', 'Successfully create calendar and import timetable')
        return True
    elif group_id is not None and teacher is None:
        # Добавление описания в календарь
        cal = Calendar()
        cal.add('prodid', '-//Generated by TimetableBot(git: nicarex).//RU')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', f'{group_id}')
        cal.add('x-wr-timezone', 'Europe/Moscow')
        cal.add('x-wr-caldesc', f'Расписание занятий для группы {group_id}')
        cal.add('refresh-interval;value=duration', 'PT6H')
        cal.add('x-published-ttl', 'PT6H')
        # Получение расписания занятий из бд расписания
        db_timetable = get_latest_file('timetable-dbs/timetable*.db')
        if db_timetable is None:
            logger.error('Cant import timetable to calendar because no db-files in timetable-dbs directory')
            return False
        conn = connection_to_sql(db_timetable)
        conn.row_factory = Row
        c = conn.cursor()
        timetable_rows = c.execute('SELECT * FROM timetable WHERE "Group" = ? ORDER BY "Week", "Day", "Les", "Subg"', (group_id,)).fetchall()
        c.close()
        conn.close()
        # Добавление занятий в календарь
        exclude_row = []
        logger.log('CALENDAR', f'Start import timetable to calendar for group = <{group_id}>')
        for index, elem in enumerate(timetable_rows):
            # Пропуск строки, если она есть в переменной
            if exclude_row:
                if elem in exclude_row:
                    continue
            # Создание нового события
            event = Event()
            # Дата со временем
            timezone = 'Europe/Moscow'
            if str(elem['Les']) == '1':
                now = pendulum.now(tz=timezone).format('YYYYMMDDTHHmmss')
                start_time = pendulum.from_format(string=f"{str(elem['Date'])} 09:00", fmt='D-MM-YYYY HH:mm',
                                                  tz=timezone).format('YYYYMMDDTHHmmss')
                end_time = pendulum.from_format(string=f"{str(elem['Date'])} 10:30", fmt='D-MM-YYYY HH:mm',
                                                tz=timezone).format('YYYYMMDDTHHmmss')
            elif str(elem['Les']) == '2':
                now = pendulum.now(tz=timezone).format('YYYYMMDDTHHmmss')
                start_time = pendulum.from_format(string=f"{str(elem['Date'])} 10:45", fmt='D-MM-YYYY HH:mm',
                                                  tz=timezone).format('YYYYMMDDTHHmmss')
                end_time = pendulum.from_format(string=f"{str(elem['Date'])} 12:15", fmt='D-MM-YYYY HH:mm',
                                                tz=timezone).format('YYYYMMDDTHHmmss')
            elif str(elem['Les']) == '3':
                now = pendulum.now(tz=timezone).format('YYYYMMDDTHHmmss')
                start_time = pendulum.from_format(string=f"{str(elem['Date'])} 12:30", fmt='D-MM-YYYY HH:mm',
                                                  tz=timezone).format('YYYYMMDDTHHmmss')
                end_time = pendulum.from_format(string=f"{str(elem['Date'])} 14:00", fmt='D-MM-YYYY HH:mm',
                                                tz=timezone).format('YYYYMMDDTHHmmss')
            elif str(elem['Les']) == '4':
                now = pendulum.now(tz=timezone).format('YYYYMMDDTHHmmss')
                start_time = pendulum.from_format(string=f"{str(elem['Date'])} 14:40", fmt='D-MM-YYYY HH:mm',
                                                  tz=timezone).format('YYYYMMDDTHHmmss')
                end_time = pendulum.from_format(string=f"{str(elem['Date'])} 16:10", fmt='D-MM-YYYY HH:mm',
                                                tz=timezone).format('YYYYMMDDTHHmmss')
            elif str(elem['Les']) == '5':
                now = pendulum.now(tz=timezone).format('YYYYMMDDTHHmmss')
                start_time = pendulum.from_format(string=f"{str(elem['Date'])} 16:25", fmt='D-MM-YYYY HH:mm',
                                                  tz=timezone).format('YYYYMMDDTHHmmss')
                end_time = pendulum.from_format(string=f"{str(elem['Date'])} 17:55", fmt='D-MM-YYYY HH:mm',
                                                tz=timezone).format('YYYYMMDDTHHmmss')
            else:
                logger.error(f'Incorrect lesson value = <{str(elem["Les"])}>')
                return False
            # Добавление дат в событие
            event['dtstart'] = start_time
            event['dtend'] = end_time
            event['dtstamp'] = now
            event['created'] = now
            event['last-modified'] = now
            # Уникальный идентификатор события
            uid = f'{start_time}@{now}@{group_id}'
            event.add('uid', str(uid))
            # Уровень занятости
            event['transp'] = 'OPAQUE'
            # Формирование строки с расписанием
            timetable_string = ''
            # Строка в зависимости от темы
            if elem['Themas'] is not None:
                timetable_string = f'({str(elem["Subj_type"])}) {str(elem["Themas"])} {str(elem["Subject"])}{str(elem["Aud"])}'
            elif elem['Themas'] is None:
                timetable_string = f'({str(elem["Subj_type"])}) {str(elem["Subject"])}{str(elem["Aud"])}'
            auds_for_description = ''
            teachers_for_description = ''
            # Обработка нескольких подгрупп для одной группы
            for i in range(1, 8):
                # Если есть такой элемент в списке
                if index + i < len(timetable_rows):
                    if str(timetable_rows[index + i]['Date']) == str(elem['Date']) and str(timetable_rows[index + i]['Les']) == str(elem['Les']):
                        if str(timetable_rows[index + i]['Aud']) != str(elem['Aud']):
                            timetable_string += f"{str(timetable_rows[index + i]['Aud'])}"
                            auds_for_description += f"{str(timetable_rows[index + i]['Aud'])}"
                            teachers_for_description += f" {str(timetable_rows[index + i]['Name'])}"
                        exclude_row += [timetable_rows[index + i]]
            # Добавление описания в событие
            event.add('summary', f'{timetable_string}')
            if elem['Themas'] is not None:
                event.add('description',
                          f'Тип занятия: {str(elem["Subj_type"])}\nТема: {str(elem["Themas"])}\nПредмет: {str(elem["Subject"])}\nАудитории:{str(elem["Aud"])}{str(auds_for_description)}\nПреподаватели: {str(elem["Name"])}{str(teachers_for_description)}')
            else:
                event.add('description',
                          f'Тип занятия: {str(elem["Subj_type"])}\nПредмет: {str(elem["Subject"])}\nАудитории:{str(elem["Aud"])}{str(auds_for_description)}\nПреподаватели: {str(elem["Name"])}{str(teachers_for_description)}')
            cal.add_component(event)
        with open(f'calendars/{group_id}.ics', 'wb') as file:
            file.write(cal.to_ical())
        logger.log('CALENDAR', 'Successfully create calendar and import timetable')
        return True
    else:
        logger.error('Incorrect request to create calendar file with timetable. Teacher and group_id are None')
        return False


def download_calendar_file_to_github(filename: str):
    logger.log('CALENDAR', f'Start upload calendar <{filename}> to GitHub')
    g = Github(github_token)
    try:
        repo = g.get_repo("Nicarex/timetablebot-files")
        all_files = []
        contents = repo.get_contents("")
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
            else:
                file = file_content
                all_files.append(str(file).replace('ContentFile(path="', '').replace('")', ''))

        filepath = f'calendars/{filename}.ics'

        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
        # Обновление файла в GitHub
        if filepath in all_files:
            contents = repo.get_contents(filepath)
            repo.update_file(contents.path, "update", content, contents.sha, branch="main")
            logger.log('CALENDAR', f'Calendar <{filename}> has been updated in GitHub')
            return True
        # Создание нового файла в GitHub
        else:
            repo.create_file(filepath, "create", content, branch="main")
            logger.log('CALENDAR', f'Calendar <{filename}> has been created in GitHub')
            return True
    except:
        logger.log('CALENDAR', f'Error happened while upload calendar <{filename}> to GitHub. Wait 20 seconds')
        time.sleep(20)


# Отправляет в ответ ссылку на календарь
def show_calendar_url_to_user(email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
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
    if email is not None and (vk_id_chat is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('CALENDAR', f'Request to show calendar urls for email = <{str(email)}>')
        # Подключение к пользовательской бд
        conn = connection_to_sql(name='user_settings.db')
        conn.row_factory = Row
        c = conn.cursor()
        user_row = c.execute('SELECT * FROM email WHERE email = ?', (email,)).fetchone()
        c.close()
        conn.close()
    elif vk_id_chat is not None and (email is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('CALENDAR', f'Request to show calendar urls for vk chat = <{str(vk_id_chat)}>')
        # Подключение к пользовательской бд
        conn = connection_to_sql(name='user_settings.db')
        conn.row_factory = Row
        c = conn.cursor()
        user_row = c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,)).fetchone()
        c.close()
        conn.close()
    elif vk_id_user is not None and (email is None and vk_id_chat is None and telegram is None and discord is None):
        logger.log('CALENDAR', f'Request to show calendar urls for vk user = <{str(vk_id_user)}>')
        # Подключение к пользовательской бд
        conn = connection_to_sql(name='user_settings.db')
        conn.row_factory = Row
        c = conn.cursor()
        user_row = c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,)).fetchone()
        c.close()
        conn.close()
    elif telegram is not None and (email is None and vk_id_chat is None and vk_id_user is None and discord is None):
        logger.log('CALENDAR', f'Request to show calendar urls for telegram = <{str(telegram)}>')
        # Подключение к пользовательской бд
        conn = connection_to_sql(name='user_settings.db')
        conn.row_factory = Row
        c = conn.cursor()
        user_row = c.execute('SELECT * FROM telegram WHERE telegram_id = ?', (telegram,)).fetchone()
        c.close()
        conn.close()
    elif discord is not None and (email is None and vk_id_chat is None and vk_id_user is None and telegram is None):
        logger.log('CALENDAR', f'Request to show calendar urls for discord = <{str(discord)}>')
        # Подключение к пользовательской бд
        conn = connection_to_sql(name='user_settings.db')
        conn.row_factory = Row
        c = conn.cursor()
        user_row = c.execute('SELECT * FROM discord WHERE discord_id = ?', (discord,)).fetchone()
        c.close()
        conn.close()
    else:
        logger.error('Incorrect request to show calendar url to user. Email, vk chat, vk user, telegram and discord are undefined')
        return 'Что-то пошло не так при обработке запроса, повторите позже'

    # Если есть сохраненные параметры для пользователя
    if user_row:
        # Проверка на сохраненные параметры для пользователя
        if user_row['teacher'] is None and user_row['group_id'] is None:
            logger.log('CALENDAR', f"Cant show calendar because no saved teachers and groups for email = <{str(email)}>")
            return '\nНевозможно отобразить календарь, так как для вас нет сохраненных преподавателей или групп'
        teachers_list = []
        groups_list = []
        if user_row['teacher'] is not None:
            teachers_list = str(user_row['teacher'])
            teachers_list = teachers_list.replace('\r', '')
            teachers_list = teachers_list.split('\n')
        if user_row['group_id'] is not None:
            groups_list = str(user_row['group_id'])
            groups_list = groups_list.replace('\r', '')
            groups_list = groups_list.split('\n')

        # Подключение к  бд
        conn = connection_to_sql(name='calendars_list.db')
        conn.row_factory = Row
        c = conn.cursor()

        answer = ''
        # Обработка календарей
        if teachers_list:
            for teacher in teachers_list:
                calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (teacher,)).fetchone()
                # Если календарь уже создан
                if calendar_row:
                    if calendar_row['calendar_url'] is not None:
                        if answer == '':
                            answer += f'Преподаватель {str(calendar_row["teacher"])}: {str(calendar_row["calendar_url"])}'
                        elif answer != '':
                            answer += f'\nПреподаватель {str(calendar_row["teacher"])}: {str(calendar_row["calendar_url"])}'
                    else:
                        return '\nЧто-то пошло не так при обработке календарей, попробуйте позже'
                # Если запрошенного календаря не существует, то создаем его, добавляем в Git и в бд
                else:
                    if create_calendar_file_with_timetable(
                            teacher=teacher) is True and download_calendar_file_to_github(
                            filename=teacher) is True:
                        teacher_in_unicode = request.pathname2url(teacher)
                        url = f'https://raw.githubusercontent.com/Nicarex/timetablebot-files/main/calendars/{teacher_in_unicode}.ics'
                        c.execute('INSERT INTO calendars (teacher, calendar_url) VALUES (?, ?)', (teacher, url))
                        conn.commit()
                        if answer == '':
                            answer += f'Преподаватель {teacher}: {url}'
                        elif answer != '':
                            answer += f'\nПреподаватель {teacher}: {url}'
                    else:
                        logger.error('Cant show calendar url because error happened while create calendar')
                        c.close()
                        conn.close()
                        return '\nЧто-то пошло не так при создании календарей, попробуйте позже'
        if groups_list:
            for group in groups_list:
                calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (group,)).fetchone()
                # Если календарь уже создан
                if calendar_row:
                    if calendar_row['calendar_url'] is not None:
                        if answer == '':
                            answer += f'Группа {group}: {str(calendar_row["calendar_url"])}'
                        elif answer != '':
                            answer += f'\nГруппа {group}: {str(calendar_row["calendar_url"])}'
                    else:
                        return '\nЧто-то пошло не так при обработке календарей, попробуйте позже'
                # Если запрошенного календаря не существует, то создаем его, добавляем в Git и в бд
                else:
                    if create_calendar_file_with_timetable(
                            group_id=group) is True and download_calendar_file_to_github(
                            filename=group) is True:
                        group_in_unicode = request.pathname2url(group)
                        url = f'https://raw.githubusercontent.com/Nicarex/timetablebot-files/main/calendars/{group_in_unicode}.ics'
                        c.execute('INSERT INTO calendars (group_id, calendar_url) VALUES (?, ?)', (group, url))
                        conn.commit()
                        if answer == '':
                            answer += f'Группа {group}: {url}'
                        elif answer != '':
                            answer += f'\nГруппа {group}: {url}'
                    else:
                        logger.error('Cant show calendar url because error happened while create calendar')
                        c.close()
                        conn.close()
                        return '\nЧто-то пошло не так при создании календарей, попробуйте позже'
        c.close()
        conn.close()
        if answer != '':
            answer = f'\n{answer}\n\nНа всякий случай, напоминаю, что копировать нужно только ссылку, которая находится после двоеточия. Копировать ФИО преподавателя или номер группы не следует.'
            return answer
        elif answer == '':
            logger.error('Cant show calendar url because answer is empty')
            return '\nПри выполнении вашего запроса произошла ошибка, пожалуйста, попробуйте позже'
    else:
        logger.log('CALENDAR', f'No saved settings for user to show calendar url. Skip')
        return '\nНет сохраненных параметров. Добавьте сначала преподавателя или группу.'


# with logger.catch():
    # create_calendar_file_with_timetable(group_id='307')
#     download_calendar_file_to_github(filename='')
