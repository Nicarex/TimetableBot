from log import logger
from datetime import timedelta
import pendulum
from other import get_latest_file, connection_to_sql
import os
from glob import glob
from sqlite3 import Row


# Дни недели для файла расписания
days_of_week = ['ПОНЕДЕЛЬНИК - ', '\nВТОРНИК - ', '\nСРЕДА - ', '\nЧЕТВЕРГ - ', '\nПЯТНИЦА - ', '\nСУББОТА - ']
time_lesson = ['', '09:00-10:30', '10:45-12:15', '12:30-14:00', '14:45-16:15', '16:25-17:55']


# Находит и форматирует дату для поиска в базе данных
# Можно ввести значения до 6 (воскресенье)
def date_request(day_of_week: int, for_file: str = None, for_db: str = None, next: str = None):

    # Возвращает дни недели в виде словаря
    def get_week_dates(base_date, start_day, end_day=None):
        monday = base_date - timedelta(days=base_date.isoweekday() - 1)
        week_dates = [monday + timedelta(days=i) for i in range(7)]
        return week_dates[start_day - 1:end_day or start_day]

    """
    test:
    dt = pendulum.parse('2021-10-30')
    """
    # Текущее время в текущем часовом поясе
    dt = pendulum.now(tz='Europe/Moscow')
    monday = dt.start_of('week')
    monday_next = dt.next(pendulum.MONDAY)
    # Если для файла
    if for_file is not None and for_db is None:
        if next is None:
            return str(get_week_dates(monday, 1, 7)[day_of_week].format('DD.MM.YYYY'))
        else:
            return str(get_week_dates(monday_next, 1, 7)[day_of_week].format('DD.MM.YYYY'))
    # Если для базы данных
    elif for_file is None and for_db is not None:
        if next is None:
            return str(get_week_dates(monday, 1, 7)[day_of_week].format('D-MM-YYYY'))
        else:
            return str(get_week_dates(monday_next, 1, 7)[day_of_week].format('D-MM-YYYY'))
    else:
        logger.error('Incorrect request for date!')
        return None


# Название дня выводится в строку
def name_of_day_string(day: int, next: str):
    return days_of_week[day] + date_request(day, for_file='YES', next=next) + '\n'


# Генерирует строку из расписания
def subject_string(conn, day: int, lesson: int, group: str = None, teacher: str = None, next: str = next, lesson_time: str = 'YES'):
    # Если это группа
    if group is not None and teacher is None:
        c = conn.cursor()
        c.execute('SELECT * FROM timetable WHERE "Group" = ? AND Date = ? AND Les = ? ORDER BY Subg', (group, date_request(day_of_week=day, for_db='YES', next=next), lesson))
        sorted_records = c.fetchall()
        c.close()
        # Обработка пустых строк
        if not sorted_records:
            return str(lesson) + '. -'
        # Если строка с темой не пустая
        if sorted_records[0]['Themas'] is not None:
            if lesson_time == 'YES':
                full_string = str(lesson) + '. ' + str(time_lesson[lesson]) + ' (' + str(sorted_records[0]['Subj_type']) + ') ' + str(sorted_records[0]['Themas']) + ' ' + str(sorted_records[0]['Subject']) + str(sorted_records[0]['Aud'])
            else:
                full_string = str(lesson) + '. (' + str(sorted_records[0]['Subj_type']) + ') ' + str(sorted_records[0]['Themas']) + ' ' + str(sorted_records[0]['Subject']) + str(sorted_records[0]['Aud'])
            # Если подгрупп нет
            if sorted_records[0]['Subg'] == 0:
                return full_string
            # Если подгруппы есть
            elif sorted_records[0]['Subg'] == 1:
                # Если подгруппа одна, что не должно быть, то возвращаем обычную строку, т.к. скорее всего ошибка в расписании
                if len(sorted_records) == 1:
                    logger.warning('Incorrect amount of rows for subgroups')
                    return full_string
                # Если следующий кабинет равен текущему, то возврати обычную строку
                elif len(sorted_records) >= 1 and str(sorted_records[0]['Aud']) == str(sorted_records[1]['Aud']):
                    return full_string
                elif len(sorted_records) == 2:
                    return full_string + str(sorted_records[1]['Aud'])
                elif len(sorted_records) == 3:
                    return full_string + str(sorted_records[1]['Aud']) + str(sorted_records[2]['Aud'])
                elif len(sorted_records) == 4:
                    return full_string + str(sorted_records[1]['Aud']) + str(sorted_records[2]['Aud']) + str(sorted_records[3]['Aud'])
                elif len(sorted_records) == 5:
                    return full_string + str(sorted_records[1]['Aud']) + str(sorted_records[2]['Aud']) + str(sorted_records[3]['Aud']) + str(sorted_records[4]['Aud'])
                elif len(sorted_records) == 6:
                    return full_string + str(sorted_records[1]['Aud']) + str(sorted_records[2]['Aud']) + str(sorted_records[3]['Aud']) + str(sorted_records[4]['Aud']) + str(sorted_records[5]['Aud'])
                else:
                    # Если строк слишком много, то что-то пошло не так
                    logger.error('Incorrect amount of rows for subgroups')
                    return None
        # Если строка с темой пустая
        elif sorted_records[0]['Themas'] is None:
            if lesson_time == 'YES':
                short_string = str(lesson) + '. ' + str(time_lesson[lesson]) + ' (' + str(sorted_records[0]['Subj_type']) + ') ' + \
                               str(sorted_records[0]['Subject']) + str(sorted_records[0]['Aud'])
            else:
                short_string = str(lesson) + '. (' + str(sorted_records[0]['Subj_type']) + ') ' + \
                               str(sorted_records[0]['Subject']) + str(sorted_records[0]['Aud'])
            # Если подгрупп нет
            if sorted_records[0]['Subg'] == 0:
                return short_string
            # Если подгруппы есть
            elif sorted_records[0]['Subg'] == 1:
                # Если подгруппа одна, что не должно быть, то возвращаем обычную строку, т.к. скорее всего ошибка в расписании
                if len(sorted_records) == 1:
                    logger.warning('Incorrect amount of rows for subgroups')
                    return short_string
                # Если следующий кабинет равен текущему, то возврати обычную строку
                elif len(sorted_records) >= 1 and str(sorted_records[0]['Aud']) == str(sorted_records[1]['Aud']):
                    return short_string
                elif len(sorted_records) == 2:
                    return short_string + str(sorted_records[1]['Aud'])
                elif len(sorted_records) == 3:
                    return short_string + str(sorted_records[1]['Aud']) + str(sorted_records[2]['Aud'])
                elif len(sorted_records) == 4:
                    return short_string + str(sorted_records[1]['Aud']) + str(sorted_records[2]['Aud']) + str(sorted_records[3]['Aud'])
                elif len(sorted_records) == 5:
                    return short_string + str(sorted_records[1]['Aud']) + str(sorted_records[2]['Aud']) + str(sorted_records[3]['Aud']) + str(sorted_records[4]['Aud'])
                elif len(sorted_records) == 6:
                    return short_string + str(sorted_records[1]['Aud']) + str(sorted_records[2]['Aud']) + str(sorted_records[3]['Aud']) + str(sorted_records[4]['Aud']) + str(sorted_records[5]['Aud'])
                else:
                    # Если строк слишком много, то что-то пошло не так
                    logger.error('Incorrect amount of rows for subgroups')
                    return None
    # Если это преподаватель
    elif teacher is not None and group is None:
        c = conn.cursor()
        c.execute('SELECT * FROM timetable WHERE Name = ? AND Date = ? AND Les = ? ORDER BY Subg', (teacher, date_request(day_of_week=day, for_db='YES', next=next), lesson))
        sorted_records = c.fetchall()
        c.close()
        # Обработка пустых строк
        if not sorted_records:
            return str(lesson) + '. -'
        # Если строка с темой не пустая
        if sorted_records[0]['Themas'] is not None:
            # Строка с темой
            if lesson_time == 'YES':
                full_string = str(lesson) + '. ' + str(time_lesson[lesson]) + ' (' + str(sorted_records[0]['Subj_type']) + ') ' + str(sorted_records[0]['Themas']) + ' ' + str(sorted_records[0]['Subject']) + str(sorted_records[0]['Aud']) + ' ' + str(sorted_records[0]['Group']) + ' гр.'
            else:
                full_string = str(lesson) + '. (' + str(sorted_records[0]['Subj_type']) + ') ' + str(sorted_records[0]['Themas']) + ' ' + str(sorted_records[0]['Subject']) + str(sorted_records[0]['Aud']) + ' ' + str(sorted_records[0]['Group']) + ' гр.'
            # Проверка на группы
            if len(sorted_records) == 1:
                return full_string
            elif len(sorted_records) >= 1 and str(sorted_records[0]['Group']) != str(sorted_records[1]['Group']):
                if len(sorted_records) == 2:
                    return full_string + ' ' + str(sorted_records[1]['Group']) + ' гр.'
                elif len(sorted_records) == 3:
                    return full_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр.'
                elif len(sorted_records) == 4:
                    return full_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр.'
                elif len(sorted_records) == 5:
                    return full_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр.'
                elif len(sorted_records) == 6:
                    return full_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр. ' + str(sorted_records[5]['Group']) + ' гр.'
                elif len(sorted_records) == 7:
                    return full_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр. ' + str(sorted_records[5]['Group']) + ' гр. ' + str(sorted_records[6]['Group']) + ' гр.'
                elif len(sorted_records) == 8:
                    return full_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр. ' + str(sorted_records[5]['Group']) + ' гр. ' + str(sorted_records[6]['Group']) + ' гр. ' + str(sorted_records[7]['Group']) + ' гр.'
                elif len(sorted_records) == 9:
                    return full_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр. ' + str(sorted_records[5]['Group']) + ' гр. ' + str(sorted_records[6]['Group']) + ' гр. ' + str(sorted_records[7]['Group']) + ' гр. ' + str(sorted_records[8]['Group']) + ' гр.'
                elif len(sorted_records) == 10:
                    return full_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр. ' + str(sorted_records[5]['Group']) + ' гр. ' + str(sorted_records[6]['Group']) + ' гр. ' + str(sorted_records[7]['Group']) + ' гр. ' + str(sorted_records[8]['Group']) + ' гр. ' + str(sorted_records[9]['Group']) + ' гр.'
                else:
                    # Если записей больше 10, то тут по-любому ошибка
                    logger.warning('Too many records!')
                    return None
            else:
                # Текущая и следующая записи идентичные
                logger.error('Identical records!')
                return None
        # Если темы нет
        elif sorted_records[0]['Themas'] is None:
            # Строка без темы
            if lesson_time == 'YES':
                short_string = str(lesson) + '. ' + str(time_lesson[lesson]) + ' (' + str(sorted_records[0]['Subj_type']) + ') ' + str(sorted_records[0]['Subject']) + ' ' + str(sorted_records[0]['Aud']) + ' ' + str(sorted_records[0]['Group']) + ' гр.'
            else:
                short_string = str(lesson) + '. (' + str(sorted_records[0]['Subj_type']) + ') ' + str(sorted_records[0]['Subject']) + ' ' + str(sorted_records[0]['Aud']) + ' ' + str(sorted_records[0]['Group']) + ' гр.'
            # Проверка на группы
            if len(sorted_records) == 1:
                return short_string
            elif len(sorted_records) >= 1 and str(sorted_records[0]['Group']) != str(sorted_records[1]['Group']):
                if len(sorted_records) == 2:
                    return short_string + ' ' + str(sorted_records[1]['Group']) + ' гр.'
                elif len(sorted_records) == 3:
                    return short_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр.'
                elif len(sorted_records) == 4:
                    return short_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр.'
                elif len(sorted_records) == 5:
                    return short_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр.'
                elif len(sorted_records) == 6:
                    return short_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр. ' + str(sorted_records[5]['Group']) + ' гр.'
                elif len(sorted_records) == 7:
                    return short_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр. ' + str(sorted_records[5]['Group']) + ' гр. ' + str(sorted_records[6]['Group']) + ' гр.'
                elif len(sorted_records) == 8:
                    return short_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр. ' + str(sorted_records[5]['Group']) + ' гр. ' + str(sorted_records[6]['Group']) + ' гр. ' + str(sorted_records[7]['Group']) + ' гр.'
                elif len(sorted_records) == 9:
                    return short_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр. ' + str(sorted_records[5]['Group']) + ' гр. ' + str(sorted_records[6]['Group']) + ' гр. ' + str(sorted_records[7]['Group']) + ' гр. ' + str(sorted_records[8]['Group']) + ' гр.'
                elif len(sorted_records) == 10:
                    return short_string + ' ' + str(sorted_records[1]['Group']) + ' гр. ' + str(sorted_records[2]['Group']) + ' гр. ' + str(sorted_records[3]['Group']) + ' гр. ' + str(sorted_records[4]['Group']) + ' гр. ' + str(sorted_records[5]['Group']) + ' гр. ' + str(sorted_records[6]['Group']) + ' гр. ' + str(sorted_records[7]['Group']) + ' гр. ' + str(sorted_records[8]['Group']) + ' гр. ' + str(sorted_records[9]['Group']) + ' гр.'
                else:
                    # Если записей больше 10, то тут по-любому ошибка
                    logger.error('Too many records!')
                    return None
            else:
                # Текущая и следующая записи идентичные
                logger.error('Identical records!')
                return None


# Собирает расписание на неделю из строк
def timetable_week(group: str = None, teacher: str = None, next: str = None, lesson_time: str = 'YES'):
    # Подключение к базе данных
    db_timetable = get_latest_file('timetable-dbs/timetable*.db')
    if db_timetable is None:
        logger.error('Cant processing timetable because no db-files in timetable-dbs directory')
        return 'В данный момент я не могу обработать ваш запрос, пожалуйста, повторите позже'
    conn = connection_to_sql(db_timetable)
    conn.row_factory = Row
    # Хранит строку с расписанием
    temp = ''
    # Дни
    for day in range(6):
        temp = temp + name_of_day_string(day, next=next)
        # Занятия
        for lesson in range(1, 6):
            subject = subject_string(conn=conn, day=day, lesson=lesson, group=group, teacher=teacher, next=next, lesson_time=lesson_time)
            if subject is not None:
                temp = temp + subject + '\n'
            else:
                conn.close()
                logger.error('An error occurred while processing timetable for "' + group + '" group or "' + teacher + '" teacher, next = "' + next + '", lesson_time = "' + lesson_time + '"')
                return 'В данный момент я не могу обработать ваш запрос, пожалуйста, повторите позже'
    if temp is not None:
        conn.close()
        return temp
    else:
        conn.close()
        logger.error('An error occurred while processing timetable for "' + group + '" group or "' + teacher + '" teacher, next = "' + next + '", lesson_time = "' + lesson_time + '"')
        return 'В данный момент я не могу обработать ваш запрос, пожалуйста, повторите позже'


# Отдает расписание на неделю по запросу
def timetable(group: str = None, teacher: str = None, next: str = None, lesson_time: str = 'YES'):
    if group and teacher is None:
        logger.log('TIMETABLE', 'Timetable request for "' + group + '" group, next = "' + str(next) + '", lesson_time = "' + lesson_time + '"')
        # Поиск уже готового расписания в директории
        if next is None:
            path = 'timetable-files/' + group + '.txt'
        else:
            path = 'timetable-files/' + group + '_next' + '.txt'
        timetable_group = None
        if glob(path):
            # Чтение файла расписания
            with open(path, 'r', encoding='utf-8') as f:
                """
                Проверка на актуальность расписания
                Берется первая строка с датой и сравнивается с понедельником
                """
                date_from_file = f.readline()
                if date_from_file == date_request(day_of_week=0, for_file='YES', next=next) + '\n':
                    timetable_group = f.read()
                    logger.log('TIMETABLE', 'Read timetable from file <' + path + '>')
        # Если прочитать из файла не удалось, то запрашиваем новое и сохраняем его
        if timetable_group is None:
            timetable_group = 'Группа ' + group + '\n' + timetable_week(group=group, teacher=teacher, next=next, lesson_time=lesson_time)
            # Запись файла расписания
            with open(path, 'w', encoding='utf-8') as f:
                f.write(date_request(day_of_week=0, for_file='YES', next=next) + '\n' + timetable_group)
                logger.log('TIMETABLE', 'Write timetable to file <' + path + '>')
        logger.log('TIMETABLE', 'Timetable response for "' + group + '" group, next = ' + str(next) + '", lesson_time = "' + lesson_time + '"')
        return timetable_group
    elif teacher and group is None:
        logger.log('TIMETABLE', 'Timetable request for "' + teacher + '" teacher, next = ' + str(next) + '", lesson_time = "' + lesson_time + '"')
        # Поиск уже готового расписания в директории
        if next is None:
            path = 'timetable-files/' + teacher + '.txt'
        else:
            path = 'timetable-files/' + teacher + '_next' + '.txt'
        timetable_teacher = None
        if glob(path):
            # Чтение файла расписания
            with open(path, 'r', encoding='utf-8') as f:
                """
                Проверка на актуальность расписания
                Берется первая строка с датой и сравнивается с понедельником
                """
                date_from_file = f.readline()
                if date_from_file == date_request(day_of_week=0, for_file='YES', next=next) + '\n':
                    timetable_teacher = f.read()
                    logger.log('TIMETABLE', 'Read timetable from file <' + path + '>')
        # Если прочитать из файла не удалось, то пишем новое
        if timetable_teacher is None:
            timetable_teacher = 'Для преподавателя ' + teacher + '\n' + timetable_week(group=group, teacher=teacher, next=next, lesson_time=lesson_time)
            # Запись файла расписания
            with open(path, 'w', encoding='utf-8') as f:
                f.write(date_request(day_of_week=0, for_file='YES', next=next) + '\n' + timetable_teacher)
                logger.log('TIMETABLE', 'Write timetable to file <' + path + '>')
        logger.log('TIMETABLE', 'Timetable response for "' + teacher + '" teacher, next = ' + str(next) + '", lesson_time = "' + lesson_time + '"')
        return timetable_teacher
    else:
        logger.error('Incorrect timetable request!')
        return 'В данный момент я не могу обработать ваш запрос, пожалуйста, повторите позже'


# with logger.catch():
    # print(timetable(group='306', next='YES', lesson_time='NO'))
    # print(timetable(group='306', next=None, lesson_time='NO'))
    # print(timetable(teacher='Горячева Н.Г.', next=None, lesson_time='NO'))

