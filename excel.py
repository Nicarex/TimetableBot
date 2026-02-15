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


def _resolve_filter(teacher, group_id):
    if teacher is not None:
        return 'Name', teacher, f'Преподаватель: {teacher}', 'Group', 'Группы'
    else:
        return 'Group', group_id, f'Группа: {group_id}', 'Name', 'Преподаватель'


def _get_days_of_month(first_day):
    days = []
    current_day = first_day
    while current_day.month == first_day.month:
        days.append(current_day)
        current_day = current_day.add(days=1)
    return days


def _fetch_lessons_for_month(cursor, filter_column, filter_value, other_column, all_dates_of_month):
    lessons = []
    last_row_key = None
    for day in all_dates_of_month:
        date_str = day.format('D-MM-YYYY')
        rows = cursor.execute(
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

            try:
                les_int = int(get_row_value(row, 'Les'))
            except (TypeError, ValueError):
                les_int = 0

            lessons.append({
                'date': day,
                'date_str': day.format('DD.MM.YYYY'),
                'day_of_week': DAYS_OF_WEEK_NAMES.get(day.day_of_week, ''),
                'lesson_num': les_int,
                'lesson_time': LESSON_TIMES_DISPLAY[les_int] if 1 <= les_int <= 6 else '',
                'subject': get_row_value(row, 'Subject'),
                'subj_type': subj_type,
                'auditorium': get_row_value(row, 'Aud'),
                'others': [str(get_row_value(row, other_column))],
                'hours': hours,
            })
    return lessons


def _make_workbook_formats(workbook):
    return {
        'title': workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#2980b9', 'font_color': 'white',
        }),
        'header': workbook.add_format({
            'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#d5e8f0', 'text_wrap': True,
        }),
        'cell': workbook.add_format({
            'font_size': 10, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'text_wrap': True,
        }),
        'cell_left': workbook.add_format({
            'font_size': 10, 'align': 'left', 'valign': 'vcenter',
            'border': 1, 'text_wrap': True,
        }),
        'total': workbook.add_format({
            'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#f0e68c',
        }),
        'total_left': workbook.add_format({
            'bold': True, 'font_size': 11, 'align': 'left', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#f0e68c',
        }),
        'summary_header': workbook.add_format({
            'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#3498db', 'font_color': 'white',
        }),
    }


def _write_workload_sheet(workbook, formats, sheet_name, entity_label, other_label, month_name, year_str, lessons):
    worksheet = workbook.add_worksheet(sheet_name)

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
    worksheet.merge_range(0, 0, 0, 8, f'{entity_label} — Нагрузка за {month_name.capitalize()} {year_str}', formats['title'])

    # Шапка таблицы
    headers = ['Дата', 'День недели', 'Пара', 'Время', 'Предмет', 'Тип занятия', 'Аудитория', other_label, 'Часы']
    for col, header in enumerate(headers):
        worksheet.write(1, col, header, formats['header'])

    # Данные
    row_num = 2
    for lesson in lessons:
        worksheet.write(row_num, 0, lesson['date_str'], formats['cell'])
        worksheet.write(row_num, 1, lesson['day_of_week'], formats['cell'])
        worksheet.write(row_num, 2, lesson['lesson_num'], formats['cell'])
        worksheet.write(row_num, 3, lesson['lesson_time'], formats['cell'])
        worksheet.write(row_num, 4, lesson['subject'], formats['cell_left'])
        worksheet.write(row_num, 5, lesson['subj_type'], formats['cell'])
        worksheet.write(row_num, 6, lesson['auditorium'], formats['cell'])
        worksheet.write(row_num, 7, ', '.join(lesson['others']), formats['cell_left'])
        worksheet.write(row_num, 8, lesson['hours'], formats['cell'])
        row_num += 1

    # Итого (формула SUM по колонке "Часы")
    data_first_excel_row = 3  # данные начинаются с 0-based row 2 = Excel row 3
    data_last_excel_row = row_num  # row_num (0-based) = Excel row_num+1, последняя строка данных = row_num-1 (0-based) = row_num (Excel)
    worksheet.merge_range(row_num, 0, row_num, 7, 'ИТОГО', formats['total'])
    worksheet.write_formula(row_num, 8, f'=SUM(I{data_first_excel_row}:I{data_last_excel_row})', formats['total'])
    row_num += 2

    # Сводка по типам занятий
    lesson_types = sorted(set(l['subj_type'] for l in lessons), key=str)

    worksheet.merge_range(row_num, 0, row_num, 2, 'Итоги по типам занятий', formats['summary_header'])
    row_num += 1
    worksheet.write(row_num, 0, 'Тип занятия', formats['header'])
    worksheet.write(row_num, 1, 'Кол-во пар', formats['header'])
    worksheet.write(row_num, 2, 'Часы', formats['header'])
    row_num += 1

    summary_data_first_row = row_num  # первая строка данных сводки (0-based)
    for subj_type in lesson_types:
        worksheet.write(row_num, 0, subj_type, formats['cell_left'])
        # COUNTIF: считаем кол-во пар данного типа в колонке F (Тип занятия)
        worksheet.write_formula(row_num, 1,
            f'=COUNTIF(F${data_first_excel_row}:F${data_last_excel_row},A{row_num + 1})',
            formats['cell'])
        # SUMIF: суммируем часы для данного типа
        worksheet.write_formula(row_num, 2,
            f'=SUMIF(F${data_first_excel_row}:F${data_last_excel_row},A{row_num + 1},I${data_first_excel_row}:I${data_last_excel_row})',
            formats['cell'])
        row_num += 1

    summary_data_last_excel_row = row_num  # row_num уже увеличен, последняя строка = row_num-1 (0-based) = row_num (Excel)
    worksheet.write(row_num, 0, 'ИТОГО', formats['total_left'])
    worksheet.write_formula(row_num, 1,
        f'=SUM(B{summary_data_first_row + 1}:B{summary_data_last_excel_row})',
        formats['total'])
    worksheet.write_formula(row_num, 2,
        f'=SUM(C{summary_data_first_row + 1}:C{summary_data_last_excel_row})',
        formats['total'])


def create_excel_with_workload(teacher: str = None, group_id: str = None, next: str = None, month_year: tuple = None):
    """
    Создает файл Excel с учебной нагрузкой за месяц.
    teacher - создать файл для преподавателя
    group_id - создать файл для группы
    next - следующий месяц
    month_year - кортеж (месяц, год), например (2, 2025) для февраля 2025. Приоритет выше next.
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

    if month_year is not None:
        first_day_of_month = pendulum.datetime(month_year[1], month_year[0], 1, tz=TIMEZONE)
    elif next is None:
        first_day_of_month = dt.start_of('month')
    else:
        first_day_of_month = dt.add(months=1).start_of('month')

    all_dates_of_month = _get_days_of_month(first_day_of_month)
    month_name = MONTH_NAMES.get(first_day_of_month.format('MMMM'), first_day_of_month.format('MMMM'))

    filter_column, filter_value, entity_label, other_column, other_label = _resolve_filter(teacher, group_id)

    conn = connection_to_sql(db_timetable)
    conn.row_factory = Row
    c = conn.cursor()
    lessons = _fetch_lessons_for_month(c, filter_column, filter_value, other_column, all_dates_of_month)
    c.close()
    conn.close()

    if not lessons:
        return f'Не найдено занятий за {month_name} для {"преподавателя " + teacher if teacher else "группы " + group_id}'

    # Генерация имени файла
    safe_name = (teacher or group_id).replace('/', '').replace('\\', '').replace(' ', '_')
    if month_year is not None:
        suffix = f'_{month_year[1]}_{month_year[0]:02d}'
    elif next:
        suffix = '_next'
    else:
        suffix = ''
    filepath = f'timetable-files/workload_{safe_name}{suffix}.xlsx'

    # Создаем директорию, если ее нет
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)

    workbook = xlsxwriter.Workbook(filepath)
    formats = _make_workbook_formats(workbook)
    _write_workload_sheet(workbook, formats, 'Нагрузка', entity_label, other_label,
                          month_name, first_day_of_month.format('YYYY'), lessons)
    workbook.close()
    logger.log('EXCEL', f'Excel workload file created: {filepath}')
    return filepath


def create_excel_with_workload_all_months(teacher: str = None, group_id: str = None, all_months: list = None):
    """
    Создает один файл Excel с нагрузкой за все месяцы (каждый месяц — отдельный лист).
    teacher - создать файл для преподавателя
    group_id - создать файл для группы
    all_months - список кортежей (месяц, год), например [(2, 2025), (3, 2025)]
    Возвращает путь к файлу или строку с ошибкой.
    """
    if teacher is None and group_id is None:
        return 'Не указан преподаватель или группа'
    if not all_months:
        return 'Нет доступных месяцев в базе данных'

    db_timetable = get_latest_file(GLOB_TIMETABLE_DB)
    if db_timetable is None:
        logger.error('Cant create excel (all months) because no db-files in timetable-dbs directory')
        return 'Извините, но в данный момент я не могу обработать ваш запрос, пожалуйста, попробуйте позже'

    pendulum.set_locale('ru')
    filter_column, filter_value, entity_label, other_column, other_label = _resolve_filter(teacher, group_id)

    conn = connection_to_sql(db_timetable)
    conn.row_factory = Row
    c = conn.cursor()

    # Собираем данные по каждому месяцу
    month_data = []
    for (month, year) in all_months:
        first_day = pendulum.datetime(year, month, 1, tz=TIMEZONE)
        all_dates = _get_days_of_month(first_day)
        lessons = _fetch_lessons_for_month(c, filter_column, filter_value, other_column, all_dates)
        if not lessons:
            continue
        month_name = MONTH_NAMES.get(first_day.format('MMMM'), first_day.format('MMMM'))
        year_str = first_day.format('YYYY')
        sheet_name = f'{month_name.capitalize()} {year_str}'
        month_data.append((sheet_name, month_name, year_str, lessons))

    c.close()
    conn.close()

    if not month_data:
        entity_desc = f'преподавателя {teacher}' if teacher else f'группы {group_id}'
        return f'Не найдено занятий ни за один месяц для {entity_desc}'

    safe_name = (teacher or group_id).replace('/', '').replace('\\', '').replace(' ', '_')
    filepath = f'timetable-files/workload_{safe_name}_all_months.xlsx'
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)

    workbook = xlsxwriter.Workbook(filepath)
    formats = _make_workbook_formats(workbook)

    for (sheet_name, month_name, year_str, lessons) in month_data:
        _write_workload_sheet(workbook, formats, sheet_name, entity_label, other_label,
                              month_name, year_str, lessons)

    workbook.close()
    logger.log('EXCEL', f'Excel all-months workload file created: {filepath}')
    return filepath
