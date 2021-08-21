from openpyxl import load_workbook  # таблица
from datetime import datetime, timedelta  # текущее время
import pytz  # часовой пояс
import download_from_site


# открытие файлов
def open_excel_file():
    excel = load_workbook(filename='IF-1-kurs.xlsx', data_only=True)
    sheet = excel['Table 1']
    return sheet


# списки
date_list = ['ПНД,', 'ВТР,', 'СРД,', 'ЧТВ,', 'ПТН,', 'СБТ,', 'ПНД', 'ВТР', 'СРД', 'ЧТВ', 'ПТН', 'СБТ']
date_replace_old = ['01/', '02/', '03/', '04/', '05/', '06/', '07/', '08/', '09/']
date_replace_new = ['1/', '2/', '3/', '4/', '5/', '6/', '7/', '8/', '9/']
alphabet = ['C', 'F', 'I', 'L', 'O', 'R']
surnames = ['Артемьева Ю.В.', 'Безвесильная А.А.', 'Ершова Н.Н.', 'Затеева Г.А.', 'Богданова И.С.', 'Борцова А.Н.',
            'Герасимов П.С.', 'Грищенко Н.В.', 'Залозная Н.Г.', 'Шарифуллина Л.Р.', 'Иванова С.М.', 'Никитенко И.Д.',
            'Кнауб Л.Е.', 'Нурмагомедов Т.Н.', 'Крюкова Л.Ю.', 'Веденяпина М.Д.', 'Гордова А.Ф.', 'Лаврова И.А.',
            'Рубищев А.Н.', 'Нуньес Е.А.', 'Туренова Е.Л.', 'Сулейманов А.М.', 'Михайлова Л.Л.', 'Аракелян М.А.',
            'Харламова Е.А.', 'Черных И.И.', 'Багдасарян А.О.']
lesson_type_old = ['ЗСО ', 'СРПП', 'ЛР', 'ПЗ', 'См', 'л', 'Пр', 'Контр.р', 'Контр.р ', 'Зачет ', 'экз. ',
                   'Групповое упражнение']
lesson_type_new = ['ЗСО', 'СРПП', 'ЛР', 'ПЗ', 'СМ', 'Л', 'ПР', 'Контр.р', 'Контр.р', 'Зачет', 'ЭКЗ', 'ГУ']
rubbish = []  # генерирует мусор
for n in range(1, 21):
    for m in range(1, 21):
        rubbish.append(str(n) + '.' + str(m))
rubbish.reverse()


# расписание на день
def timetable(i, weekday, f, sheet):
    file = open('timetable.txt', 'a')
    # определение дня недели
    if weekday == 0:
        file = open('timetable.txt', 'w')
        file.write('ПОНЕДЕЛЬНИК - ' + f + '\n')
    elif weekday == 1:
        file.write('ВТОРНИК - ' + f + '\n')
    elif weekday == 2:
        file.write('СРЕДА - ' + f + '\n')
    elif weekday == 3:
        file.write('ЧЕТВЕРГ - ' + f + '\n')
    elif weekday == 4:
        file.write('ПЯТНИЦА - ' + f + '\n')
    elif weekday == 5:
        file.write('СУББОТА - ' + f + '\n')
    #    temp = ''  # временный файл
    for j in range(1, 6):  # расписание
        # обычная строка
        if not sheet['R' + str(i)].value == '' and not str(sheet['R' + str(i)].value) == 'None':
            temp = ''  # временный файл
            file.write(str(j) + '. ')  # номер занятия
            time = sheet['B' + str(i)].value  # время занятия
            time = time.replace(' ', '')
            temp += time
            cell = sheet['R' + str(i)].value  # предмет
            for l in range(0, 12):  # тип занятия
                if not cell.find(lesson_type_old[l]) == -1:
                    cell = cell.replace(lesson_type_old[l], '', 1)
                    temp += ' (' + lesson_type_new[l] + ')'
                    break
            for p in rubbish:  # убирает мусор
                if not cell.find(p) == -1:
                    cell = cell.replace(p, '')
            temp += cell
            cell = sheet['T' + str(i)].value  # кабинет
            while not cell.find('  ') == -1: cell = cell.replace('  ',
                                                                 ' ')  # убираются лишние пробелы из строки с кабинетами
            if not cell.find(' ') == -1: cell = cell.replace(' ', '; ')
            if not cell.find('\n') == -1: cell = cell.replace('\n', '; ')
            temp += ' ' + cell
            while not temp.find('  ') == -1: temp = temp.replace('  ', '')  # убираются лишние пробелы
            file.write(temp + '\n')
            i += 1  # переход к следующей строке
        # совмещенная строка
        elif str(sheet['R' + str(i)].value) == 'None':
            temp = ''
            file.write(str(j) + '. ')  # номер занятия
            cell = 'None'  # предмет + кабинет
            k = 5
            while cell == 'None':
                if k == -1:
                    break
                cell = str(sheet[alphabet[k] + str(i)].value)
                k -= 1
            if not cell == 'None':
                time = sheet['B' + str(i)].value  # время занятия
                time = time.replace(' ', '')
                temp += time
            for l in surnames:  # убирается фамилия
                if not cell.find(l) == -1:
                    cell = cell.replace(l, '')
            for l in range(0, 12):  # тип занятия
                if not cell.find(lesson_type_old[l]) == -1:
                    cell = cell.replace(lesson_type_old[l], '', 1)
                    temp += ' (' + lesson_type_new[l] + ')'
                    break
            for p in rubbish:  # убирает мусор
                if not cell.find(p) == -1:
                    cell = cell.replace(p, '')
            if not cell == 'None':
                temp += cell
            elif cell == 'None':
                temp = '-'
            while not temp.find('  ') == -1: temp = temp.replace('  ', ' ')  # убираются лишние пробелы
            file.write(temp + '\n')
            i += 1  # переход к следующей строке
        # нет занятия
        else:
            file.write(str(j) + '. ')
            file.write('-\n')
            i += 1  # переход к следующей строке
        if j == 5 and not weekday == 4:
            file.write('\n')
        if j == 5 and weekday == 4:
            file.close()


tz = pytz.timezone('Europe/Moscow')  # часовой пояс
weekday_now = datetime.now(tz).weekday()  # текущая неделя


def date(date_search, sheet):
    date_search = datetime.strftime(date_search, '%d/%m')
    for z in range(0, 9):  # замена даты
        if not date_search.find(date_replace_old[z]) == -1: date_search = date_search.replace(date_replace_old[z],
                                                                                              date_replace_new[z])
    for i in range(14, 634):  # определение текущего дня в таблице
        need_date = str(sheet['A' + str(i)].value)
        if not need_date == 'None':
            for u in date_list:
                need_date = need_date.replace('\n', '')
                need_date = need_date.replace(' ', '')
                if not need_date.find(u) == -1: need_date = need_date.replace(u, '')
                if need_date == date_search:
                    return i


def day(r, sheet):
    f = datetime.strftime(r, '%d.%m.%Y')
    t = r.weekday()
    timetable(date(r, sheet), t, f, sheet)


now = datetime.now(tz)
one = timedelta(1)
two = timedelta(2)
three = timedelta(3)
four = timedelta(4)
five = timedelta(5)
six = timedelta(6)
seven = timedelta(7)
eight = timedelta(8)
nine = timedelta(9)
ten = timedelta(10)
eleven = timedelta(11)


# текущая неделя
def timetable_now():
#    download.DownloadFile('IF-1-kurs.xlsx')
    sheet = open_excel_file()
    if weekday_now == 0:  # понедельник
        day(now, sheet)
        day(now + one, sheet)
        day(now + two, sheet)
        day(now + three, sheet)
        day(now + four, sheet)
    elif weekday_now == 1:  # вторник
        day(now - one, sheet)
        day(now, sheet)
        day(now + one, sheet)
        day(now + two, sheet)
        day(now + three, sheet)
    elif weekday_now == 2:  # среда
        day(now - two, sheet)
        day(now - one, sheet)
        day(now, sheet)
        day(now + one, sheet)
        day(now + two, sheet)
    elif weekday_now == 3:  # четверг
        day(now - three, sheet)
        day(now - two, sheet)
        day(now - one, sheet)
        day(now, sheet)
        day(now + one, sheet)
    elif weekday_now == 4:  # пятница
        day(now - four, sheet)
        day(now - three, sheet)
        day(now - two, sheet)
        day(now - one, sheet)
        day(now, sheet)
    elif weekday_now == 5:  # суббота
        day(now - five, sheet)
        day(now - four, sheet)
        day(now - three, sheet)
        day(now - two, sheet)
        day(now - one, sheet)
    elif weekday_now == 6:  # воскресенье
        day(now - six, sheet)
        day(now - five, sheet)
        day(now - four, sheet)
        day(now - three, sheet)
        day(now - two, sheet)


# следующая неделя
def timetable_next():
#    download.DownloadFile('IF-1-kurs.xlsx')
    sheet = open_excel_file()
    if weekday_now == 0:  # понедельник
        day(now + seven, sheet)
        day(now + eight, sheet)
        day(now + nine, sheet)
        day(now + ten, sheet)
        day(now + eleven, sheet)
    elif weekday_now == 1:  # вторник
        day(now + six, sheet)
        day(now + seven, sheet)
        day(now + eight, sheet)
        day(now + nine, sheet)
        day(now + ten, sheet)
    elif weekday_now == 2:  # среда
        day(now + five, sheet)
        day(now + six, sheet)
        day(now + seven, sheet)
        day(now + eight, sheet)
        day(now + nine, sheet)
    elif weekday_now == 3:  # четверг
        day(now + four, sheet)
        day(now + five, sheet)
        day(now + six, sheet)
        day(now + seven, sheet)
        day(now + eight, sheet)
    elif weekday_now == 4:  # пятница
        day(now + three, sheet)
        day(now + four, sheet)
        day(now + five, sheet)
        day(now + six, sheet)
        day(now + seven, sheet)
    elif weekday_now == 5:  # суббота
        day(now + two, sheet)
        day(now + three, sheet)
        day(now + four, sheet)
        day(now + five, sheet)
        day(now + six, sheet)
    elif weekday_now == 6:  # воскресенье
        day(now + one, sheet)
        day(now + two, sheet)
        day(now + three, sheet)
        day(now + four, sheet)
        day(now + five, sheet)
