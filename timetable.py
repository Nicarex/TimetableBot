from log import logger
from datetime import timedelta
import pendulum
from chardet import detect
from sql_db import connection_to_sqlite
from sqlite3 import Row
import pandas as pd
import os
from pathlib import Path
from glob import glob


# Дни недели для файла расписания
days_of_week = ['ПОНЕДЕЛЬНИК - ', '\nВТОРНИК - ', '\nСРЕДА - ', '\nЧЕТВЕРГ - ', '\nПЯТНИЦА - ', '\nСУББОТА - ']
time_lesson = ['', '09:00-10:30', '10:45-12:15', '12:30-14:00', '14:45-16:15', '16:25-17:55']


# Получает последний измененный файл
def get_latest_file(path):
    """
    example path = 'timetable-dbs/timetable*.db'
    """
    list_of_files = glob(path)  # * means all if need specific format then *.csv
    # Если есть хоть один файл
    if list_of_files:
        latest_file = max(list_of_files, key=os.path.getmtime)
        logger.debug('Latest file is ' + latest_file)
        return latest_file
    else:
        logger.warning('No files in this path ' + path)
        return None


# Проверка кодировки файла
def check_encoding(file, encoding):
    logger.info('Check encoding of file <' + file + '>...')
    rawfile = open(file, 'rb').read()
    result_encoding = detect(rawfile)
    if result_encoding['encoding'] == encoding:
        logger.success('Encoding of file <' + file + '> is ' + result_encoding['encoding'])
        return True
    else:
        logger.error('Encoding of file <' + file + '>doest match with request! Encoding is ' + str(result_encoding['encoding']))
        return False


# Конвертирует CSV-файл в SQL-файл
def convert_to_sql(csv_file):
    """
    example:
    for file in os.listdir('downloads'):
        convert_to_sql()
    """
    # Если файл существует и заканчивается на csv
    if Path(csv_file).is_file() and csv_file.endswith('.csv'):
        pass
    else:
        logger.error('Cant convert to sql because no file exist!')
        return None
    date = pendulum.now(tz='Europe/Moscow').format('YYYY-MM-DD_HH-mm-ss')
    logger.info('Convert <' + csv_file + '> to SQL...')
    timetable_csv = pd.read_csv(csv_file, encoding='utf-8', sep=';')
    if not os.path.isdir('timetable-dbs'):  # Если пути не существует - создать
        os.makedirs('timetable-dbs', exist_ok=True)
    conn = connection_to_sqlite(name='timetable-dbs/timetable_' + date + '.db')
    timetable_csv.to_sql(name='timetable', con=conn, if_exists='append', index=False)
    logger.success('File <' + csv_file + '> successfully converted to timetable_' + date + '.db')


# Возвращает дни недели в виде словаря
def get_week_dates(base_date, start_day, end_day=None):
    monday = base_date - timedelta(days=base_date.isoweekday() - 1)
    week_dates = [monday + timedelta(days=i) for i in range(7)]
    return week_dates[start_day - 1:end_day or start_day]


# Находит и форматирует дату для поиска в базе данных
# Можно ввести значения до 6 (воскресенье)
def date_request(day_of_week, for_file=None, for_db=None, next=None):
    """
    manual:
    dt = pendulum.parse('2021-05-31')
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
def name_of_day_string(day, next):
    return days_of_week[day] + date_request(day, for_file='YES', next=next) + '\n'


def subject_string(conn, day, lesson, group=None, teacher=None, next=next):
    # Если это группа
    if group is not None and teacher is None:
        c = conn.cursor()
        c.execute('SELECT * FROM timetable WHERE "Group" = ? AND Date = ? AND Les = ?', (group, date_request(day_of_week=day, for_db='YES', next=next), lesson))
        records = c.fetchall()
        c.close()
        logger.trace(str(len(records)) + ' records for ' + str(day+1) + ' day and ' + str(lesson) + ' lesson...')
        # Обработка пустых строк
        if not records:
            return str(lesson) + '. -'
        # Если строка с темой не пустая
        if records[0]['Themas'] is not None:
            full_string = str(lesson) + '. ' + time_lesson[lesson] + ' (' + records[0]['Subj_type'] + ') ' + records[0]['Themas'] + ' ' + records[0]['Subject'] + records[0]['Aud']
            # Если подгрупп нет
            if records[0]['Subg'] == 0:
                return full_string
            # Если подгруппы есть
            elif records[0]['Subg'] == 1:
                # Если подгруппа одна, что не должно быть, то возвращаем обычную строку, т.к. скорее всего ошибка в расписании
                if len(records) == 1:
                    logger.warning('Incorrect amount of rows for subgroups')
                    return full_string
                # Если следующий кабинет равен текущему, то возврати обычную строку
                elif len(records) >= 1 and records[0]['Aud'] == records[1]['Aud']:
                    return full_string
                elif len(records) == 2:
                    return full_string + records[1]['Aud']
                elif len(records) == 3:
                    return full_string + records[1]['Aud'] + records[2]['Aud']
                elif len(records) == 4:
                    return full_string + records[1]['Aud'] + records[2]['Aud'] + records[3]['Aud']
                elif len(records) == 5:
                    return full_string + records[1]['Aud'] + records[2]['Aud'] + records[3]['Aud'] + records[4]['Aud']
                elif len(records) == 6:
                    return full_string + records[1]['Aud'] + records[2]['Aud'] + records[3]['Aud'] + records[4]['Aud'] + records[5]['Aud']
                else:
                    # Если строк слишком много, то что-то пошло не так
                    logger.error('Incorrect amount of rows for subgroups')
                    return None
        # Если строка с темой пустая
        elif records[0]['Themas'] is None:
            short_string = str(lesson) + '. ' + time_lesson[lesson] + ' (' + records[0]['Subj_type'] + ') ' + records[0]['Subject'] + records[0]['Aud']
            # Если подгрупп нет
            if records[0]['Subg'] == 0:
                return short_string
            # Если подгруппы есть
            elif records[0]['Subg'] == 1:
                # Если подгруппа одна, что не должно быть, то возвращаем обычную строку, т.к. скорее всего ошибка в расписании
                if len(records) == 1:
                    logger.warning('Incorrect amount of rows for subgroups')
                    return short_string
                # Если следующий кабинет равен текущему, то возврати обычную строку
                elif len(records) >= 1 and records[0]['Aud'] == records[1]['Aud']:
                    return short_string
                elif len(records) == 2:
                    return short_string + records[1]['Aud']
                elif len(records) == 3:
                    return short_string + records[1]['Aud'] + records[2]['Aud']
                elif len(records) == 4:
                    return short_string + records[1]['Aud'] + records[2]['Aud'] + records[3]['Aud']
                elif len(records) == 5:
                    return short_string + records[1]['Aud'] + records[2]['Aud'] + records[3]['Aud'] + records[4]['Aud']
                elif len(records) == 6:
                    return short_string + records[1]['Aud'] + records[2]['Aud'] + records[3]['Aud'] + records[4]['Aud'] + \
                           records[5]['Aud']
                else:
                    # Если строк слишком много, то что-то пошло не так
                    logger.error('Incorrect amount of rows for subgroups')
                    return None
    # Если это преподаватель
    elif teacher is not None and group is None:
        c = conn.cursor()
        c.execute('SELECT * FROM timetable WHERE Name = ? AND Date = ? AND Les = ?', (teacher, date_request(day_of_week=day, for_db='YES', next=next), lesson))
        records = c.fetchall()
        c.close()
        logger.trace(str(len(records)) + ' records for ' + str(day+1) + ' day and ' + str(lesson) + ' lesson...')
        # Обработка пустых строк
        if not records:
            return str(lesson) + '. -'
        # Если строка с темой не пустая
        if records[0]['Themas'] is not None:
            # Строка с темой
            full_string = str(lesson) + '. ' + time_lesson[lesson] + ' (' + records[0]['Subj_type'] + ') ' + records[0]['Themas'] + ' ' + records[0]['Subject'] + records[0]['Aud'] + ' ' + records[0]['Group'] + ' гр.'
            # Проверка на группы
            if len(records) == 1:
                return full_string
            elif len(records) >= 1 and records[0]['Group'] != records[1][['Group']]:
                if len(records) == 2:
                    return full_string + records[1]['Group'] + ' гр.'
                elif len(records) == 3:
                    return full_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр.'
                elif len(records) == 4:
                    return full_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3]['Group'] + ' гр.'
                elif len(records) == 5:
                    return full_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3]['Group'] + ' гр. ' + records[4]['Group'] + ' гр.'
                elif len(records) == 6:
                    return full_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3]['Group'] + ' гр. ' + records[4]['Group'] + ' гр. ' + records[5]['Group'] + ' гр.'
                elif len(records) == 7:
                    return full_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3]['Group'] + ' гр. ' + records[4]['Group'] + ' гр. ' + records[5]['Group'] + ' гр. ' + records[6]['Group'] + ' гр.'
                elif len(records) == 8:
                    return full_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3]['Group'] + ' гр. ' + records[4]['Group'] + ' гр. ' + records[5]['Group'] + ' гр. ' + records[6]['Group'] + ' гр. ' + records[7]['Group'] + ' гр.'
                elif len(records) == 9:
                    return full_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3]['Group'] + ' гр. ' + records[4]['Group'] + ' гр. ' + records[5]['Group'] + ' гр. ' + records[6]['Group'] + ' гр. ' + records[7]['Group'] + ' гр. ' + records[8]['Group'] + ' гр.'
                elif len(records) == 10:
                    return full_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3]['Group'] + ' гр. ' + records[4]['Group'] + ' гр. ' + records[5]['Group'] + ' гр. ' + records[6]['Group'] + ' гр. ' + records[7]['Group'] + ' гр. ' + records[8]['Group'] + ' гр. ' + records[9]['Group'] + ' гр.'
                else:
                    # Если записей больше 10, то тут по-любому ошибка
                    logger.error('Too many records!')
                    return None
            else:
                # Текущая и следующая записи идентичные
                logger.error('Identical records!')
                return None
        # Если темы нет
        elif records[0]['Themas'] is None:
            # Строка без темы
            short_string = str(lesson) + '. ' + time_lesson[lesson] + ' (' + records[0]['Subj_type'] + ') ' + records[0][
                    'Subject'] + ' ' + records[0]['Aud'] + ' ' + records[0]['Group'] + ' гр.'
            # Проверка на группы
            if len(records) == 1:
                return short_string
            elif len(records) >= 1 and records[0]['Group'] != records[1][['Group']]:
                if len(records) == 2:
                    return short_string + records[1]['Group'] + ' гр.'
                elif len(records) == 3:
                    return short_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр.'
                elif len(records) == 4:
                    return short_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3][
                        'Group'] + ' гр.'
                elif len(records) == 5:
                    return short_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3][
                        'Group'] + ' гр. ' + records[4]['Group'] + ' гр.'
                elif len(records) == 6:
                    return short_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3][
                        'Group'] + ' гр. ' + records[4]['Group'] + ' гр. ' + records[5]['Group'] + ' гр.'
                elif len(records) == 7:
                    return short_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3][
                        'Group'] + ' гр. ' + records[4]['Group'] + ' гр. ' + records[5]['Group'] + ' гр. ' + records[6][
                               'Group'] + ' гр.'
                elif len(records) == 8:
                    return short_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3][
                        'Group'] + ' гр. ' + records[4]['Group'] + ' гр. ' + records[5]['Group'] + ' гр. ' + records[6][
                               'Group'] + ' гр. ' + records[7]['Group'] + ' гр.'
                elif len(records) == 9:
                    return short_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3][
                        'Group'] + ' гр. ' + records[4]['Group'] + ' гр. ' + records[5]['Group'] + ' гр. ' + records[6][
                               'Group'] + ' гр. ' + records[7]['Group'] + ' гр. ' + records[8]['Group'] + ' гр.'
                elif len(records) == 10:
                    return short_string + records[1]['Group'] + ' гр. ' + records[2]['Group'] + ' гр. ' + records[3][
                        'Group'] + ' гр. ' + records[4]['Group'] + ' гр. ' + records[5]['Group'] + ' гр. ' + records[6][
                               'Group'] + ' гр. ' + records[7]['Group'] + ' гр. ' + records[8]['Group'] + ' гр. ' + \
                           records[9]['Group'] + ' гр.'
                else:
                    # Если записей больше 10, то тут по-любому ошибка
                    logger.error('Too many records!')
                    return None
            else:
                # Текущая и следующая записи идентичные
                logger.error('Identical records!')
                return None


def timetable_week(conn, group=None, teacher=None, next=None):
    # Хранит строку с расписанием
    temp = ''
    # Дни
    for day in range(6):
        logger.debug('Processing timetable for ' + str(day+1) + ' day...')
        temp = temp + name_of_day_string(day, next=next)
        # Пары
        for lesson in range(1, 6):
            logger.trace('Processing timetable for ' + str(lesson) + ' lesson...')
            subject = subject_string(conn=conn, day=day, lesson=lesson, group=group, teacher=teacher, next=next) + '\n'
            if subject is not None:
                temp = temp + subject
            elif subject is None:
                conn.close()
                logger.error(
                    'An error occurred while processing timetable for ' + group + ' group or ' + teacher + ' teacher!')
                return 'Произошла ошибка при выполнении запроса...'
    if temp is not None:
        conn.close()
        return temp
    else:
        conn.close()
        logger.error('An error occurred while processing timetable for ' + group + ' group or ' + teacher + ' teacher!')
        return 'Произошла ошибка при выполнении запроса...'


def timetable(group, teacher=None, next=None):
    db_timetable = get_latest_file('timetable-dbs/timetable*.db')
    if db_timetable is None:
        logger.error('Cant processing timetable because no db-files in timetable-dbs directory')
        return 'В данный момент я не могу обработать ваш запрос, пожалуйста, повторите позже'
    logger.debug('Using <' + db_timetable + '> file for timetable')
    if group is not None and teacher is None:
        logger.info('Timetable request for "' + group + '" group, next = ' + next)
        conn = connection_to_sqlite(db_timetable)
        conn.row_factory = Row
        timetable_group = 'Группа ' + group + '\n' + timetable_week(conn=conn, group=group, teacher=teacher, next=next)
        logger.success('Timetable response for "' + group + '" group, next = ' + next)
        return timetable_group
    elif group is None and teacher is not None:
        logger.info('Timetable request for "' + teacher + '" teacher, next = ' + next)
        conn = connection_to_sqlite(db_timetable)
        conn.row_factory = Row
        timetable_teacher = 'Для преподавателя ' + teacher + '\n' + timetable_week(conn=conn, teacher=teacher, next=next)
        logger.success('Timetable response for "' + teacher + '" teacher, next = ' + next)
        return timetable_teacher
    else:
        logger.error('Incorrect timetable request!')
        return 'В данный момент я не могу обработать ваш запрос, пожалуйста, повторите позже'


with logger.catch():

    # for file in os.listdir('downloads'):
    #     convert_to_sql(csv_file='downloads/'+file)
    print(timetable(group='693', teacher=None, next='YES'))