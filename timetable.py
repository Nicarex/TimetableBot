from logger import logger
from datetime import timedelta
import pendulum
from other import get_latest_file, connection_to_sql
from glob import glob, iglob
from sqlite3 import Row
import os


# Дни недели для файла расписания
list_with_days_of_week = ['ПОНЕДЕЛЬНИК - ', '\nВТОРНИК - ', '\nСРЕДА - ', '\nЧЕТВЕРГ - ', '\nПЯТНИЦА - ', '\nСУББОТА - ', '\nВОСКРЕСЕНЬЕ - ']
list_with_lesson_time = ['', '09:00-10:30', '10:45-12:15', '12:30-14:00', '14:40-16:10', '16:25-17:55']
dict_with_names_of_month = {'января': 'январь', 'февраля': 'февраль', 'марта': 'март', 'апреля': 'апрель', 'мая': 'май', 'июня': 'июнь', 'июля': 'июль', 'августа': 'август', 'сентября': 'сентябрь', 'октября': 'октябрь', 'ноября': 'ноябрь', 'декабря': 'декабрь'}


# Учебная нагрузка
def workload(teacher: str = None, next: str = None):
    db_timetable = get_latest_file('timetable-dbs/timetable*.db')
    if db_timetable is None:
        logger.error('Cant show timetable because no db-files in timetable-dbs directory')
        return 'Извините, но в данный момент я не могу обработать ваш запрос, пожалуйста, попробуйте позже'
    # Текущее время
    pendulum.set_locale('ru')
    dt = pendulum.now(tz='Europe/Moscow')
    # Текущий
    if next is None:
        first_day_of_month = dt.start_of('month')
        last_day_of_month = dt.end_of('month')
    # Следующий
    else:
        dt_next_month = dt.add(months=1)
        first_day_of_month = dt_next_month.start_of('month')
        last_day_of_month = dt_next_month.end_of('month')
    all_dates_of_month = [first_day_of_month.format('D-MM-YYYY')]
    next_day = first_day_of_month
    while True:
        next_day = next_day.add(days=1)
        if next_day.format('MMMM') == first_day_of_month.format('MMMM'):
            all_dates_of_month += [next_day.format('D-MM-YYYY')]
        else:
            break
    conn = connection_to_sql(db_timetable)
    conn.row_factory = Row
    c = conn.cursor()
    all_lessons_of_month = {}
    counter_of_all_lessons_in_month = 0
    for day in all_dates_of_month:
        timetable_on_day = c.execute('SELECT * FROM timetable WHERE "Name" = ? AND "Date" = ?', (str(teacher), day)).fetchall()
        for row in timetable_on_day:
            counter_of_all_lessons_in_month += 1
            if all_lessons_of_month.get(row['Subj_type']) is None:
                all_lessons_of_month[row['Subj_type']] = 1
            else:
                all_lessons_of_month[row['Subj_type']] += 1
    answer = f"Преподаватель {str(teacher)}\nИтого за {str(dict_with_names_of_month.get(first_day_of_month.format('MMMM')))} - {str(counter_of_all_lessons_in_month*2)} ч. занятий"
    if counter_of_all_lessons_in_month != 0:
        answer += f'\nТипы занятий:'
        for type_of_lesson in all_lessons_of_month:
            answer += f'\n{type_of_lesson} - {all_lessons_of_month[type_of_lesson]}'
    return answer


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
    return list_with_days_of_week[day] + date_request(day, for_file='YES', next=next) + '\n'


def timetable(group_id: str = None, teacher: str = None, month: str = None, next: str = None, lesson_time: str = None, use_previous_timetable_db: str = None):
    """
    Возвращает расписание для группы или преподавателя на неделю, или месяц
    group_id - номер группы (307)
    teacher - ФИО преподавателя (Иванов И.И.)
    month - требуется расписание на месяц (YES)
    next - следующий месяц / следующая неделя (YES)
    no_show_lesson_time - не отображать время пар в расписании (YES)
    use_previous_timetable_db - использование предыдущей бд расписания (YES)

    При запросе расписания:
    Выбирается файл бд, поиск уже готового расписания -> проверяется на актуальность \ создаем новое, записываем в файл, возвращаем -> возвращаем \ создаем новое, записываем в файл, возвращаем
    """
    logger.log('TIMETABLE', f'Request to show timetable for teacher = "{str(teacher)}" or group = "{str(group_id)}", month = "{str(month)}", next = "{str(next)}", lesson_time = "{str(lesson_time)}"')

    # Выбирается бд
    if use_previous_timetable_db is None:
        # Последняя бд
        db_timetable = get_latest_file('timetable-dbs/timetable*.db')
    else:
        # Предыдущая бд
        db_timetable = sorted(iglob('timetable-dbs/*.db'), key=os.path.getmtime)[-2]
    if db_timetable is None:
        logger.error('Cant show timetable because no db-files in timetable-dbs directory')
        return 'Извините, но в данный момент я не могу обработать ваш запрос, пожалуйста, попробуйте позже'

    # Рассчитываем даты занятий
    # Текущее время
    dt = pendulum.now(tz='Europe/Moscow')
    # Нужна неделя
    if month is None:
        first_day_of_current_week = dt.start_of('week')
        first_day_of_next_week = dt.next(pendulum.MONDAY)
    # Нужен месяц
    else:
        # Текущий
        if next is None:
            first_day_of_month = dt.start_of('month')
        # Следующий
        else:
            dt_next_month = dt.add(months=1)
            first_day_of_month = dt_next_month.start_of('month')
        # Если первый день месяца - воскресенье, то считаем, что первый день месяца - понедельник на следующей неделе
        if first_day_of_month == pendulum.SUNDAY:
            first_day_of_month = first_day_of_month.next(pendulum.MONDAY)
        start_of_week_on_first_day_of_month = first_day_of_month.start_of('week')
        # Даты всех понедельников месяца
        dates_of_month = [start_of_week_on_first_day_of_month]
        last_date = start_of_week_on_first_day_of_month
        while True:
            start_of_next_week_on_first_day_of_month = last_date.next(pendulum.MONDAY)
            if start_of_next_week_on_first_day_of_month.format('MMMM') == first_day_of_month.format('MMMM'):
                dates_of_month += [start_of_next_week_on_first_day_of_month]
                last_date = start_of_next_week_on_first_day_of_month
            else:
                break

    # Преподаватель
    if teacher is not None and group_id is None:
        # Поиск уже готового расписания в директории
        if use_previous_timetable_db is None:
            # Не месяц
            if month is None:
                # Текущая неделя
                if next is None:
                    # С отображением времени
                    if lesson_time is None:
                        path = f'timetable-files/{str(teacher)}.txt'
                    # Без отображения времени
                    else:
                        path = f'timetable-files/{str(teacher)}_without_time.txt'
                # Следующая неделя
                else:
                    if lesson_time is None:
                        path = f'timetable-files/{str(teacher)}_next.txt'
                    else:
                        path = f'timetable-files/{str(teacher)}_next_without_time.txt'
            # Расписание на месяц
            else:
                # Текущий месяц
                if next is None:
                    # С отображением времени
                    if lesson_time is None:
                        path = f'timetable-files/{str(teacher)}_month.txt'
                    # Без отображения времени
                    else:
                        path = f'timetable-files/{str(teacher)}_month_without_time.txt'
                # Следующий месяц
                else:
                    if lesson_time is None:
                        path = f'timetable-files/{str(teacher)}_month_next.txt'
                    else:
                        path = f'timetable-files/{str(teacher)}_month_next_without_time.txt'
            # Если файл с таким путем существует
            if glob(path):
                # Чтение файла расписания
                with open(path, 'r', encoding='utf-8') as f:
                    """
                    Проверка на актуальность расписания
                    Берется первая строка с датой и сравнивается с понедельником
                    """
                    date_from_file = f.readline()
                    if date_from_file == date_request(day_of_week=0, for_file='YES', next=next) + '\n':
                        timetable_string = f.read()
                        logger.log('TIMETABLE',
                                   f'Read timetable from file <{path}> for teacher = "{str(teacher)}", next = "{str(next)}", lesson_time = "{str(lesson_time)}"')
                        return timetable_string
        # Если готового расписания нет, пишем новое
        timetable_string = f'Преподаватель {str(teacher)}'
        conn = connection_to_sql(db_timetable)
        conn.row_factory = Row
        c = conn.cursor()
        # Расписание на неделю
        if month is None:
            # Проверка на наличие занятий на неделю
            timetable_on_week = []
            for day in range(7):
                timetable_on_day = c.execute('SELECT * FROM timetable WHERE "Name" = ? AND "Date" = ?', (str(teacher), date_request(day_of_week=day, for_db='YES', next=next))).fetchone()
                if timetable_on_day:
                    timetable_on_week += timetable_on_day
            if not timetable_on_week:
                if next is None:
                    c.close()
                    conn.close()
                    return f'{timetable_string}\nНе найдено занятий на текущую неделю'
                else:
                    c.close()
                    conn.close()
                    return f'{timetable_string}\nНе найдено занятий на следующую неделю'
            for day in range(7):
                # Проверка на воскресенье
                if day == 6:
                    timetable_rows = c.execute(
                        'SELECT * FROM timetable WHERE "Name" = ? AND "Date" = ?',
                        (str(teacher), date_request(day_of_week=day, for_db='YES', next=next))).fetchone()
                    if not timetable_rows:
                        continue
                # Название дня недели и дата
                timetable_string += '\n' + list_with_days_of_week[day] + date_request(day_of_week=day, for_file='YES', next=next)
                # Формирование строки для каждого занятия
                for lesson in range(1,6):
                    timetable_rows = c.execute('SELECT * FROM timetable WHERE "Name" = ? AND "Date" = ? AND "Les" = ? ORDER BY "Group", "Subg"', (teacher, date_request(day_of_week=day, for_db='YES', next=next), lesson)).fetchall()
                    if not timetable_rows:
                        timetable_string += f"\n{str(lesson)}. -"
                    else:
                        row = timetable_rows[0]
                        # Строка в зависимости от темы
                        if row['Themas'] is not None:
                            if lesson_time is None:
                                timetable_string += f'\n{str(lesson)}. {list_with_lesson_time[lesson]} ({str(row["Subj_type"])}) {str(row["Themas"])} {str(row["Subject"])}{str(row["Aud"])} {str(row["Group"])} гр.'
                            else:
                                timetable_string += f'\n{str(lesson)}. ({str(row["Subj_type"])}) {str(row["Themas"])} {str(row["Subject"])}{str(row["Aud"])} {str(row["Group"])} гр.'
                        elif row['Themas'] is None:
                            if lesson_time is None:
                                timetable_string += f'\n{str(lesson)}. {list_with_lesson_time[lesson]} ({str(row["Subj_type"])}) {str(row["Subject"])}{str(row["Aud"])} {str(row["Group"])} гр.'
                            else:
                                timetable_string += f'\n{str(lesson)}. ({str(row["Subj_type"])}) {str(row["Subject"])}{str(row["Aud"])} {str(row["Group"])} гр.'
                        # Обработка нескольких групп на одном занятии
                        if len(timetable_rows) > 1:
                            for i in range(1, len(timetable_rows)):
                                timetable_string += f" {str(timetable_rows[i]['Group'])} гр."
            c.close()
            conn.close()
        # Расписание на месяц
        else:
            # Проверка на наличие занятий на неделю
            timetable_on_month = []
            for week in dates_of_month:
                for day in range(7):
                    timetable_on_day = c.execute('SELECT * FROM timetable WHERE "Name" = ? AND "Date" = ?', (str(teacher), date_request(day_of_week=day, for_db='YES', next=next))).fetchone()
                    if timetable_on_day:
                        timetable_on_month += [timetable_on_day]
            if not timetable_on_month:
                c.close()
                conn.close()
                return f'{timetable_string}\nНе найдено занятий на запрошенный период'
            for day in range(7):
                # Проверка на воскресенье
                if day == 6:
                    timetable_rows = c.execute('SELECT * FROM timetable WHERE "Name" = ? AND "Date" = ?',(str(teacher), date_request(day_of_week=day, for_db='YES', next=next))).fetchone()
                    if not timetable_rows:
                        continue
                # Название дня недели и дата
                timetable_string += '\n' + list_with_days_of_week[day] + date_request(day_of_week=day, for_file='YES',
                                                                                      next=next)
                # Формирование строки для каждого занятия
                for lesson in range(1, 6):
                    timetable_rows = c.execute(
                        'SELECT * FROM timetable WHERE "Name" = ? AND "Date" = ? AND "Les" = ? ORDER BY "Group", "Subg"',
                        (teacher, date_request(day_of_week=day, for_db='YES', next=next), lesson)).fetchall()
                    if not timetable_rows:
                        timetable_string += f"\n{str(lesson)}. -"
                    else:
                        row = timetable_rows[0]
                        # Строка в зависимости от темы
                        if row['Themas'] is not None:
                            if lesson_time is None:
                                timetable_string += f'\n{str(lesson)}. {list_with_lesson_time[lesson]} ({str(row["Subj_type"])}) {str(row["Themas"])} {str(row["Subject"])}{str(row["Aud"])} {str(row["Group"])} гр.'
                            else:
                                timetable_string += f'\n{str(lesson)}. ({str(row["Subj_type"])}) {str(row["Themas"])} {str(row["Subject"])}{str(row["Aud"])} {str(row["Group"])} гр.'
                        elif row['Themas'] is None:
                            if lesson_time is None:
                                timetable_string += f'\n{str(lesson)}. {list_with_lesson_time[lesson]} ({str(row["Subj_type"])}) {str(row["Subject"])}{str(row["Aud"])} {str(row["Group"])} гр.'
                            else:
                                timetable_string += f'\n{str(lesson)}. ({str(row["Subj_type"])}) {str(row["Subject"])}{str(row["Aud"])} {str(row["Group"])} гр.'
                        # Обработка нескольких групп на одном занятии
                        if len(timetable_rows) > 1:
                            for i in range(1, len(timetable_rows)):
                                timetable_string += f" {str(timetable_rows[i]['Group'])} гр."
            c.close()
            conn.close()
        # Запись файла расписания
        if use_previous_timetable_db is None:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(date_request(day_of_week=0, for_file='YES', next=next) + '\n' + timetable_string)
                logger.log('TIMETABLE', f'Write timetable to file <{path}> for teacher = "{str(teacher)}", next = "{str(next)}", lesson_time = "{str(lesson_time)}"')
        logger.log('TIMETABLE', f'Timetable response for teacher = "{str(teacher)}", next = "{str(next)}", lesson_time = "{str(lesson_time)}"')
        return timetable_string
    # Группа
    elif group_id is not None and teacher is None:
        # Поиск уже готового расписания в директории
        if use_previous_timetable_db is None:
            if next is None:
                if lesson_time is None:
                    path = f'timetable-files/{str(group_id)}.txt'
                else:
                    path = f'timetable-files/{str(group_id)}_without_time.txt'
            else:
                if lesson_time is None:
                    path = f'timetable-files/{str(group_id)}_next.txt'
                else:
                    path = f'timetable-files/{str(group_id)}_next_without_time.txt'
            if glob(path):
                # Чтение файла расписания
                with open(path, 'r', encoding='utf-8') as f:
                    """
                    Проверка на актуальность расписания
                    Берется первая строка с датой и сравнивается с понедельником
                    """
                    date_from_file = f.readline()
                    if date_from_file == date_request(day_of_week=0, for_file='YES', next=next) + '\n':
                        timetable_string = f.read()
                        logger.log('TIMETABLE',
                                   f'Read timetable from file <{path}> for group = "{str(group_id)}", next = "{str(next)}", lesson_time = "{str(lesson_time)}"')
                        return timetable_string
        # Если готового расписания нет, пишем новое
        timetable_string = f'Группа {str(group_id)}'
        conn = connection_to_sql(db_timetable)
        conn.row_factory = Row
        c = conn.cursor()
        # Проверка на наличие занятий на неделю
        timetable_on_week = []
        for day in range(7):
            timetable_on_day = c.execute('SELECT * FROM timetable WHERE "Group" = ? AND "Date" = ?', (str(group_id), date_request(day_of_week=day, for_db='YES', next=next))).fetchone()
            if timetable_on_day:
                timetable_on_week += timetable_on_day
        if not timetable_on_week:
            if next is None:
                c.close()
                conn.close()
                return f'{timetable_string}\nНе найдено занятий на текущую неделю'
            else:
                c.close()
                conn.close()
                return f'{timetable_string}\nНе найдено занятий на следующую неделю'
        for day in range(7):
            # Проверка на воскресенье
            if day == 6:
                timetable_rows = c.execute(
                    'SELECT * FROM timetable WHERE "Group" = ? AND "Date" = ?',
                    (str(group_id), date_request(day_of_week=day, for_db='YES', next=next))).fetchone()
                if not timetable_rows:
                    continue
            # Название дня недели и дата
            timetable_string += '\n' + list_with_days_of_week[day] + date_request(day_of_week=day, for_file='YES', next=next)
            # Формирование строки для каждого занятия
            for lesson in range(1, 6):
                timetable_rows = c.execute(
                    'SELECT * FROM timetable WHERE "Group" = ? AND "Date" = ? AND "Les" = ? ORDER BY "Subg"',
                    (str(group_id), date_request(day_of_week=day, for_db='YES', next=next), lesson)).fetchall()
                if not timetable_rows:
                    timetable_string += f"\n{str(lesson)}. -"
                else:
                    row = timetable_rows[0]
                    # Строка в зависимости от темы
                    if row['Themas'] is not None:
                        if lesson_time is None:
                            timetable_string += f'\n{str(lesson)}. {list_with_lesson_time[lesson]} ({str(row["Subj_type"])}) {str(row["Themas"])} {str(row["Subject"])}{str(row["Aud"])}'
                        else:
                            timetable_string += f'\n{str(lesson)}. ({str(row["Subj_type"])}) {str(row["Themas"])} {str(row["Subject"])}{str(row["Aud"])}'
                    elif row['Themas'] is None:
                        if lesson_time is None:
                            timetable_string += f'\n{str(lesson)}. {list_with_lesson_time[lesson]} ({str(row["Subj_type"])}) {str(row["Subject"])}{str(row["Aud"])}'
                        else:
                            timetable_string += f'\n{str(lesson)}. ({str(row["Subj_type"])}) {str(row["Subject"])}{str(row["Aud"])}'
                    # Обработка нескольких подгрупп на одном занятии
                    if len(timetable_rows) > 1:
                        for i in range(1, len(timetable_rows)):
                            timetable_string += f"{str(timetable_rows[i]['Aud'])}"
        c.close()
        conn.close()
        # Запись файла расписания
        if use_previous_timetable_db is None:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(date_request(day_of_week=0, for_file='YES', next=next) + '\n' + timetable_string)
                logger.log('TIMETABLE', f'Write timetable to file <{path}> for group = "{str(group_id)}", next = "{str(next)}", lesson_time = "{str(lesson_time)}"')
        logger.log('TIMETABLE', f'Timetable response for group = "{str(group_id)}", next = "{str(next)}", lesson_time = "{str(lesson_time)}"')
        return timetable_string
    else:
        logger.error('Incorrect request to show timetable. Teacher and group_id are None')
        return False


# with logger.catch():
    # timetable(group_id=None, teacher=None, month='YES', next=None, lesson_time=None)
    # print(work_load(teacher='Уфимцева А.М.', next=None))
