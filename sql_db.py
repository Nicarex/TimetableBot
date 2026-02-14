import asyncio
import os
import platform
import random
import sqlite3
from glob import iglob
from pathlib import Path

from vkbottle import API

from calendar_timetable import create_calendar_file_with_timetable, download_calendar_file_to_github
from constants import MESSAGE_PREFIX, MESSAGE_SPLIT_SENTINEL
from logger import logger
from other import read_config, get_latest_file, connection_to_sql, sendMail, get_row_value, format_timetable_html
from timetable import date_request, timetable, workload
from platform_context import resolve_platform

# Инициализация
vk_token = read_config(vk='YES')
tg_token = read_config(telegram='YES')
ds_token = read_config(discord='YES')


# В Windows asyncio есть баг, это исправление
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def write_msg_vk_chat(message: str, chat_id: str):
    logger.log('SQL', f'Try to send message to vk chat <{str(chat_id)}>')
    api = API(vk_token)
    try:
        chat_id = int(chat_id)
        # For community (group) tokens, sending to conversations requires using peer_id = 2000000000 + chat_id
        # If chat_id already looks like a peer_id (>2e9), use it directly.
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


async def write_msg_vk_user(message: str, user_id: str):
    logger.log('SQL', f'Try to send message to vk user <{str(user_id)}>')
    api = API(vk_token)
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


async def write_msg_telegram(message: str, tg_id):
    logger.log('SQL', f'Try to send message to telegram <{str(tg_id)}>')
    from aiogram import Bot
    import re
    bot = Bot(token=tg_token)
    # Helper to extract new supergroup id from error text
    def _extract_new_supergroup_id(text: str):
        if not text:
            return None
        # Try common phrasings that Telegram returns when a group was migrated
        m = re.search(r'migrated to a supergroup with id\s+(-?\d+)', text)
        if m:
            return m.group(1)
        m = re.search(r'supergroup with id\s+(-?\d+)', text)
        if m:
            return m.group(1)
        # Fallback: look for -100... style ids
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
            # If chat was migrated to supergroup - update DB and retry
            if new_id is not None:
                logger.log('SQL', f'Telegram chat {single_id} was migrated to supergroup {new_id}, updating DB and retrying')
                # Try to update stored id in user_settings.db
                try:
                    conn = connection_to_sql('user_settings.db')
                    cur = conn.cursor()
                    cur.execute('UPDATE telegram SET telegram_id = ? WHERE telegram_id = ?', (str(new_id), str(single_id)))
                    conn.commit()
                    cur.close()
                    conn.close()
                    logger.log('SQL', f'Updated telegram_id in DB: {single_id} -> {new_id}')
                except Exception as db_e:
                    logger.log('SQL', f'Failed to update telegram_id in DB for {single_id}: {db_e}')
                # Retry sending to the new id
                try:
                    await bot.send_message(chat_id=int(new_id), text=MESSAGE_PREFIX + message)
                    logger.log('SQL', f'Message have been sent to telegram <{str(new_id)}>)')
                    return True
                except Exception as e2:
                    logger.log('SQL', f'Error happened while sending message to migrated telegram id <{str(new_id)}>: {e2}')
                    return False
            else:
                # Detect when bot was blocked, user was deactivated or similar forbidden errors
                lower_err = err_text.lower() if err_text else ''
                # Treat these cases as permanent/unrecoverable for this chat/user and disable notifications
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
                        cur.execute('UPDATE telegram SET notification = ? WHERE telegram_id = ?', (0, str(single_id)))
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
        # Support passing a list of ids or a single id
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


# Создание пользовательской базы данных
def create_db_user_settings():
    path = 'dbs/user_settings.db'
    if Path(path).is_file():
        return True
    # Таблица для почты
    conn = connection_to_sql(name=path)
    if conn is None:
        logger.error(f'Не удалось создать или открыть базу данных {path}. Проверьте наличие файла и права доступа.')
        return False
    try:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS email(
                    email           TEXT,
                    group_id        TEXT,
                    teacher         TEXT,
                    notification    INTEGER,
                    lesson_time     INTEGER);
                    """)

        # Таблица для ВК пользователей
        conn.execute("""CREATE TABLE IF NOT EXISTS vk_user (
                    vk_id           TEXT,
                    group_id        TEXT,
                    teacher         TEXT,
                    notification    INTEGER,
                    lesson_time     INTEGER);
                    """)

        # Таблица для ВК чатов
        conn.execute("""CREATE TABLE IF NOT EXISTS vk_chat (
                    vk_id           TEXT,
                    group_id        TEXT,
                    teacher         TEXT,
                    notification    INTEGER,
                    lesson_time     INTEGER);
                    """)

        # Таблица для telegram
        conn.execute("""CREATE TABLE IF NOT EXISTS telegram (
                    telegram_id     TEXT,
                    group_id        TEXT,
                    teacher         TEXT,
                    notification    INTEGER,
                    lesson_time     INTEGER);
                    """)

        # Таблица для discord
        conn.execute("""CREATE TABLE IF NOT EXISTS discord (
                        discord_id      TEXT,
                        group_id        TEXT,
                        teacher         TEXT,
                        notification    INTEGER,
                        lesson_time     INTEGER);
                        """)

        conn.commit()  # Сохранение изменений
        c.close()
        conn.close()  # Закрытие подключения
        logger.log('SQL', 'User database has been created')
    except Exception as e:
        logger.error(f'Ошибка при создании таблиц в базе данных {path}: {e}')
        if conn:
            conn.close()
        return False


# Создание базы данных календарей
def create_db_calendars_list():
    path = 'dbs/calendars_list.db'
    # Если файл существует, то True
    if Path(path).is_file():
        return True
    conn = connection_to_sql(name=path)
    if conn is None:
        logger.error(f'Не удалось создать или открыть базу данных {path}. Проверьте наличие файла и права доступа.')
        return False
    try:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS calendars(
                    group_id        TEXT,
                    teacher         TEXT,
                    calendar_url    TEXT);
                    """)
        conn.commit()  # Сохранение изменений
        c.close()
        conn.close()  # Закрытие подключения
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


# Отправляет письмо на почту о том, что расписание изменилось
def send_notifications_email(group_list_current_week: list, group_list_next_week: list, teacher_list_current_week: list, teacher_list_next_week: list):
    """
    Берем по одному пользователю из бд с email, и смотрим, есть ли у него совпадение с кем-то из списков
    Если есть, то отправляем письмо, что расписание изменилось для такой-то группы или преподавателя
    """
    # Подключение к пользовательской базе данных
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    email_users = c.execute('SELECT * FROM email WHERE notification = 1').fetchall()
    c.close()
    conn.close()
    for user in email_users:
        answer = ''
        if teacher_list_current_week:
            for item in teacher_list_current_week:
                if str(item) in str(user['teacher']):
                    answer += f'Расписание на текущую неделю для преподавателя {item} было изменено\n'
                    if user['lesson_time'] == 1:
                        answer += timetable(teacher=item) + '\n\n'
                    else:
                        answer += timetable(teacher=item, lesson_time='YES') + '\n\n'
        if teacher_list_next_week:
            for item in teacher_list_next_week:
                if str(item) in str(user['teacher']):
                    answer += f'Расписание на следующую неделю для преподавателя {item} было изменено\n'
                    if user['lesson_time'] == 1:
                        answer += timetable(teacher=item, next='YES') + '\n\n'
                    else:
                        answer += timetable(teacher=item, lesson_time='YES', next='YES') + '\n\n'
        if group_list_current_week:
            for item in group_list_current_week:
                if str(item) in str(user['group_id']):
                    answer += f'Расписание на текущую неделю для группы {item} было изменено\n'
                    if user['lesson_time'] == 1:
                        answer += timetable(group_id=item) + '\n\n'
                    else:
                        answer += timetable(group_id=item, lesson_time='YES') + '\n\n'
        if group_list_next_week:
            for item in group_list_next_week:
                if str(item) in str(user['group_id']):
                    answer += f'Расписание на следующую неделю для группы {item} было изменено\n'
                    if user['lesson_time'] == 1:
                        answer += timetable(group_id=item, next='YES') + '\n\n'
                    else:
                        answer += timetable(group_id=item, lesson_time='YES', next='YES') + '\n\n'
        if answer != '':
            html_answer = format_timetable_html(answer)
            sendMail(to_email=user['email'], subject='Изменения в расписании', text='', html=html_answer)
    return True


def _collect_notification_messages(user, group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week, id_column):
    """Собирает список сообщений для рассылки уведомлений VK пользователю/чату."""
    messages = []
    user_id = user[id_column]
    for label, items_list, is_next, field in [
        ('текущую', teacher_list_current_week, False, 'teacher'),
        ('следующую', teacher_list_next_week, True, 'teacher'),
        ('текущую', group_list_current_week, False, 'group_id'),
        ('следующую', group_list_next_week, True, 'group_id'),
    ]:
        if not items_list or user[field] is None:
            continue
        entity_type = 'преподавателя' if field == 'teacher' else 'группы'
        for item in items_list:
            if str(item) in str(user[field]):
                messages.append((f'Изменения в расписании на {label} неделю для {entity_type} {item}', user_id))
                kw = {'teacher': item} if field == 'teacher' else {'group_id': item}
                if is_next:
                    kw['next'] = 'YES'
                if user['lesson_time'] != 1:
                    kw['lesson_time'] = 'YES'
                messages.append((timetable(**kw), user_id))
    return messages


async def _send_notifications_vk_async(table, id_column, send_fn, log_label, group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week):
    """Общая асинхронная рассылка уведомлений VK (для чатов и пользователей)."""
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    vk_users = c.execute(f'SELECT * FROM {table} WHERE notification = 1').fetchall()
    c.close()
    conn.close()
    for user in vk_users:
        messages = _collect_notification_messages(
            user, group_list_current_week, group_list_next_week,
            teacher_list_current_week, teacher_list_next_week, id_column)
        for msg, uid in messages:
            logger.log('SQL', f'Попытка отправки сообщения {log_label}: {id_column}={uid}')
            try:
                result = await send_fn(msg, uid)
                logger.log('SQL', f'Результат отправки {log_label} {id_column}={uid}: {result}')
            except Exception as e:
                logger.log('SQL', f'Ошибка при отправке {log_label} {id_column}={uid}: {e}')
            await asyncio.sleep(0.4)
    return True


def send_notifications_vk_chat(group_list_current_week: list, group_list_next_week: list, teacher_list_current_week: list, teacher_list_next_week: list):
    return asyncio.run(_send_notifications_vk_async(
        'vk_chat', 'vk_id', write_msg_vk_chat, 'VK чату',
        group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week))


def send_notifications_vk_user(group_list_current_week: list, group_list_next_week: list, teacher_list_current_week: list, teacher_list_next_week: list):
    return asyncio.run(_send_notifications_vk_async(
        'vk_user', 'vk_id', write_msg_vk_user, 'VK пользователю',
        group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week))

async def _send_notifications_telegram_async(group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week):
    """Асинхронная рассылка уведомлений в Telegram."""
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    users = c.execute('SELECT * FROM telegram WHERE notification = 1').fetchall()
    c.close()
    conn.close()
    for user in users:
        messages = []
        tg_id = user['telegram_id']
        for label, items_list, is_next in [
            ('текущую', teacher_list_current_week, False),
            ('следующую', teacher_list_next_week, True),
        ]:
            if items_list and user['teacher'] is not None:
                for item in items_list:
                    if str(item) in str(user['teacher']):
                        messages.append(f'Изменения в расписании на {label} неделю для преподавателя {item}')
                        kw = {'teacher': item}
                        if is_next:
                            kw['next'] = 'YES'
                        if user['lesson_time'] != 1:
                            kw['lesson_time'] = 'YES'
                        messages.append(timetable(**kw))
        for label, items_list, is_next in [
            ('текущую', group_list_current_week, False),
            ('следующую', group_list_next_week, True),
        ]:
            if items_list and user['group_id'] is not None:
                for item in items_list:
                    if str(item) in str(user['group_id']):
                        messages.append(f'Изменения в расписании на {label} неделю для группы {item}')
                        kw = {'group_id': item}
                        if is_next:
                            kw['next'] = 'YES'
                        if user['lesson_time'] != 1:
                            kw['lesson_time'] = 'YES'
                        messages.append(timetable(**kw))
        for msg in messages:
            await write_msg_telegram(message=msg, tg_id=tg_id)
    return True


def send_notifications_telegram(group_list_current_week: list, group_list_next_week: list, teacher_list_current_week: list, teacher_list_next_week: list):
    """Обёртка для вызова асинхронной рассылки в Telegram."""
    return asyncio.run(_send_notifications_telegram_async(
        group_list_current_week, group_list_next_week,
        teacher_list_current_week, teacher_list_next_week))


# Получает разницу в двух sql-файлах расписания для отправки разницы пользователям
def getting_the_difference_in_sql_files_and_sending_them():
    """
    Ищет разницу между последним и прошлым расписанием
    Если разница есть, то уведомляет об этом пользователя и отправляет новое расписание
    Если нет, то возвращает False

    Нужно учесть при использовании, что функция не должна быть False
    """
    logger.log('SQL', 'Search the differences in timetables...')
    try:
        # Последняя база данных
        last_db = get_latest_file(path='timetable-dbs/*.db')
        # Предпоследняя база данных
        previous_db = sorted(iglob('timetable-dbs/*.db'), key=os.path.getmtime)[-2]
        logger.log('SQL', 'Previous timetable db is <' + previous_db + '>')
    except IndexError:
        logger.log('SQL', 'No previous sql-file. Skip file comparison for differences in timetables')
        return False
    # Подключение к базам данных расписания
    conn = connection_to_sql(last_db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("ATTACH ? AS db2", (previous_db,))
    
    # Получаем все строки из обеих таблиц
    c.execute("SELECT * FROM main.timetable")
    current_rows = c.fetchall()
    c.execute("SELECT * FROM db2.timetable")
    previous_rows = c.fetchall()
    c.close()
    conn.close()
    
    # Функция для нормализации строки (приведение всех числовых значений к одному типу)
    def normalize_row(row):
        """Приводит числовые значения к целым числам для консистентного сравнения"""
        normalized = {}
        for key in row.keys():
            val = row[key]
            # Если значение число (int или float), приводим к int если возможно
            if isinstance(val, float) and val == int(val):
                normalized[key] = int(val)
            else:
                normalized[key] = val
        return normalized
    
    # Нормализуем каждую строку
    current_normalized_rows = [normalize_row(row) for row in current_rows]
    previous_normalized_rows = [normalize_row(row) for row in previous_rows]
    
    # Находим разницу, сравнивая как словари
    difference = []
    for curr_row in current_normalized_rows:
        if curr_row not in previous_normalized_rows:
            difference.append(curr_row)
    if not difference:
        logger.log('SQL', 'No differences in timetables')
        return False
    # Календарь
    # Обновление расписания в календарях
    list_with_teachers = []
    list_with_groups = []
    # Подключение к бд
    conn = connection_to_sql(name='calendars_list.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    for row in difference:
        # Добавление в список, чтобы повторно не обрабатывать
        row_name = get_row_value(row, 'Name')
        row_group = get_row_value(row, 'Group')
        if not str(row_name) in list_with_teachers:
            list_with_teachers += [str(row_name)]
            # Если календарь существует для этого преподавателя
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
    # Отправка разницы в ВК и почту
    # Создание списков с датами на текущую и следующую недели для дальнейшего фильтра бд по ним
    dates_current_week = []
    for day in range(0, 7):
        dates_current_week += [date_request(day_of_week=day, for_db='YES')]
    dates_next_week = []
    for day in range(0, 7):
        dates_next_week += [date_request(day_of_week=day, for_db='YES', next='YES')]
    # Списки с группами и преподавателями, у которых есть изменения в расписании на текущую и следующую недели
    group_list_current_week = []
    group_list_next_week = []
    teacher_list_current_week = []
    teacher_list_next_week = []
    # Фильтрация значений из бд и распределение их по спискам
    # Для каждого походящего значения создаем расписание с текущей бд расписания
    # и сравниваем его с расписанием созданным с предыдущей бд расписания
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
    logger.log('SQL', 'Got the differences. Trying to send them to users')
    if send_notifications_email(group_list_current_week=group_list_current_week, group_list_next_week=group_list_next_week, teacher_list_current_week=teacher_list_current_week, teacher_list_next_week=teacher_list_next_week) is True:
        logger.log('SQL', 'Successfully sent the differences by email')
    if send_notifications_vk_chat(group_list_current_week=group_list_current_week, group_list_next_week=group_list_next_week, teacher_list_current_week=teacher_list_current_week, teacher_list_next_week=teacher_list_next_week) is True:
        logger.log('SQL', 'Successfully sent the differences by vk_chat')
    if send_notifications_vk_user(group_list_current_week=group_list_current_week, group_list_next_week=group_list_next_week, teacher_list_current_week=teacher_list_current_week, teacher_list_next_week=teacher_list_next_week) is True:
        logger.log('SQL', 'Successfully sent the differences by vk_user')
    if send_notifications_telegram(group_list_current_week=group_list_current_week, group_list_next_week=group_list_next_week, teacher_list_current_week=teacher_list_current_week, teacher_list_next_week=teacher_list_next_week) is True:
        logger.log('SQL', 'Successfully sent the difference by telegram')


# Поиск групп и преподавателей в запросе, и добавление их в пользовательскую бд
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


def _find_already_saved(matched_items, saved_value):
    """Находит элементы из matched_items, которые уже есть в saved_value."""
    result = ''
    if matched_items and saved_value is not None:
        for item in matched_items:
            if str(saved_value).find(str(item)) != -1:
                result += item + ' '
    return result


def _update_column_values(cursor, table, column, id_column, user_id, matched_items, saved_value):
    """Добавляет новые значения в столбец, возвращает строку добавленных."""
    response = ''
    for item in matched_items:
        if str(saved_value).find(str(item)) == -1:
            current_value = cursor.execute(
                f'SELECT * FROM {table} WHERE {id_column} = ?', (user_id,)
            ).fetchone()[column]
            if current_value is not None:
                cursor.execute(
                    f'UPDATE {table} SET {column} = ? WHERE {id_column} = ?',
                    (current_value + '\n' + item, user_id))
                response += ' ' + item
            else:
                cursor.execute(
                    f'UPDATE {table} SET {column} = ? WHERE {id_column} = ?',
                    (item, user_id))
                response += item
    return response


def _prepare_insert_values(matched_items):
    """Подготавливает значения для INSERT: (db_value, display_value)."""
    if not matched_items:
        return None, ''
    insert_val = '\n'.join(matched_items)
    display_val = ' '.join(matched_items)
    return insert_val, display_val


def search_group_and_teacher_in_request(request: str, email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    """
    Поступает запрос -> смотрим, существуют ли такие данные в бд расписания
    есть - добавляем в базу данных пользователя, нет - ищем возможные совпадения из бд расписания ->
    -> совпадения есть - отправляем пользователю возможные варианты, нет - отправляем False
    """
    logger.log('SQL', 'Search request in groups and teachers...')
    if len(request) <= 2:
        logger.log('SQL', 'Request <= 2 symbols, skip')
        return False
    timetable_db = get_latest_file('timetable-dbs/*.db')
    if timetable_db is None:
        logger.error('Cant search groups and teachers in request because no timetable-db exists')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    conn = connection_to_sql(timetable_db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM timetable')
    timetable_rows = c.fetchall()
    # Ищет группы и преподавателей для переданного запроса
    matched_group = []
    matched_teacher = []
    for row in timetable_rows:
        name = str(row['Name'])
        group = str(row['Group'])
        if request.find(name) != -1 and name not in matched_teacher and name != ' ':
            matched_teacher.append(name)
        if request.find(group) != -1 and group not in matched_group:
            matched_group.append(group)
    # Если есть хоть одна распознанная группа или преподаватель
    if matched_group or matched_teacher:
        c.close()
        conn.close()
        ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
        if ctx is None:
            logger.error('Incorrect request to search groups and teachers')
            return False
        is_chat = ctx.name == 'vk_chat'
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(f'SELECT * FROM {ctx.table} WHERE {ctx.id_column} = ?', (ctx.user_id,))
        user_row = c.fetchone()
        if user_row:
            # Поиск значений, которые уже есть в базе данных
            saved_teachers = _find_already_saved(matched_teacher, user_row['teacher'])
            saved_groups = _find_already_saved(matched_group, user_row['group_id'])
            response = _build_saved_response(saved_teachers, saved_groups, is_chat=is_chat)
            # Добавление новых значений
            added_teachers = _update_column_values(
                c, ctx.table, 'teacher', ctx.id_column, ctx.user_id,
                matched_teacher, user_row['teacher'])
            added_groups = _update_column_values(
                c, ctx.table, 'group_id', ctx.id_column, ctx.user_id,
                matched_group, user_row['group_id'])
            conn.commit()
            c.close()
            conn.close()
            response = _build_added_response(response, added_teachers, added_groups)
            logger.log('SQL', f'Added values teachers: "{added_teachers}", groups: "{added_groups}" for {ctx.name} <{ctx.user_id}>')
        else:
            # Новая запись
            logger.log('SQL', f'No values found for {ctx.name} <{ctx.user_id}>. Create new entry...')
            insert_teacher, response_teacher = _prepare_insert_values(matched_teacher)
            insert_group, response_group = _prepare_insert_values(matched_group)
            c.execute(
                f'INSERT INTO {ctx.table} ({ctx.id_column}, group_id, teacher, notification, lesson_time) VALUES (?, ?, ?, 1, 1)',
                (ctx.user_id, insert_group, insert_teacher))
            conn.commit()
            c.close()
            conn.close()
            response = _build_added_response('', response_teacher, response_group)
            logger.log('SQL', f'Added values teachers: "{response_teacher}", groups: "{response_group}" for {ctx.name} <{ctx.user_id}>')
        return response
    # Если ничего не распознано, то ищем возможные варианты
    else:
        logger.log('SQL', 'No recognized groups or teachers. Start search suggestions...')
        if len(request) > 6:
            request_mod = '%' + request[:-4] + '%'
        else:
            request_mod = '%' + request + '%'
        c.execute('SELECT * FROM timetable WHERE "Group" LIKE ?', (request_mod,))
        records_group = c.fetchall()
        c.execute('SELECT * FROM timetable WHERE "Name" LIKE ?', (request_mod,))
        records_teacher = c.fetchall()
        c.close()
        conn.close()
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


# Включение и отключение уведомлений об изменениях
def _toggle_setting(column: str, setting_name_gen: str, setting_name_nom: str,
                    enable: str = None, disable: str = None,
                    email: str = None, vk_id_chat: str = None, vk_id_user: str = None,
                    telegram: str = None, discord: str = None):
    """Generic helper для включения/отключения notification или lesson_time."""
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error(f'Incorrect request to toggle {column}. No platform specified')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    logger.log('SQL', f'Incoming request to toggle {column} for {ctx.name} = <{ctx.user_id}>')
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f'SELECT * FROM {ctx.table} WHERE {ctx.id_column} = ?', (ctx.user_id,))
    row = c.fetchone()
    if row:
        if enable is not None and row[column] == 1:
            c.close()
            conn.close()
            return f'{setting_name_nom} уже включены' if column == 'notification' else 'Отображение времени занятий уже включено'
        elif disable is not None and row[column] == 0:
            c.close()
            conn.close()
            return f'{setting_name_nom} уже отключены' if column == 'notification' else 'Отображение времени занятий уже отключено'
        elif enable is not None:
            c.execute(f'UPDATE {ctx.table} SET {column} = ? WHERE {ctx.id_column} = ?', (1, ctx.user_id))
            conn.commit()
            c.close()
            conn.close()
            logger.log('SQL', f'{column} for {ctx.name} <{ctx.user_id}> enabled')
            return f'{setting_name_nom} успешно включены' if column == 'notification' else 'Отображение времени занятий успешно включено'
        elif disable is not None:
            c.execute(f'UPDATE {ctx.table} SET {column} = ? WHERE {ctx.id_column} = ?', (0, ctx.user_id))
            conn.commit()
            c.close()
            conn.close()
            logger.log('SQL', f'{column} for {ctx.name} <{ctx.user_id}> disabled')
            return f'{setting_name_nom} успешно отключены' if column == 'notification' else 'Отображение времени занятий успешно отключено'
        else:
            c.close()
            conn.close()
            logger.error(f'Incorrect request to toggle {column} for {ctx.name} <{ctx.user_id}>. enable={enable}, disable={disable}')
            return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    else:
        c.close()
        conn.close()
        logger.log('SQL', f'No values found for {ctx.name} <{ctx.user_id}>. Skip toggle {column}')
        return f'Невозможно изменить настройки {setting_name_gen}, так как для вас не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'


def enable_and_disable_notifications(enable: str = None, disable: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    return _toggle_setting('notification', 'уведомлений', 'Уведомления', enable=enable, disable=disable,
                           email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)


# Включение и отключение отображения времени занятий в расписании
def enable_and_disable_lesson_time(enable: str = None, disable: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    return _toggle_setting('lesson_time', 'отображения времени занятий', 'Отображение времени занятий', enable=enable, disable=disable,
                           email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)


# Удаление сохраненных настроек групп и преподов для пользователей
def delete_all_saved_groups_and_teachers(email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error('Incorrect request to delete saved groups and teachers. No platform specified')
        return 'Невозможно удалить, так как для вас нет сохраненых параметров. Добавьте сначала группу или преподавателя'
    logger.log('SQL', f'Incoming request to delete all saved groups and teachers for {ctx.name} = <{ctx.user_id}>')
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f'SELECT * FROM {ctx.table} WHERE {ctx.id_column} = ?', (ctx.user_id,))
    result = c.fetchone()
    if result:
        if result['group_id'] is not None or result['teacher'] is not None:
            c.execute(f'UPDATE {ctx.table} SET group_id = ? WHERE {ctx.id_column} = ?', (None, ctx.user_id))
            c.execute(f'UPDATE {ctx.table} SET teacher = ? WHERE {ctx.id_column} = ?', (None, ctx.user_id))
            conn.commit()
            c.close()
            conn.close()
            logger.log('SQL', f'All saved groups and teachers for {ctx.name} <{ctx.user_id}> are deleted')
            return 'Сохраненные группы и преподаватели успешно удалены'
        else:
            c.close()
            conn.close()
            logger.log('SQL', f'No saved groups or teachers for {ctx.name} <{ctx.user_id}>')
            return 'Нет сохраненных групп или преподавателей для удаления'
    else:
        c.close()
        conn.close()
        logger.log('SQL', f'No saved settings for {ctx.name} <{ctx.user_id}>')
        return 'Невозможно удалить, так как для вас нет сохраненых параметров. Добавьте сначала группу или преподавателя'


# Отображение текущих настроек
def display_saved_settings(email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error('Incorrect request to display saved settings. No platform specified')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    logger.log('SQL', f'Incoming request to display all saved settings for {ctx.name} = <{ctx.user_id}>')
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f'SELECT * FROM {ctx.table} WHERE {ctx.id_column} = ?', (ctx.user_id,))
    result = c.fetchone()
    c.close()
    conn.close()
    if result is not None:
        answer = ''
        if result['group_id'] is None and result['teacher'] is None:
            answer += 'Нет сохраненных групп и преподавателей\n'
        if result['group_id'] is not None:
            groups = str(result['group_id']).split('\n')
            answer += 'Сохранены группы: ' + ' '.join(groups) + '\n'
        if result['teacher'] is not None:
            teachers = str(result['teacher']).split('\n')
            answer += 'Сохранены преподаватели: ' + ' '.join(teachers) + '\n'
        if result['notification'] == 1:
            answer += 'Уведомления включены\n'
        elif result['notification'] == 0:
            answer += 'Уведомления отключены\n'
        if result['lesson_time'] == 1:
            answer += 'Отображение времени занятий включено'
        elif result['lesson_time'] == 0:
            answer += 'Отображение времени занятий отключено'
        logger.log('SQL', f'Display saved settings for {ctx.name} <{ctx.user_id}>')
        return answer
    else:
        logger.log('SQL', f'No saved settings for {ctx.name} <{ctx.user_id}>')
        return 'Для вас нет сохраненных параметров'


# Получение расписания для пользователя
def getting_timetable_for_user(next: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error('Incorrect timetable request. No platform specified')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    logger.log('SQL', f'Incoming timetable request for {ctx.name} = <{ctx.user_id}>')
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f'SELECT * FROM {ctx.table} WHERE {ctx.id_column} = ?', (ctx.user_id,))
    row = c.fetchone()
    c.close()
    conn.close()
    if row is not None:
        teachers_answer = ''
        groups_answer = ''
        lesson_time = None
        if row['lesson_time'] == 0:
            lesson_time = 'NO'
        if row['group_id'] is None and row['teacher'] is None:
            logger.log('SQL', f'No saved groups or teachers for {ctx.name} <{ctx.user_id}>')
            return 'Нет сохраненных групп или преподавателей для отправки расписания'
        # Email не использует 'Cut\n' разделитель
        separator = '' if ctx.name == 'email' else MESSAGE_SPLIT_SENTINEL
        if row['teacher'] is not None:
            teachers = str(row['teacher']).replace('\r', '').split('\n')
            for i in teachers:
                teachers_answer += separator + timetable(teacher=str(i), next=next, lesson_time=lesson_time) + '\n'
        if row['group_id'] is not None:
            groups = str(row['group_id']).replace('\r', '').split('\n')
            for i in groups:
                groups_answer += separator + timetable(group_id=str(i), next=next, lesson_time=lesson_time) + '\n'
        logger.log('SQL', f'Response to timetable request for {ctx.name} <{ctx.user_id}>')
        result = teachers_answer + groups_answer
        if ctx.name == 'email':
            return format_timetable_html(result)
        return result
    else:
        logger.log('SQL', f'No saved groups or teachers for {ctx.name} <{ctx.user_id}>')
        return 'Нет сохраненных групп или преподавателей для отправки расписания'


# Получение учебной нагрузки для пользователя
def getting_workload_for_user(next: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    ctx = resolve_platform(email=email, vk_id_chat=vk_id_chat, vk_id_user=vk_id_user, telegram=telegram, discord=discord)
    if ctx is None:
        logger.error('Incorrect workload request. No platform specified')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
    logger.log('SQL', f'Incoming workload request for {ctx.name} = <{ctx.user_id}>')
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f'SELECT * FROM {ctx.table} WHERE {ctx.id_column} = ?', (ctx.user_id,))
    row = c.fetchone()
    c.close()
    conn.close()
    if row is not None:
        if row['teacher'] is None:
            logger.log('SQL', f'No saved teachers for {ctx.name} <{ctx.user_id}>')
            return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
        teachers_answer = ''
        separator = '' if ctx.name == 'email' else MESSAGE_SPLIT_SENTINEL
        teachers = str(row['teacher']).replace('\r', '').split('\n')
        for i in teachers:
            teachers_answer += separator + workload(teacher=str(i), next=next) + '\n'
        logger.log('SQL', f'Response to workload request for {ctx.name} <{ctx.user_id}>')
        return teachers_answer
    else:
        logger.log('SQL', f'No saved teachers for {ctx.name} <{ctx.user_id}>')
        return 'Нет сохраненных преподавателей для отправки учебной нагрузки'

