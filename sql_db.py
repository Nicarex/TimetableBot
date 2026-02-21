import asyncio
import os
import platform
import random
import sqlite3
import threading
from glob import iglob
from pathlib import Path

from vkbottle import API
from vkbottle.http import AiohttpClient

from calendar_timetable import create_calendar_file_with_timetable, download_calendar_file_to_github
from constants import MESSAGE_PREFIX, MESSAGE_SPLIT_SENTINEL
from logger import logger
from contextlib import contextmanager
from other import read_config, get_latest_file, connection_to_sql, sendMail, get_row_value, format_timetable_html, DatabaseError, NotificationError
from timetable import date_request, timetable, workload
from excel import create_excel_with_workload, create_excel_with_workload_all_months
from constants import GLOB_TIMETABLE_DB
from platform_context import resolve_platform

@contextmanager
def _db_connection(name: str, row_factory=None):
    """Контекстный менеджер для БД: auto-commit, auto-rollback, auto-close.
    Использует модульную ссылку на connection_to_sql, чтобы моки в тестах работали."""
    conn = connection_to_sql(name)
    if conn is None:
        raise DatabaseError(f'Не удалось подключиться к БД: {name}')
    if row_factory:
        conn.row_factory = row_factory
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Кэш уникальных групп и преподавателей из timetable-db.
# Обновляется только при смене файла БД, что сильно ускоряет поиск.
_timetable_cache_lock = threading.Lock()
_timetable_cache = {
    'db_path': None,        # путь к БД, для которой построен кэш
    'groups': set(),        # уникальные группы
    'teachers': set(),      # уникальные преподаватели
}


def _refresh_timetable_cache(db_path: str):
    """Загружает уникальные группы и преподавателей из БД в кэш (только если БД изменилась)."""
    with _timetable_cache_lock:
        if _timetable_cache['db_path'] == db_path:
            return
        try:
            with _db_connection(db_path, row_factory=sqlite3.Row) as conn:
                c = conn.cursor()
                c.execute('SELECT DISTINCT "Group" FROM timetable WHERE "Group" IS NOT NULL AND "Group" != \' \'')
                groups = {str(row[0]) for row in c.fetchall()}
                c.execute('SELECT DISTINCT "Name" FROM timetable WHERE "Name" IS NOT NULL AND "Name" != \' \'')
                teachers = {str(row[0]) for row in c.fetchall()}
            _timetable_cache['db_path'] = db_path
            _timetable_cache['groups'] = groups
            _timetable_cache['teachers'] = teachers
            logger.log('SQL', f'Timetable cache refreshed: {len(groups)} groups, {len(teachers)} teachers')
        except Exception as e:
            logger.error(f'Failed to refresh timetable cache: {e}')

# Инициализация
vk_token = read_config(vk='YES')
tg_token = read_config(telegram='YES')
ds_token = read_config(discord='YES')


# В Windows asyncio есть баг, это исправление
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ─── Вспомогательные функции для работы с единой таблицей users ───

def _get_user(cursor, platform_name: str, platform_id: str):
    """Возвращает строку пользователя из таблицы users или None."""
    return cursor.execute(
        'SELECT * FROM users WHERE platform = ? AND platform_id = ?',
        (platform_name, platform_id)
    ).fetchone()


def _get_user_teachers(cursor, user_id: int) -> list:
    """Возвращает список преподавателей пользователя."""
    return [r['teacher'] for r in cursor.execute(
        'SELECT teacher FROM user_teachers WHERE user_id = ?', (user_id,)
    ).fetchall()]


def _get_user_groups(cursor, user_id: int) -> list:
    """Возвращает список групп пользователя."""
    return [r['group_id'] for r in cursor.execute(
        'SELECT group_id FROM user_groups WHERE user_id = ?', (user_id,)
    ).fetchall()]


def _get_notifiable_users_with_subs(cursor, platform_name: str) -> list:
    """Загружает пользователей с подписками одним JOIN-запросом вместо N+1."""
    rows = cursor.execute('''
        SELECT u.id, u.platform_id, u.notification, u.lesson_time,
               ut.teacher, ug.group_id
        FROM users u
        LEFT JOIN user_teachers ut ON ut.user_id = u.id
        LEFT JOIN user_groups ug ON ug.user_id = u.id
        WHERE u.platform = ? AND u.notification = 1
    ''', (platform_name,)).fetchall()
    users = {}
    for row in rows:
        uid = row['id']
        if uid not in users:
            users[uid] = {
                'id': uid,
                'platform_id': row['platform_id'],
                'notification': row['notification'],
                'lesson_time': row['lesson_time'],
                'teachers': set(),
                'groups': set(),
            }
        if row['teacher']:
            users[uid]['teachers'].add(row['teacher'])
        if row['group_id']:
            users[uid]['groups'].add(row['group_id'])
    # Конвертируем set в list для совместимости
    for u in users.values():
        u['teachers'] = list(u['teachers'])
        u['groups'] = list(u['groups'])
    return list(users.values())


# ─── Отправка сообщений ───

async def write_msg_vk_chat(message: str, chat_id: str):
    logger.log('SQL', f'Try to send message to vk chat <{str(chat_id)}>')
    api = API(vk_token, http_client=AiohttpClient())
    try:
        chat_id = int(chat_id)
        if chat_id > 2000000000:
            peer_id = chat_id
        else:
            peer_id = 2000000000 + chat_id
        result = await api.messages.send(
            message=MESSAGE_PREFIX + message,
            peer_id=peer_id,
            random_id=random.randint(1, 2**31 - 1)
        )
        logger.log('SQL', f'Message have been sent to vk chat <{str(chat_id)}>, result: {result}')
        await asyncio.sleep(.25)
        return True
    except Exception as e:
        logger.log('SQL', f'Error happened while sending message to vk chat <{str(chat_id)}>: {e}')
        return False
    finally:
        await api.http_client.close()


async def write_msg_vk_user(message: str, user_id: str):
    logger.log('SQL', f'Try to send message to vk user <{str(user_id)}>')
    api = API(vk_token, http_client=AiohttpClient())
    try:
        user_id = int(user_id)
        result = await api.messages.send(
            message=MESSAGE_PREFIX + message,
            peer_id=user_id,
            random_id=random.randint(1, 2**31 - 1)
        )
        logger.log('SQL', f'Message have been sent to vk user <{str(user_id)}>, result: {result}')
        await asyncio.sleep(.25)
        return True
    except Exception as e:
        logger.log('SQL', f'Error happened while sending message to vk user <{str(user_id)}>: {e}')
        return False
    finally:
        await api.http_client.close()


async def write_msg_telegram(message: str, tg_id):
    logger.log('SQL', f'Try to send message to telegram <{str(tg_id)}>')
    from aiogram import Bot
    import re
    bot = Bot(token=tg_token)

    def _extract_new_supergroup_id(text: str):
        if not text:
            return None
        m = re.search(r'migrated to a supergroup with id\s+(-?\d+)', text)
        if m:
            return m.group(1)
        m = re.search(r'supergroup with id\s+(-?\d+)', text)
        if m:
            return m.group(1)
        m = re.search(r'(-100\d{6,})', text)
        if m:
            return m.group(1)
        return None

    async def _send_single(single_id):
        try:
            try:
                chat_id = int(single_id)
            except Exception:
                chat_id = single_id
            await bot.send_message(chat_id=chat_id, text=MESSAGE_PREFIX + message)
            logger.log('SQL', f'Message have been sent to telegram <{str(single_id)}>)')
            return True
        except Exception as e:
            err_text = str(e)
            new_id = _extract_new_supergroup_id(err_text)
            if new_id is not None:
                logger.log('SQL', f'Telegram chat {single_id} was migrated to supergroup {new_id}, updating DB and retrying')
                try:
                    conn = connection_to_sql('user_settings.db')
                    cur = conn.cursor()
                    cur.execute(
                        'UPDATE users SET platform_id = ? WHERE platform = ? AND platform_id = ?',
                        (str(new_id), 'telegram', str(single_id)))
                    conn.commit()
                    cur.close()
                    conn.close()
                    logger.log('SQL', f'Updated telegram platform_id in DB: {single_id} -> {new_id}')
                except Exception as db_e:
                    logger.log('SQL', f'Failed to update telegram platform_id in DB for {single_id}: {db_e}')
                try:
                    await bot.send_message(chat_id=int(new_id), text=MESSAGE_PREFIX + message)
                    logger.log('SQL', f'Message have been sent to telegram <{str(new_id)}>)')
                    return True
                except Exception as e2:
                    logger.log('SQL', f'Error happened while sending message to migrated telegram id <{str(new_id)}>: {e2}')
                    return False
            else:
                lower_err = err_text.lower() if err_text else ''
                disabled_conditions = [
                    'bot was blocked',
                    'user is deactivated',
                ]
                if any(cond in lower_err for cond in disabled_conditions) or (('forbidden' in lower_err) and ('blocked' in lower_err)):
                    reason = 'user deactivated' if 'deactiv' in lower_err else 'bot blocked'
                    logger.log('SQL', f'Telegram notifications will be disabled for <{single_id}> ({reason})')
                    try:
                        conn = connection_to_sql('user_settings.db')
                        cur = conn.cursor()
                        cur.execute(
                            'UPDATE users SET notification = 0 WHERE platform = ? AND platform_id = ?',
                            ('telegram', str(single_id)))
                        conn.commit()
                        cur.close()
                        conn.close()
                        logger.log('SQL', f'Disabled telegram notifications for <{single_id}> in DB')
                    except Exception as db_e:
                        logger.log('SQL', f'Failed to disable telegram notifications for <{single_id}>: {db_e}')
                    return False
                logger.log('SQL', f'Error happened while sending message to telegram <{str(single_id)}>: {e}')
                return False

    try:
        if isinstance(tg_id, (list, tuple)):
            results = []
            for item in tg_id:
                res = await _send_single(item)
                results.append(res)
                await asyncio.sleep(.25)
            return all(results)
        else:
            return await _send_single(tg_id)
    finally:
        await bot.session.close()


# ─── Создание / инициализация БД ───

def create_db_user_settings():
    path = 'dbs/user_settings.db'
    if Path(path).is_file():
        return True
    conn = connection_to_sql(name=path)
    if conn is None:
        logger.error(f'Не удалось создать или открыть базу данных {path}. Проверьте наличие файла и права доступа.')
        return False
    try:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform        TEXT NOT NULL,
                    platform_id     TEXT NOT NULL,
                    notification    INTEGER NOT NULL DEFAULT 1,
                    lesson_time     INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(platform, platform_id));
                    """)
        c.execute("""CREATE TABLE IF NOT EXISTS user_groups (
                    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    group_id        TEXT NOT NULL,
                    PRIMARY KEY (user_id, group_id));
                    """)
        c.execute("""CREATE TABLE IF NOT EXISTS user_teachers (
                    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    teacher         TEXT NOT NULL,
                    PRIMARY KEY (user_id, teacher));
                    """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_notification ON users(notification) WHERE notification = 1")
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_platform ON users(platform, platform_id)")
        conn.commit()
        c.close()
        conn.close()
        logger.log('SQL', 'User database has been created')
    except Exception as e:
        logger.error(f'Ошибка при создании таблиц в базе данных {path}: {e}')
        if conn:
            conn.close()
        return False


def create_db_calendars_list():
    path = 'dbs/calendars_list.db'
    if Path(path).is_file():
        return True
    conn = connection_to_sql(name=path)
    if conn is None:
        logger.error(f'Не удалось создать или открыть базу данных {path}. Проверьте наличие файла и права доступа.')
        return False
    try:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS calendars(
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id        TEXT,
                    teacher         TEXT,
                    calendar_url    TEXT,
                    UNIQUE(group_id, teacher));
                    """)
        conn.commit()
        c.close()
        conn.close()
        logger.log('SQL', 'Calendar database has been created')
    except Exception as e:
        logger.error(f'Ошибка при создании таблицы calendars в базе данных {path}: {e}')
        if conn:
            conn.close()
        return False


def init_databases():
    """Инициализация пользовательских БД. Вызывать после create_required_dirs()."""
    create_db_user_settings()
    create_db_calendars_list()


# ─── Уведомления ───

def _collect_notification_messages_normalized(user_row, user_teachers, user_groups,
                                              group_list_current_week, group_list_next_week,
                                              teacher_list_current_week, teacher_list_next_week):
    """Собирает список сообщений для рассылки уведомлений пользователю.
    Использует нормализованные списки teachers/groups вместо \n-строк."""
    messages = []
    teachers_set = set(user_teachers)
    groups_set = set(user_groups)
    for label, items_list, is_next, entity_set, entity_type in [
        ('текущую', teacher_list_current_week, False, teachers_set, 'преподавателя'),
        ('следующую', teacher_list_next_week, True, teachers_set, 'преподавателя'),
        ('текущую', group_list_current_week, False, groups_set, 'группы'),
        ('следующую', group_list_next_week, True, groups_set, 'группы'),
    ]:
        if not items_list:
            continue
        for item in items_list:
            if item in entity_set:
                msg_text = f'Изменения в расписании на {label} неделю для {entity_type} {item}'
                kw = {'teacher': item} if entity_type == 'преподавателя' else {'group_id': item}
                if is_next:
                    kw['next'] = 'YES'
                if user_row['lesson_time'] != 1:
                    kw['lesson_time'] = 'YES'
                messages.append((msg_text, timetable(**kw)))
    return messages


def send_notifications_email(group_list_current_week: list, group_list_next_week: list,
                             teacher_list_current_week: list, teacher_list_next_week: list):
    """Отправляет email-уведомления об изменениях расписания."""
    with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        email_users = _get_notifiable_users_with_subs(c, 'email')
        for user in email_users:
            messages = _collect_notification_messages_normalized(
                user, user['teachers'], user['groups'],
                group_list_current_week, group_list_next_week,
                teacher_list_current_week, teacher_list_next_week)
            if messages:
                answer = ''
                for msg_text, tt in messages:
                    answer += msg_text + '\n' + tt + '\n\n'
                html_answer = format_timetable_html(answer)
                try:
                    sendMail(to_email=user['platform_id'], subject='Изменения в расписании', text='', html=html_answer)
                except NotificationError as e:
                    logger.log('SQL', f'Failed to send notification email to {user["platform_id"]}: {e}')
    return True


async def _send_notifications_vk_async(platform_name, send_fn, log_label,
                                       group_list_current_week, group_list_next_week,
                                       teacher_list_current_week, teacher_list_next_week):
    """Общая асинхронная рассылка уведомлений VK (для чатов и пользователей)."""
    with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        vk_users = _get_notifiable_users_with_subs(c, platform_name)
    for user in vk_users:
        messages = _collect_notification_messages_normalized(
            user, user['teachers'], user['groups'],
            group_list_current_week, group_list_next_week,
            teacher_list_current_week, teacher_list_next_week)
        uid = user['platform_id']
        for msg_text, tt in messages:
            logger.log('SQL', f'Попытка отправки сообщения {log_label}: {uid}')
            try:
                await send_fn(msg_text, uid)
                await send_fn(tt, uid)
            except Exception as e:
                logger.log('SQL', f'Ошибка при отправке {log_label} {uid}: {e}')
            await asyncio.sleep(0.4)
    return True


def send_notifications_vk_chat(group_list_current_week: list, group_list_next_week: list,
                                teacher_list_current_week: list, teacher_list_next_week: list):
    return asyncio.run(_send_notifications_vk_async(
        'vk_chat', write_msg_vk_chat, 'VK чату',
        group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week))


def send_notifications_vk_user(group_list_current_week: list, group_list_next_week: list,
                                teacher_list_current_week: list, teacher_list_next_week: list):
    return asyncio.run(_send_notifications_vk_async(
        'vk_user', write_msg_vk_user, 'VK пользователю',
        group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week))


async def send_notifications_vk_both_async(group_list_current_week: list, group_list_next_week: list,
                                            teacher_list_current_week: list, teacher_list_next_week: list):
    """Async-рассылка VK-уведомлений (чаты + пользователи) в одном event loop.
    Используется notification listener'ом vk.py через постоянный event loop потока."""
    await _send_notifications_vk_async(
        'vk_chat', write_msg_vk_chat, 'VK чату',
        group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week)
    await _send_notifications_vk_async(
        'vk_user', write_msg_vk_user, 'VK пользователю',
        group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week)


async def _send_notifications_telegram_async(group_list_current_week, group_list_next_week,
                                              teacher_list_current_week, teacher_list_next_week):
    """Асинхронная рассылка уведомлений в Telegram."""
    with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        users = _get_notifiable_users_with_subs(c, 'telegram')
    for user in users:
        messages = _collect_notification_messages_normalized(
            user, user['teachers'], user['groups'],
            group_list_current_week, group_list_next_week,
            teacher_list_current_week, teacher_list_next_week)
        tg_id = user['platform_id']
        for msg_text, tt in messages:
            await write_msg_telegram(message=msg_text, tg_id=tg_id)
            for part in tt.split(MESSAGE_SPLIT_SENTINEL):
                if part:
                    await write_msg_telegram(message=part, tg_id=tg_id)
    return True


def send_notifications_telegram(group_list_current_week: list, group_list_next_week: list,
                                 teacher_list_current_week: list, teacher_list_next_week: list):
    """Обёртка для вызова асинхронной рассылки в Telegram."""
    return asyncio.run(_send_notifications_telegram_async(
        group_list_current_week, group_list_next_week,
        teacher_list_current_week, teacher_list_next_week))


# ─── Сравнение расписаний и рассылка ───

def update_changed_calendars(difference: list):
    """Обновляет iCal-файлы на GitHub для преподавателей и групп из списка изменений.
    Вызывается отдельно от compute_timetable_differences() чтобы можно было
    запустить параллельно с рассылкой уведомлений."""
    list_with_teachers = []
    list_with_groups = []
    with _db_connection('calendars_list.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        for row in difference:
            row_name = get_row_value(row, 'Name')
            row_group = get_row_value(row, 'Group')
            if not str(row_name) in list_with_teachers:
                list_with_teachers += [str(row_name)]
                calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (str(row_name),)).fetchone()
                if calendar_row:
                    if create_calendar_file_with_timetable(teacher=str(row_name)) is True:
                        if download_calendar_file_to_github(filename=str(row_name)) is False:
                            logger.log('SQL', f'Cant import timetable to calendar for teacher = "{str(row_name)}"')
                        else:
                            logger.log('SQL', f'Calendar for teacher = "{str(row_name)}" has been successfully updated')
            if not str(row_group) in list_with_groups:
                list_with_groups += [str(row_group)]
                calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (str(row_group),)).fetchone()
                if calendar_row:
                    if create_calendar_file_with_timetable(group_id=str(row_group)) is True:
                        if download_calendar_file_to_github(filename=str(row_group)) is False:
                            logger.log('SQL', f'Cant import timetable to calendar for group = {str(row_group)}')
                        else:
                            logger.log('SQL', f'Calendar for group = "{str(row_group)}" has been successfully updated')


def compute_timetable_differences():
    """Вычисляет разницу между последним и предыдущим расписанием.
    Возвращает tuple (event_dict, difference) где:
      event_dict — dict с ключами group_list_current_week, group_list_next_week,
                   teacher_list_current_week, teacher_list_next_week
      difference — сырой список изменённых строк для update_changed_calendars()
    Если разницы нет — возвращает (None, [])."""
    logger.log('SQL', 'Search the differences in timetables...')
    try:
        last_db = get_latest_file(path='timetable-dbs/*.db')
        previous_db = sorted(iglob('timetable-dbs/*.db'), key=os.path.getmtime)[-2]
        logger.log('SQL', 'Previous timetable db is <' + previous_db + '>')
    except IndexError:
        logger.log('SQL', 'No previous sql-file. Skip file comparison for differences in timetables')
        return None, []
    # Подключение к базам данных расписания
    with _db_connection(last_db, row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        c.execute("ATTACH ? AS db2", (previous_db,))
        c.execute("SELECT * FROM main.timetable")
        current_rows = c.fetchall()
        c.execute("SELECT * FROM db2.timetable")
        previous_rows = c.fetchall()
        c.execute("DETACH DATABASE db2")

    def normalize_row(row):
        normalized = {}
        for key in row.keys():
            val = row[key]
            if isinstance(val, float) and val == int(val):
                normalized[key] = int(val)
            else:
                normalized[key] = val
        return normalized

    current_normalized_rows = [normalize_row(row) for row in current_rows]
    previous_normalized_rows = [normalize_row(row) for row in previous_rows]

    difference = []
    for curr_row in current_normalized_rows:
        if curr_row not in previous_normalized_rows:
            difference.append(curr_row)
    if not difference:
        logger.log('SQL', 'No differences in timetables')
        return None, []
    # Формирование списков изменений
    dates_current_week = [date_request(day_of_week=day, for_db='YES') for day in range(7)]
    dates_next_week = [date_request(day_of_week=day, for_db='YES', next='YES') for day in range(7)]
    group_list_current_week = []
    group_list_next_week = []
    teacher_list_current_week = []
    teacher_list_next_week = []
    for row in difference:
        row_name = get_row_value(row, 'Name')
        row_group = get_row_value(row, 'Group')
        row_date = get_row_value(row, 'Date')
        if str(row_date) in dates_current_week:
            if str(row_name) not in teacher_list_current_week:
                if str(timetable(teacher=str(row_name))) != str(timetable(teacher=str(row_name), use_previous_timetable_db='YES')):
                    teacher_list_current_week += [str(row_name)]
            if str(row_group) not in group_list_current_week:
                if str(timetable(group_id=str(row_group))) != str(timetable(group_id=str(row_group), use_previous_timetable_db='YES')):
                    group_list_current_week += [str(row_group)]
        elif str(row_date) in dates_next_week:
            if str(row_name) not in teacher_list_next_week:
                if str(timetable(teacher=str(row_name), next='YES')) != str(timetable(teacher=str(row_name), next='YES', use_previous_timetable_db='YES')):
                    teacher_list_next_week += [str(row_name)]
            if str(row_group) not in group_list_next_week:
                if str(timetable(group_id=str(row_group), next='YES')) != str(timetable(group_id=str(row_group), next='YES', use_previous_timetable_db='YES')):
                    group_list_next_week += [str(row_group)]
    return {
        'group_list_current_week': group_list_current_week,
        'group_list_next_week': group_list_next_week,
        'teacher_list_current_week': teacher_list_current_week,
        'teacher_list_next_week': teacher_list_next_week,
    }, difference


def getting_the_difference_in_sql_files_and_sending_them():
    """Обратно-совместимая обёртка: вычисляет разницу и рассылает уведомления."""
    event, difference = compute_timetable_differences()
    if event is None:
        return False
    update_changed_calendars(difference)
    logger.log('SQL', 'Got the differences. Trying to send them to users')
    kw = event
    if send_notifications_email(**kw) is True:
        logger.log('SQL', 'Successfully sent the differences by email')
    if send_notifications_vk_chat(**kw) is True:
        logger.log('SQL', 'Successfully sent the differences by vk_chat')
    if send_notifications_vk_user(**kw) is True:
        logger.log('SQL', 'Successfully sent the differences by vk_user')
    if send_notifications_telegram(**kw) is True:
        logger.log('SQL', 'Successfully sent the difference by telegram')


# ─── Поиск групп и преподавателей ───

def _build_saved_response(response_teacher, response_group, is_chat=False):
    """Формирует текст о уже сохранённых преподавателях/группах."""
    response = ''
    prefix = '' if is_chat else 'Для вас уже сохранены '
    teacher_label = 'Преподаватели уже сохранены: ' if is_chat else prefix + 'преподаватели: '
    group_label = 'Группы уже сохранены: ' if is_chat else prefix + 'группы: '
    if response_teacher:
        response += teacher_label + response_teacher
        if response_group:
            response += '\n'
    if response_group:
        response += group_label + response_group
    return response


def _build_added_response(existing_response, response_teacher, response_group):
    """Формирует текст о добавленных преподавателях/группах."""
    parts = []
    if response_teacher:
        parts.append('Добавлены преподаватели: ' + response_teacher)
    if response_group:
        parts.append('Добавлены группы: ' + response_group)
    added = '\n'.join(parts)
    if existing_response and added:
        return existing_response + '\n\n' + added
    return existing_response + added


def search_group_and_teacher_in_request(request: str, email: str = None, vk_id_chat: str = None,
                                         vk_id_user: str = None, telegram: str = None, discord: str = None):
    """
    Поступает запрос -> смотрим, существуют ли такие данные в бд расписания.
    Использует UPSERT для атомарного создания/обновления пользователя.
    """
    logger.log('SQL', 'Search request in groups and teachers...')
    if len(request) <= 2:
        logger.log('SQL', 'Request <= 2 symbols, skip')
        return False
    timetable_db = get_latest_file('timetable-dbs/*.db')
    if timetable_db is None:
        logger.error('Cant search groups and teachers in request because no timetable-db exists')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    _refresh_timetable_cache(timetable_db)
    with _timetable_cache_lock:
        cached_groups = _timetable_cache['groups'].copy()
        cached_teachers = _timetable_cache['teachers'].copy()
    matched_group = [g for g in cached_groups if request.find(g) != -1]
    matched_teacher = [t for t in cached_teachers if request.find(t) != -1]
    if matched_group or matched_teacher:
        ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
        if ctx is None:
            logger.error('Incorrect request to search groups and teachers')
            return False
        is_chat = ctx.platform == 'vk_chat'
        with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
            c = conn.cursor()
            # UPSERT: создаём пользователя если не существует
            c.execute(
                'INSERT INTO users (platform, platform_id, notification, lesson_time) VALUES (?, ?, 1, 1) '
                'ON CONFLICT(platform, platform_id) DO NOTHING',
                (ctx.platform, ctx.user_id))
            conn.commit()
            user_row = _get_user(c, ctx.platform, ctx.user_id)
            uid = user_row['id']
            # Определяем уже сохранённые и новые значения
            existing_teachers = set(_get_user_teachers(c, uid))
            existing_groups = set(_get_user_groups(c, uid))
            saved_teachers = [t for t in matched_teacher if t in existing_teachers]
            new_teachers = [t for t in matched_teacher if t not in existing_teachers]
            saved_groups = [g for g in matched_group if g in existing_groups]
            new_groups = [g for g in matched_group if g not in existing_groups]
            # Добавляем новые значения в junction-таблицы
            for t in new_teachers:
                c.execute('INSERT OR IGNORE INTO user_teachers (user_id, teacher) VALUES (?, ?)', (uid, t))
            for g in new_groups:
                c.execute('INSERT OR IGNORE INTO user_groups (user_id, group_id) VALUES (?, ?)', (uid, g))
        # Формируем ответ
        response = _build_saved_response(
            ' '.join(saved_teachers) if saved_teachers else '',
            ' '.join(saved_groups) if saved_groups else '',
            is_chat=is_chat)
        response = _build_added_response(
            response,
            ' '.join(new_teachers) if new_teachers else '',
            ' '.join(new_groups) if new_groups else '')
        logger.log('SQL', f'Added teachers: "{" ".join(new_teachers)}", groups: "{" ".join(new_groups)}" for {ctx.platform} <{ctx.user_id}>')
        return response
    else:
        logger.log('SQL', 'No recognized groups or teachers. Start search suggestions...')
        if len(request) > 6:
            request_mod = '%' + request[:-4] + '%'
        else:
            request_mod = '%' + request + '%'
        with _db_connection(timetable_db, row_factory=sqlite3.Row) as conn:
            c = conn.cursor()
            c.execute('SELECT DISTINCT "Group" FROM timetable WHERE "Group" LIKE ?', (request_mod,))
            records_group = c.fetchall()
            c.execute('SELECT DISTINCT "Name" FROM timetable WHERE "Name" LIKE ?', (request_mod,))
            records_teacher = c.fetchall()
        response = ''
        if records_group is not None:
            for row in records_group:
                if response.find(row["Group"]) == -1:
                    response += row["Group"] + '\n'
        if records_teacher is not None:
            for row in records_teacher:
                if response.find(row['Name']) == -1:
                    response += row['Name'] + '\n'
        if response:
            logger.log('SQL', 'Suggestions found for request')
            return 'Возможно вы имели ввиду:\n' + response
        else:
            logger.log('SQL', 'No suggestions found for request')
            return False


# ─── Настройки пользователя ───

def _toggle_setting(column: str, setting_name_gen: str, setting_name_nom: str,
                    enable: str = None, disable: str = None,
                    email: str = None, vk_id_chat: str = None, vk_id_user: str = None,
                    telegram: str = None, discord: str = None):
    """Generic helper для включения/отключения notification или lesson_time."""
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error(f'Incorrect request to toggle {column}. No platform specified')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    logger.log('SQL', f'Incoming request to toggle {column} for {ctx.platform} = <{ctx.user_id}>')
    with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        row = _get_user(c, ctx.platform, ctx.user_id)
        if row:
            if enable is not None and row[column] == 1:
                return f'{setting_name_nom} уже включены' if column == 'notification' else 'Отображение времени занятий уже включено'
            elif disable is not None and row[column] == 0:
                return f'{setting_name_nom} уже отключены' if column == 'notification' else 'Отображение времени занятий уже отключено'
            elif enable is not None:
                c.execute('UPDATE users SET {} = 1 WHERE id = ?'.format(column), (row['id'],))
                logger.log('SQL', f'{column} for {ctx.platform} <{ctx.user_id}> enabled')
                return f'{setting_name_nom} успешно включены' if column == 'notification' else 'Отображение времени занятий успешно включено'
            elif disable is not None:
                c.execute('UPDATE users SET {} = 0 WHERE id = ?'.format(column), (row['id'],))
                logger.log('SQL', f'{column} for {ctx.platform} <{ctx.user_id}> disabled')
                return f'{setting_name_nom} успешно отключены' if column == 'notification' else 'Отображение времени занятий успешно отключено'
            else:
                logger.error(f'Incorrect request to toggle {column} for {ctx.platform} <{ctx.user_id}>. enable={enable}, disable={disable}')
                return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
        else:
            logger.log('SQL', f'No values found for {ctx.platform} <{ctx.user_id}>. Skip toggle {column}')
            return f'Невозможно изменить настройки {setting_name_gen}, так как для вас не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'


def enable_and_disable_notifications(enable: str = None, disable: str = None, email: str = None,
                                      vk_id_chat: str = None, vk_id_user: str = None,
                                      telegram: str = None, discord: str = None):
    return _toggle_setting('notification', 'уведомлений', 'Уведомления', enable=enable, disable=disable,
                           email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)


def enable_and_disable_lesson_time(enable: str = None, disable: str = None, email: str = None,
                                    vk_id_chat: str = None, vk_id_user: str = None,
                                    telegram: str = None, discord: str = None):
    return _toggle_setting('lesson_time', 'отображения времени занятий', 'Отображение времени занятий', enable=enable, disable=disable,
                           email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)


def delete_all_saved_groups_and_teachers(email: str = None, vk_id_chat: str = None,
                                          vk_id_user: str = None, telegram: str = None, discord: str = None):
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error('Incorrect request to delete saved groups and teachers. No platform specified')
        return 'Невозможно удалить, так как для вас нет сохраненых параметров. Добавьте сначала группу или преподавателя'
    logger.log('SQL', f'Incoming request to delete all saved groups and teachers for {ctx.platform} = <{ctx.user_id}>')
    with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        user = _get_user(c, ctx.platform, ctx.user_id)
        if user:
            uid = user['id']
            teachers = _get_user_teachers(c, uid)
            groups = _get_user_groups(c, uid)
            if teachers or groups:
                c.execute('DELETE FROM user_teachers WHERE user_id = ?', (uid,))
                c.execute('DELETE FROM user_groups WHERE user_id = ?', (uid,))
                logger.log('SQL', f'All saved groups and teachers for {ctx.platform} <{ctx.user_id}> are deleted')
                return 'Сохраненные группы и преподаватели успешно удалены'
            else:
                logger.log('SQL', f'No saved groups or teachers for {ctx.platform} <{ctx.user_id}>')
                return 'Нет сохраненных групп или преподавателей для удаления'
        else:
            logger.log('SQL', f'No saved settings for {ctx.platform} <{ctx.user_id}>')
            return 'Невозможно удалить, так как для вас нет сохраненых параметров. Добавьте сначала группу или преподавателя'


def display_saved_settings(email: str = None, vk_id_chat: str = None,
                            vk_id_user: str = None, telegram: str = None, discord: str = None):
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error('Incorrect request to display saved settings. No platform specified')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    logger.log('SQL', f'Incoming request to display all saved settings for {ctx.platform} = <{ctx.user_id}>')
    with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        user = _get_user(c, ctx.platform, ctx.user_id)
        if user is not None:
            groups = _get_user_groups(c, user['id'])
            teachers = _get_user_teachers(c, user['id'])
            notification = user['notification']
            lesson_time = user['lesson_time']
        else:
            logger.log('SQL', f'No saved settings for {ctx.platform} <{ctx.user_id}>')
            return 'Для вас нет сохраненных параметров'
    answer = ''
    if not groups and not teachers:
        answer += 'Нет сохраненных групп и преподавателей\n'
    if groups:
        answer += 'Сохранены группы: ' + ' '.join(groups) + '\n'
    if teachers:
        answer += 'Сохранены преподаватели: ' + ' '.join(teachers) + '\n'
    if notification == 1:
        answer += 'Уведомления включены\n'
    elif notification == 0:
        answer += 'Уведомления отключены\n'
    if lesson_time == 1:
        answer += 'Отображение времени занятий включено'
    elif lesson_time == 0:
        answer += 'Отображение времени занятий отключено'
    logger.log('SQL', f'Display saved settings for {ctx.platform} <{ctx.user_id}>')
    return answer


# ─── Получение расписания / нагрузки ───

def getting_timetable_for_user(next: str = None, email: str = None, vk_id_chat: str = None,
                                vk_id_user: str = None, telegram: str = None, discord: str = None):
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error('Incorrect timetable request. No platform specified')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    logger.log('SQL', f'Incoming timetable request for {ctx.platform} = <{ctx.user_id}>')
    with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        user = _get_user(c, ctx.platform, ctx.user_id)
        if user is not None:
            teachers = _get_user_teachers(c, user['id'])
            groups = _get_user_groups(c, user['id'])
            user_lesson_time = user['lesson_time']
        else:
            logger.log('SQL', f'No saved groups or teachers for {ctx.platform} <{ctx.user_id}>')
            return 'Нет сохраненных групп или преподавателей для отправки расписания'
    lesson_time = None
    if user_lesson_time == 0:
        lesson_time = 'NO'
    if not groups and not teachers:
        logger.log('SQL', f'No saved groups or teachers for {ctx.platform} <{ctx.user_id}>')
        return 'Нет сохраненных групп или преподавателей для отправки расписания'
    separator = '' if ctx.platform == 'email' else MESSAGE_SPLIT_SENTINEL
    teachers_answer = ''
    groups_answer = ''
    for t in teachers:
        teachers_answer += separator + timetable(teacher=str(t), next=next, lesson_time=lesson_time) + '\n'
    for g in groups:
        groups_answer += separator + timetable(group_id=str(g), next=next, lesson_time=lesson_time) + '\n'
    logger.log('SQL', f'Response to timetable request for {ctx.platform} <{ctx.user_id}>')
    result = teachers_answer + groups_answer
    if ctx.platform == 'email':
        return format_timetable_html(result)
    return result


def getting_workload_for_user(next: str = None, email: str = None, vk_id_chat: str = None,
                               vk_id_user: str = None, telegram: str = None, discord: str = None):
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error('Incorrect workload request. No platform specified')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    logger.log('SQL', f'Incoming workload request for {ctx.platform} = <{ctx.user_id}>')
    with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        user = _get_user(c, ctx.platform, ctx.user_id)
        if user is not None:
            teachers = _get_user_teachers(c, user['id'])
        else:
            logger.log('SQL', f'No saved teachers for {ctx.platform} <{ctx.user_id}>')
            return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
    if not teachers:
        logger.log('SQL', f'No saved teachers for {ctx.platform} <{ctx.user_id}>')
        return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
    separator = '' if ctx.platform == 'email' else MESSAGE_SPLIT_SENTINEL
    teachers_answer = ''
    for t in teachers:
        teachers_answer += separator + workload(teacher=str(t), next=next) + '\n'
    logger.log('SQL', f'Response to workload request for {ctx.platform} <{ctx.user_id}>')
    return teachers_answer


def getting_workload_excel_for_user(next: str = None, email: str = None, vk_id_chat: str = None,
                                     vk_id_user: str = None, telegram: str = None, discord: str = None):
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error('Incorrect workload excel request. No platform specified')
        return []
    logger.log('SQL', f'Incoming workload excel request for {ctx.platform} = <{ctx.user_id}>')
    with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        user = _get_user(c, ctx.platform, ctx.user_id)
        if user is None:
            logger.log('SQL', f'No saved settings for {ctx.platform} <{ctx.user_id}>')
            return []
        teachers = _get_user_teachers(c, user['id'])
        groups = _get_user_groups(c, user['id'])
    files = []
    for t in teachers:
        result = create_excel_with_workload(teacher=str(t), next=next)
        if result.endswith('.xlsx'):
            files.append(result)
    for g in groups:
        result = create_excel_with_workload(group_id=str(g), next=next)
        if result.endswith('.xlsx'):
            files.append(result)
    logger.log('SQL', f'Generated {len(files)} workload excel files for {ctx.platform} <{ctx.user_id}>')
    return files


def get_all_months_from_timetable_db():
    """Возвращает отсортированный список кортежей (месяц, год) всех доступных месяцев из БД расписания."""
    db_timetable = get_latest_file(GLOB_TIMETABLE_DB)
    if db_timetable is None:
        return []
    with _db_connection(db_timetable) as conn:
        c = conn.cursor()
        rows = c.execute('SELECT DISTINCT "Date" FROM timetable').fetchall()
    months = set()
    for row in rows:
        date_str = row[0]
        if not date_str:
            continue
        parts = date_str.split('-')
        if len(parts) == 3:
            try:
                month = int(parts[1])
                year = int(parts[2])
                months.add((month, year))
            except ValueError:
                continue
    return sorted(months, key=lambda x: (x[1], x[0]))


def getting_workload_excel_all_months_for_user(email: str = None, vk_id_chat: str = None,
                                                vk_id_user: str = None, telegram: str = None):
    """Генерирует Excel-файл нагрузки за все доступные месяцы."""
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram)
    if ctx is None:
        logger.error('Incorrect workload excel all months request. No platform specified')
        return []
    logger.log('SQL', f'Incoming workload excel all months request for {ctx.platform} = <{ctx.user_id}>')
    with _db_connection('user_settings.db', row_factory=sqlite3.Row) as conn:
        c = conn.cursor()
        user = _get_user(c, ctx.platform, ctx.user_id)
        if user is None:
            logger.log('SQL', f'No saved settings for {ctx.platform} <{ctx.user_id}>')
            return []
        teachers = _get_user_teachers(c, user['id'])
        groups = _get_user_groups(c, user['id'])
    all_months = get_all_months_from_timetable_db()
    if not all_months:
        return []
    files = []
    for t in teachers:
        result = create_excel_with_workload_all_months(teacher=str(t), all_months=all_months)
        if result.endswith('.xlsx'):
            files.append(result)
    for g in groups:
        result = create_excel_with_workload_all_months(group_id=str(g), all_months=all_months)
        if result.endswith('.xlsx'):
            files.append(result)
    logger.log('SQL', f'Generated {len(files)} all-months workload excel file(s) for {ctx.platform} <{ctx.user_id}>')
    return files
