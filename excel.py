from sqlite3 import Row
from other import connection_to_sql, get_latest_file
from logger import logger
import pendulum
import xlsxwriter


def create_excel_with_workload(teacher: str = None, caf_id: str = None, all_teachers: str = None, next: str = None):
    """
    Создает файл Excel с учебной нагрузкой.
    teacher - создать файл для преподавателя
    caf_id - создать файл, состоящий из преподавателей одной кафедры
    all_teachers - создать файл, содержащий всех преподавателей, разделенный по кафедрам
    next - следующий период. Для teacher - следующий месяц, для caf_id - следующий семестр
    """
    if all_teachers is not None and (teacher is None and caf_id is None):
        # Выбирается бд
        db_timetable = get_latest_file('timetable-dbs/timetable*.db')
        if db_timetable is None:
            logger.error('Cant create excel with workload because no db-files in timetable-dbs directory')
            return 'Извините, но в данный момент я не могу обработать ваш запрос, пожалуйста, попробуйте позже'
        # Текущее время
        pendulum.set_locale('ru')
        dt = pendulum.now(tz='Europe/Moscow')
        # Подключение к бд
        conn = connection_to_sql(db_timetable)
        conn.row_factory = Row
        c = conn.cursor()
        # Поиск в бд
        for year in range(1, 4):
            # Проверяем предыдущий год
            if year == 1:
                date_in_cycle = dt.subtract(years=1)
            # Проверяем текущий год
            elif year == 2:
                date_in_cycle = dt
            # Проверяем следующий год
            elif year == 3:
                date_in_cycle = dt.add(years=1)
            # Проверяем каждый месяц
            for month in range(1, 13):
                if month / 10 < 1:
                    month_for_db = str(date_in_cycle.format(f'[%-0{str(month)}]-YYYY'))
                else:
                    month_for_db = str(date_in_cycle.format(f'[%-{str(month)}]-YYYY'))
                rows_with_month = c.execute('SELECT * FROM timetable WHERE "Date" LIKE ?', (month_for_db,)).fetchall()
                # if rows_with_month:


workbook = xlsxwriter.Workbook('hello.xlsx')
worksheet = workbook.add_worksheet()

worksheet.write('A1', 'Hello world')

workbook.close()


# with logger.catch():
    # create_excel_with_workload(all_teachers='YES')