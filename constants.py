# Все константы и конфигурация проекта TimetableBot

# Часовой пояс
TIMEZONE = 'Europe/Moscow'

# Директории
DIR_TIMETABLE_DBS = 'timetable-dbs'
DIR_TIMETABLE_FILES = 'timetable-files'
DIR_DOWNLOADS = 'downloads'
DIR_LOG = 'log'
DIR_CALENDARS = 'calendars'
DIR_DBS = 'dbs'

# Glob-паттерны и пути к БД
GLOB_TIMETABLE_DB = 'timetable-dbs/timetable*.db'
PATH_USER_SETTINGS = 'user_settings.db'
PATH_CALENDARS_DB = 'calendars_list.db'

# URLs
URL_INSTRUCTIONS = 'https://nicarex.github.io/timetablebot-site/'
GITHUB_REPO_NAME = 'Nicarex/timetablebot-files'
GITHUB_CALENDARS_BASE_URL = 'https://raw.githubusercontent.com/Nicarex/timetablebot-files/main/calendars/'

# Время занятий: номер пары -> (начало, конец)
LESSON_TIMES = {
    1: ('09:00', '10:30'),
    2: ('10:45', '12:15'),
    3: ('12:30', '14:00'),
    4: ('14:40', '16:10'),
    5: ('16:25', '17:55'),
    6: ('18:05', '19:35'),
}

# Строковое представление времени пар для отображения (индекс = номер пары)
LESSON_TIMES_DISPLAY = ['', '09:00-10:30', '10:45-12:15', '12:30-14:00', '14:40-16:10', '16:25-17:55', '18:05-19:35']


def lesson_time_str(lesson_num: int) -> str:
    """Возвращает строку '09:00-10:30' для номера пары, или '' если номер некорректный."""
    if lesson_num not in LESSON_TIMES:
        return ''
    start, end = LESSON_TIMES[lesson_num]
    return f'{start}-{end}'


# Дни недели для файла расписания
DAYS_OF_WEEK = [
    'ПОНЕДЕЛЬНИК - ', '\nВТОРНИК - ', '\nСРЕДА - ', '\nЧЕТВЕРГ - ',
    '\nПЯТНИЦА - ', '\nСУББОТА - ', '\nВОСКРЕСЕНЬЕ - '
]

# Названия месяцев (родительный -> именительный)
MONTH_NAMES = {
    'января': 'январь', 'февраля': 'февраль', 'марта': 'март',
    'апреля': 'апрель', 'мая': 'май', 'июня': 'июнь',
    'июля': 'июль', 'августа': 'август', 'сентября': 'сентябрь',
    'октября': 'октябрь', 'ноября': 'ноябрь', 'декабря': 'декабрь',
}

# Типы занятий (сокращение -> полное название)
LESSON_TYPE_NAMES = {
    'л': 'лекция', 'пз': 'практическое занятие',
    'зао': 'зачет с оценкой', 'экз.': 'экзамен',
    'српп': 'самостоятельная работа под руководством преподавателя',
    'гк': 'групповая консультация', 'см': 'семинар',
    'контр.р': 'контрольная работа', 'лр': 'лабораторная работа',
    'курс.р': 'курсовая работа',
}

# Префикс сообщений
MESSAGE_PREFIX = '➡ '

# Разделитель для разбиения длинных ответов
MESSAGE_SPLIT_SENTINEL = 'Cut\n'

# VK club ID (используется в text-матчинге чат-хэндлеров)
VK_CLUB_ID = 199038911

# Discord admin username
DISCORD_ADMIN_USERNAME = 'Nicare#6529'

# Информация об авторе
AUTHOR_INFO = (
    'Автор бота:\nстудент 307 группы\nНасонов Никита\n\n'
    'Контакты:\nVK: https://vk.com/nicarex\nEmail: my.profile.protect@gmail.com'
)

# Таймауты и задержки (секунды)
SQL_TIMEOUT = 20
VK_SEND_DELAY = 0.25
MAIL_RETRY_WAIT = 120
CALENDAR_REFRESH_INTERVAL = 'PT6H'
