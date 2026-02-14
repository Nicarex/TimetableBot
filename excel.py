from sqlite3 import Row
from other import connection_to_sql, get_latest_file, get_row_value
from logger import logger
import pendulum
import xlsxwriter
import os
from constants import TIMEZONE, GLOB_TIMETABLE_DB, MONTH_NAMES, LESSON_TIMES_DISPLAY


DAYS_OF_WEEK_NAMES = {
    0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
    4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье',
}


def create_excel_with_workload(teacher: str = None, group_id: str = None, next: str = None):
    """
    Создает файл Excel с учебной нагрузкой за месяц.
    teacher - создать файл для преподавателя
    group_id - создать файл для группы
    next - следующий месяц
    Возвращает путь к файлу или строку с ошибкой.
    """
    if teacher is None and group_id is None:
        return 'Не указан преподаватель или группа'

    db_timetable = get_latest_file(GLOB_TIMETABLE_DB)
    if db_timetable is None:
        logger.error('Cant create excel with workload because no db-files in timetable-dbs directory')
        return 'Извините, но в данный момент я не могу обработать ваш запрос, пожалуйста, попробуйте позже'

    pendulum.set_locale('ru')
    dt = pendulum.now(tz=TIMEZONE)

    if next is None:
        first_day_of_month = dt.start_of('month')
    else:
        first_day_of_month = dt.add(months=1).start_of('month')

    # Все дни месяца
    all_dates_of_month = []
    current_day = first_day_of_month
    while current_day.month == first_day_of_month.month:
        all_dates_of_month.append(current_day)
        current_day = current_day.add(days=1)

    month_name = MONTH_NAMES.get(first_day_of_month.format('MMMM'), first_day_of_month.format('MMMM'))

    conn = connection_to_sql(db_timetable)
    conn.row_factory = Row
    c = conn.cursor()

    # Определяем фильтр и название
    if teacher is not None:
        filter_column = 'Name'
        filter_value = teacher
        entity_label = f'Преподаватель: {teacher}'
        other_column = 'Group'
        other_label = 'Группы'
    else:
        filter_column = 'Group'
        filter_value = group_id
        entity_label = f'Группа: {group_id}'
        other_column = 'Name'
        other_label = 'Преподаватель'

    # Собираем все занятия за месяц
    lessons = []
    last_row_key = None
    for day in all_dates_of_month:
        date_str = day.format('D-MM-YYYY')
        rows = c.execute(
            f'SELECT * FROM timetable WHERE "{filter_column}" = ? AND "Date" = ? ORDER BY "Les", "{other_column}", "Subg"',
            (str(filter_value), date_str)
        ).fetchall()

        for row in rows:
            row_key = (get_row_value(row, 'Les'), get_row_value(row, 'Date'))
            # Пропускаем дубликаты пар (подгруппы на одной паре)
            if row_key == last_row_key:
                # Но собираем дополнительные группы/преподавателей
                if lessons:
                    other_val = str(get_row_value(row, other_column))
                    if other_val not in lessons[-1]['others']:
                        lessons[-1]['others'].append(other_val)
                continue
            last_row_key = row_key

            subj_type = get_row_value(row, 'Subj_type')
            # Обработка None значений
            if subj_type is None:
                subj_type = 'Не указано'
            if subj_type in ('ГК', 'Консультация', 'Проверка'):
                hours = 1.0
            else:
                hours = 2.0

            lessons.append({
                'date': day,
                'date_str': day.format('DD.MM.YYYY'),
                'day_of_week': DAYS_OF_WEEK_NAMES.get(day.day_of_week, ''),
                'lesson_num': get_row_value(row, 'Les'),
                'lesson_time': LESSON_TIMES_DISPLAY[int(get_row_value(row, 'Les'))] if int(get_row_value(row, 'Les')) <= 6 else '',
                'subject': get_row_value(row, 'Subject'),
                'subj_type': subj_type,
                'auditorium': get_row_value(row, 'Aud'),
                'others': [str(get_row_value(row, other_column))],
                'hours': hours,
            })

    c.close()
    conn.close()

    if not lessons:
        return f'Не найдено занятий за {month_name} для {"преподавателя " + teacher if teacher else "группы " + group_id}'

    # Генерация имени файла
    safe_name = (teacher or group_id).replace('/', '').replace('\\', '').replace(' ', '_')
    suffix = '_next' if next else ''
    filepath = f'timetable-files/workload_{safe_name}{suffix}.xlsx'

    # Создаем директорию, если ее нет
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)

    workbook = xlsxwriter.Workbook(filepath)
    worksheet = workbook.add_worksheet('Нагрузка')

    # Форматы
    fmt_title = workbook.add_format({
        'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#2980b9', 'font_color': 'white',
    })
    fmt_header = workbook.add_format({
        'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#d5e8f0', 'text_wrap': True,
    })
    fmt_cell = workbook.add_format({
        'font_size': 10, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'text_wrap': True,
    })
    fmt_cell_left = workbook.add_format({
        'font_size': 10, 'align': 'left', 'valign': 'vcenter',
        'border': 1, 'text_wrap': True,
    })
    fmt_total = workbook.add_format({
        'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#f0e68c',
    })
    fmt_total_left = workbook.add_format({
        'bold': True, 'font_size': 11, 'align': 'left', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#f0e68c',
    })
    fmt_summary_header = workbook.add_format({
        'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#3498db', 'font_color': 'white',
    })

    # Ширина колонок
    worksheet.set_column(0, 0, 14)   # Дата
    worksheet.set_column(1, 1, 14)   # День недели
    worksheet.set_column(2, 2, 6)    # Пара
    worksheet.set_column(3, 3, 14)   # Время
    worksheet.set_column(4, 4, 30)   # Предмет
    worksheet.set_column(5, 5, 14)   # Тип занятия
    worksheet.set_column(6, 6, 12)   # Аудитория
    worksheet.set_column(7, 7, 25)   # Группы/Преподаватель
    worksheet.set_column(8, 8, 8)    # Часы

    # Заголовок
    worksheet.merge_range(0, 0, 0, 8, f'{entity_label} — Нагрузка за {month_name} {first_day_of_month.format("YYYY")}', fmt_title)

    # Шапка таблицы
    headers = ['Дата', 'День недели', 'Пара', 'Время', 'Предмет', 'Тип занятия', 'Аудитория', other_label, 'Часы']
    for col, header in enumerate(headers):
        worksheet.write(1, col, header, fmt_header)

    # Данные
    row_num = 2
    for lesson in lessons:
        worksheet.write(row_num, 0, lesson['date_str'], fmt_cell)
        worksheet.write(row_num, 1, lesson['day_of_week'], fmt_cell)
        worksheet.write(row_num, 2, lesson['lesson_num'], fmt_cell)
        worksheet.write(row_num, 3, lesson['lesson_time'], fmt_cell)
        worksheet.write(row_num, 4, lesson['subject'], fmt_cell_left)
        worksheet.write(row_num, 5, lesson['subj_type'], fmt_cell)
        worksheet.write(row_num, 6, lesson['auditorium'], fmt_cell)
        worksheet.write(row_num, 7, ', '.join(lesson['others']), fmt_cell_left)
        worksheet.write(row_num, 8, lesson['hours'], fmt_cell)
        row_num += 1

    # Итого
    total_hours = sum(l['hours'] for l in lessons)
    worksheet.merge_range(row_num, 0, row_num, 7, 'ИТОГО', fmt_total)
    worksheet.write(row_num, 8, total_hours, fmt_total)
    row_num += 2

    # Сводка по типам занятий
    type_summary = {}
    for lesson in lessons:
        st = lesson['subj_type']
        if st not in type_summary:
            type_summary[st] = {'count': 0, 'hours': 0.0}
        type_summary[st]['count'] += 1
        type_summary[st]['hours'] += lesson['hours']

    worksheet.merge_range(row_num, 0, row_num, 2, 'Итоги по типам занятий', fmt_summary_header)
    row_num += 1
    worksheet.write(row_num, 0, 'Тип занятия', fmt_header)
    worksheet.write(row_num, 1, 'Кол-во пар', fmt_header)
    worksheet.write(row_num, 2, 'Часы', fmt_header)
    row_num += 1

    for subj_type, data in sorted(type_summary.items(), key=lambda x: str(x[0])):
        worksheet.write(row_num, 0, subj_type, fmt_cell_left)
        worksheet.write(row_num, 1, data['count'], fmt_cell)
        worksheet.write(row_num, 2, data['hours'], fmt_cell)
        row_num += 1

    worksheet.write(row_num, 0, 'ИТОГО', fmt_total_left)
    worksheet.write(row_num, 1, sum(d['count'] for d in type_summary.values()), fmt_total)
    worksheet.write(row_num, 2, total_hours, fmt_total)

    workbook.close()
    logger.log('EXCEL', f'Excel workload file created: {filepath}')
    return filepath
