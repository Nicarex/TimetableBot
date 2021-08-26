from datetime import timedelta
import pendulum
from dbf import connect_to_dbf

# Дни недели для файла расписания
days_of_week = ['ПОНЕДЕЛЬНИК - ', '\nВТОРНИК - ', '\nСРЕДА - ', '\nЧЕТВЕРГ - ', '\nПЯТНИЦА - ', '\nСУББОТА - ']
time_lesson = ['', '09:00-10:30', '10:45-12:15', '12:30-14:00', '14:45-16:15', '16:25-17:55']


# Возвращает дни недели в виде словаря
def get_week_dates(base_date, start_day, end_day=None):
    monday = base_date - timedelta(days=base_date.isoweekday() - 1)
    week_dates = [monday + timedelta(days=i) for i in range(7)]
    return week_dates[start_day - 1:end_day or start_day]


# Находит и форматирует дату для поиска в dfb
# Можно ввести значения до 6 (воскресенье)
def date_for_dbf(day_of_week, next=None):
    """
    DEBUG!!!
    """
    # dt = pendulum.parse('2021-05-31')

    # Текущее время в текущем часовом поясе
    dt = pendulum.now(tz='Europe/Moscow')
    monday = dt.start_of('week')
    monday_next = dt.next(pendulum.MONDAY)
    # Если на текущую неделю
    if next is None:
        return str(get_week_dates(monday, 1, 7)[day_of_week].format('D-MM-YYYY'))
    # Если на следующую неделю
    else:
        return str(get_week_dates(monday_next, 1, 7)[day_of_week].format('D-MM-YYYY'))


# Получаем дату для файла с расписанием
def date_for_file(day_of_week, next=None):
    """
    DEBUG!!!
    """
    # dt = pendulum.parse('2021-05-31')

    # Текущее время в текущем часовом поясе
    dt = pendulum.now(tz='Europe/Moscow')
    monday = dt.start_of('week')
    monday_next = dt.next(pendulum.MONDAY)
    # Если на текущую неделю
    if next is None:
        return str(get_week_dates(monday, 1, 7)[day_of_week].format('DD.MM.YYYY'))
    # Если на следующую неделю
    else:
        return str(get_week_dates(monday_next, 1, 7)[day_of_week].format('DD.MM.YYYY'))


def sort_for_teacher(item):
    return int(item['WEEK']), int(item['DAY']), int(item['LES']), str(item['GROUP'])


# Название дня выводится в строку
def name_of_day_string(day, next):
    return days_of_week[day] + date_for_file(day, next=next) + '\n'


# Предмет выводится в строку
def subject_string(sorted_dbf, day, lesson=None, teacher=None, next=None):
    # Выводимая строка
    a = ''
    # Хранит дату
    b = ''
    # Получаем запись в листе через длину листа
    for number in range(len(sorted_dbf)):
        # Если дата в записи равна нужной дате
        if sorted_dbf[number]['DATE'] == date_for_dbf(day, next=next):
            # b принимает текущую дату, если дата в записи совпадает с текущей датой
            b = sorted_dbf[number]['DATE']
            # Если номер пары в записи равен номеру необходимой пары
            if sorted_dbf[number]['LES'] == str(lesson) and teacher is None:
                # Обработка строк с подгруппами
                if sorted_dbf[number]['SUBG'] == str(1):
                    a = a + str(lesson) + '. ' + str(time_lesson[lesson]) + ' (' + sorted_dbf[number]['SUBJ_TYPE'] + ') ' + sorted_dbf[number]['THEME'] + ' ' + sorted_dbf[number]['SUBJECT'] + ' ' + sorted_dbf[number]['AUD']
                    if sorted_dbf[number + 1]['SUBG'] != str(2):
                        return a + '\n'
                if sorted_dbf[number + 1]['SUBG'] == str(2):
                    a = a + ' ' + sorted_dbf[number + 1]['AUD']
                    if sorted_dbf[number + 2]['SUBG'] != str(3):
                        return a + '\n'
                if sorted_dbf[number + 2]['SUBG'] == str(3):
                    a = a + ' ' + sorted_dbf[number + 2]['AUD']
                    if sorted_dbf[number + 3]['SUBG'] != str(4):
                        return a + '\n'
                if sorted_dbf[number + 3]['SUBG'] == str(4):
                    a = a + ' ' + sorted_dbf[number + 3]['AUD']
                    if sorted_dbf[number + 4]['SUBG'] != str(5):
                        return a + '\n'
                # Обычные строки
                # Возвращает строку с парой
                if sorted_dbf[number]['SUBG'] == '':
                    return str(lesson) + '. ' + str(time_lesson[lesson]) + ' (' + sorted_dbf[number]['SUBJ_TYPE'] + ') ' + sorted_dbf[number]['THEME'] + ' ' + sorted_dbf[number]['SUBJECT'] + ' ' + sorted_dbf[number]['AUD'] + '\n'
            # Для учителей
            elif sorted_dbf[number]['LES'] == str(lesson) and teacher is not None:
                # Если в одной паре несколько групп
                if sorted_dbf[number + 1]['LES'] == str(lesson) and sorted_dbf[number+1]['DATE'] == date_for_dbf(day, next=next):
                    for j in range(1, 10):
                        if sorted_dbf[number + j]['LES'] == str(lesson) and sorted_dbf[number + j]['DATE'] == date_for_dbf(day, next=next):
                            a = a + ' ' + sorted_dbf[number + j]['GROUP']
                return str(lesson) + '. ' + str(time_lesson[lesson]) + ' (' + sorted_dbf[number]['SUBJ_TYPE'] + ') ' + sorted_dbf[number]['THEME'] + ' ' + sorted_dbf[number]['SUBJECT'] + ' ' + sorted_dbf[number]['AUD'] + ' ' + sorted_dbf[number]['GROUP'] + a + ' гр.' + '\n'
        # Если дата в записи не совпадает с датой в b и b не пустая
        elif sorted_dbf[number]['DATE'] != b and b != '':
            return str(lesson) + '. -\n'
        # Для полностью пустых дней
        # Если number хранит последнюю цифру в листе, то значит такой даты в базе данных нет, и в этот день пар нет
        elif number == (len(sorted_dbf) - 1):
            return str(lesson) + '. -\n'


# Расписание на неделю
def timetable_week(sorted_dbf, teacher, next):
    # Хранит строку с расписанием
    temp = ''
    # Дни
    for day in range(6):
        temp = temp + name_of_day_string(day, next=next)
        # Пары
        for lesson in range(1, 6):
            temp = temp + str(subject_string(sorted_dbf=sorted_dbf, day=day, lesson=lesson, teacher=teacher, next=next))
    return temp


# Непосредственно собирается расписание
def timetable(group, teacher=None, next=None):
    sorted_dbf = []
    # Если нужна группа
    if group != '':
        # Создаем лист, в котором будут храниться записи отсортированные через группу
        # Сделано для производительности
        for record in connect_to_dbf():
            if record['GROUP'] == group:
                sorted_dbf.append(record)
        return 'Группа ' + group + '\n' + timetable_week(sorted_dbf=sorted_dbf, teacher=teacher, next=next)
    elif teacher is not None and group == '':
        for record in connect_to_dbf():
            if record['NAME'] == teacher:
                sorted_dbf.append(record)
        sorted_dbf.sort(key=sort_for_teacher)
        return 'Для преподавателя ' + teacher + '\n' + timetable_week(sorted_dbf=sorted_dbf, teacher=teacher, next=next)


"""
DEBUG!!!
"""
# print(timetable('307', theme='YES', next=None))
# print(timetable('', teacher='Макатов З.В.'))
# print(timetable('', teacher='Будыкина Т.А.'))
