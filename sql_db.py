import asyncio
import os
import platform
import sqlite3
from glob import iglob
from pathlib import Path

from vkbottle import API

from calendar_timetable import create_calendar_file_with_timetable, download_calendar_file_to_github
from logger import logger
from other import read_config, get_latest_file, connection_to_sql, sendMail
from timetable import date_request, timetable, workload

# Инициализация
vk_token = read_config(vk='YES')
tg_token = read_config(telegram='YES')
ds_token = read_config(discord='YES')


# В Windows asyncio есть баг, это исправление
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def write_msg_vk_chat(message: str, chat_id: str):
    import random
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
            message='➡ ' + message,
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
    import random
    logger.log('SQL', f'Try to send message to vk user <{str(user_id)}>')
    api = API(vk_token)
    try:
        user_id = int(user_id)
        result = await api.messages.send(
            message='➡ ' + message,
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
            await bot.send_message(chat_id=chat_id, text='➡ ' + message)
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
                    await bot.send_message(chat_id=int(new_id), text='➡ ' + message)
                    logger.log('SQL', f'Message have been sent to telegram <{str(new_id)}>)')
                    return True
                except Exception as e2:
                    logger.log('SQL', f'Error happened while sending message to migrated telegram id <{str(new_id)}>: {e2}')
                    return False
            else:
                # Detect when bot was blocked by the user and disable notifications for this telegram id
                lower_err = err_text.lower() if err_text else ''
                if ('bot was blocked' in lower_err) or (('forbidden' in lower_err) and ('blocked' in lower_err)):
                    logger.log('SQL', f'Telegram bot was blocked by user <{single_id}>, disabling notifications in DB')
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
            sendMail(to_email=user['email'], subject='Изменения в расписании', text=answer)
    return True


async def send_notifications_vk_chat_async(group_list_current_week: list, group_list_next_week: list, teacher_list_current_week: list, teacher_list_next_week: list):
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    vk_users = c.execute('SELECT * FROM vk_chat WHERE notification = 1').fetchall()
    c.close()
    conn.close()
    for user in vk_users:
        messages = []
        if teacher_list_current_week:
            for item in teacher_list_current_week:
                if user['teacher'] is not None and str(item) in str(user['teacher']):
                    messages.append((f'Изменения в расписании на текущую неделю для преподавателя {item}', user['vk_id']))
                    if user['lesson_time'] == 1:
                        messages.append((timetable(teacher=item), user['vk_id']))
                    else:
                        messages.append((timetable(teacher=item, lesson_time='YES'), user['vk_id']))
        if teacher_list_next_week:
            for item in teacher_list_next_week:
                if user['teacher'] is not None and str(item) in str(user['teacher']):
                    messages.append((f'Изменения в расписании на следующую неделю для преподавателя {item}', user['vk_id']))
                    if user['lesson_time'] == 1:
                        messages.append((timetable(teacher=item, next='YES'), user['vk_id']))
                    else:
                        messages.append((timetable(teacher=item, lesson_time='YES', next='YES'), user['vk_id']))
        if group_list_current_week:
            for item in group_list_current_week:
                if user['group_id'] is not None and str(item) in str(user['group_id']):
                    messages.append((f'Изменения в расписании на текущую неделю для группы {item}', user['vk_id']))
                    if user['lesson_time'] == 1:
                        messages.append((timetable(group_id=item), user['vk_id']))
                    else:
                        messages.append((timetable(group_id=item, lesson_time='YES'), user['vk_id']))
        if group_list_next_week:
            for item in group_list_next_week:
                if user['group_id'] is not None and str(item) in str(user['group_id']):
                    messages.append((f'Изменения в расписании на следующую неделю для группы {item}', user['vk_id']))
                    if user['lesson_time'] == 1:
                        messages.append((timetable(group_id=item, next='YES'), user['vk_id']))
                    else:
                        messages.append((timetable(group_id=item, lesson_time='YES', next='YES'), user['vk_id']))
        for msg, chat_id in messages:
            logger.log('SQL', f'Попытка отправки сообщения в VK чат: chat_id={chat_id}')
            try:
                result = await write_msg_vk_chat(msg, chat_id)
                logger.log('SQL', f'Результат отправки VK чату chat_id={chat_id}: {result}')
            except Exception as e:
                logger.log('SQL', f'Ошибка при отправке VK чату chat_id={chat_id}: {e}')
            await asyncio.sleep(0.4)
    return True

def send_notifications_vk_chat(group_list_current_week: list, group_list_next_week: list, teacher_list_current_week: list, teacher_list_next_week: list):
    import inspect
    frame = inspect.currentframe().f_back
    is_async = frame and frame.f_code.co_flags & inspect.CO_COROUTINE
    if is_async:
        # В асинхронном контексте просто await
        return send_notifications_vk_chat_async(group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week)
    else:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если цикл уже запущен, используем run_coroutine_threadsafe
                fut = asyncio.run_coroutine_threadsafe(
                    send_notifications_vk_chat_async(group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week), loop)
                return fut.result()
            else:
                return loop.run_until_complete(
                    send_notifications_vk_chat_async(group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week))
        except RuntimeError:
            # Если нет активного цикла, создаём новый
            return asyncio.run(
                send_notifications_vk_chat_async(group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week))

async def send_notifications_vk_user_async(group_list_current_week: list, group_list_next_week: list, teacher_list_current_week: list, teacher_list_next_week: list):
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    vk_users = c.execute('SELECT * FROM vk_user WHERE notification = 1').fetchall()
    c.close()
    conn.close()
    for user in vk_users:
        messages = []
        if teacher_list_current_week:
            for item in teacher_list_current_week:
                if user['teacher'] is not None and str(item) in str(user['teacher']):
                    messages.append((f'Изменения в расписании на текущую неделю для преподавателя {item}', user['vk_id']))
                    if user['lesson_time'] == 1:
                        messages.append((timetable(teacher=item), user['vk_id']))
                    else:
                        messages.append((timetable(teacher=item, lesson_time='YES'), user['vk_id']))
        if teacher_list_next_week:
            for item in teacher_list_next_week:
                if user['teacher'] is not None and str(item) in str(user['teacher']):
                    messages.append((f'Изменения в расписании на следующую неделю для преподавателя {item}', user['vk_id']))
                    if user['lesson_time'] == 1:
                        messages.append((timetable(teacher=item, next='YES'), user['vk_id']))
                    else:
                        messages.append((timetable(teacher=item, lesson_time='YES', next='YES'), user['vk_id']))
        if group_list_current_week:
            for item in group_list_current_week:
                if user['group_id'] is not None and str(item) in str(user['group_id']):
                    messages.append((f'Изменения в расписании на текущую неделю для группы {item}', user['vk_id']))
                    if user['lesson_time'] == 1:
                        messages.append((timetable(group_id=item), user['vk_id']))
                    else:
                        messages.append((timetable(group_id=item, lesson_time='YES'), user['vk_id']))
        if group_list_next_week:
            for item in group_list_next_week:
                if user['group_id'] is not None and str(item) in str(user['group_id']):
                    messages.append((f'Изменения в расписании на следующую неделю для группы {item}', user['vk_id']))
                    if user['lesson_time'] == 1:
                        messages.append((timetable(group_id=item, next='YES'), user['vk_id']))
                    else:
                        messages.append((timetable(group_id=item, lesson_time='YES', next='YES'), user['vk_id']))
        for msg, vk_id in messages:
            logger.log('SQL', f'Попытка отправки сообщения VK пользователю: vk_id={vk_id}')
            try:
                result = await write_msg_vk_user(msg, vk_id)
                logger.log('SQL', f'Результат отправки VK пользователю vk_id={vk_id}: {result}')
            except Exception as e:
                logger.log('SQL', f'Ошибка при отправке VK пользователю vk_id={vk_id}: {e}')
            await asyncio.sleep(0.4)  # задержка между сообщениями (400 мс)
    return True

def send_notifications_vk_user(group_list_current_week: list, group_list_next_week: list, teacher_list_current_week: list, teacher_list_next_week: list):

    import inspect
    frame = inspect.currentframe().f_back
    is_async = frame and frame.f_code.co_flags & inspect.CO_COROUTINE
    if is_async:
        # В асинхронном контексте просто await
        return send_notifications_vk_user_async(group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week)
    else:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                fut = asyncio.run_coroutine_threadsafe(
                    send_notifications_vk_user_async(group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week), loop)
                return fut.result()
            else:
                return loop.run_until_complete(
                    send_notifications_vk_user_async(group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week))
        except RuntimeError:
            return asyncio.run(
                send_notifications_vk_user_async(group_list_current_week, group_list_next_week, teacher_list_current_week, teacher_list_next_week))

def send_notifications_telegram(group_list_current_week: list, group_list_next_week: list, teacher_list_current_week: list, teacher_list_next_week: list):
    """
    Берем по одному пользователю из бд, и смотрим, есть ли у него совпадение с кем-то из списков
    Если есть, то отправляем сообщение, что расписание изменилось для такой-то группы или преподавателя
    """
    # Подключение к пользовательской базе данных
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    users = c.execute('SELECT * FROM telegram WHERE notification = 1').fetchall()
    c.close()
    conn.close()
    for user in users:
        if teacher_list_current_week:
            for item in teacher_list_current_week:
                if user['teacher'] is not None:
                    if str(item) in str(user['teacher']):
                        asyncio.run(write_msg_telegram(message=f'Изменения в расписании на текущую неделю для преподавателя {item}', tg_id=user['telegram_id']))
                        if user['lesson_time'] == 1:
                            asyncio.run(write_msg_telegram(
                                message=timetable(teacher=item), tg_id=user['telegram_id']))
                        else:
                            asyncio.run(write_msg_telegram(
                                message=timetable(teacher=item, lesson_time='YES'), tg_id=user['telegram_id']))
        if teacher_list_next_week:
            for item in teacher_list_next_week:
                if user['teacher'] is not None:
                    if str(item) in str(user['teacher']):
                        asyncio.run(write_msg_telegram(
                            message=f'Изменения в расписании на следующую неделю для преподавателя {item}', tg_id=user['telegram_id']))
                        if user['lesson_time'] == 1:
                            asyncio.run(write_msg_telegram(
                                message=timetable(teacher=item, next='YES'), tg_id=user['telegram_id']))
                        else:
                            asyncio.run(write_msg_telegram(
                                message=timetable(teacher=item, lesson_time='YES', next='YES'), tg_id=user['telegram_id']))
        if group_list_current_week:
            for item in group_list_current_week:
                if user['group_id'] is not None:
                    if str(item) in str(user['group_id']):
                        asyncio.run(write_msg_telegram(
                            message=f'Изменения в расписании на текущую неделю для группы {item}', tg_id=user['telegram_id']))
                        if user['lesson_time'] == 1:
                            asyncio.run(write_msg_telegram(
                                message=timetable(group_id=item), tg_id=user['telegram_id']))
                        else:
                            asyncio.run(write_msg_telegram(
                                message=timetable(group_id=item, lesson_time='YES'), tg_id=user['telegram_id']))
        if group_list_next_week:
            for item in group_list_next_week:
                if user['group_id'] is not None:
                    if str(item) in str(user['group_id']):
                        asyncio.run(write_msg_telegram(
                            message=f'Изменения в расписании на следующую неделю для группы {item}', tg_id=user['telegram_id']))
                        if user['lesson_time'] == 1:
                            asyncio.run(write_msg_telegram(
                                message=timetable(group_id=item, next='YES'), tg_id=user['telegram_id']))
                        else:
                            asyncio.run(write_msg_telegram(
                                message=timetable(group_id=item, lesson_time='YES', next='YES'), tg_id=user['telegram_id']))
    return True


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
    c.execute("SELECT * FROM main.timetable EXCEPT SELECT * FROM db2.timetable")
    difference = c.fetchall()
    c.close()
    conn.close()
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
        if not str(row['Name']) in list_with_teachers:
            list_with_teachers += [str(row['Name'])]
            # Если календарь существует для этого преподавателя
            calendar_row = c.execute('SELECT * FROM calendars WHERE teacher = ?', (str(row['Name']),)).fetchone()
            if calendar_row:
                if create_calendar_file_with_timetable(teacher=str(row['Name'])) is True:
                    if download_calendar_file_to_github(filename=str(row['Name'])) is False:
                        logger.log('SQL', f'Cant import timetable to calendar for teacher = "{str(row["Name"])}"')
                    else:
                        logger.log('SQL', f'Calendar for teacher = "{str(row["Name"])}" has been successfully updated')
        if not str(row['Group-Utf']) in list_with_groups:
            list_with_groups += [str(row['Group-Utf'])]
            calendar_row = c.execute('SELECT * FROM calendars WHERE group_id = ?', (str(row['Group-Utf']),)).fetchone()
            if calendar_row:
                if create_calendar_file_with_timetable(group_id=str(row['Group-Utf'])) is True:
                    if download_calendar_file_to_github(filename=str(row['Group-Utf'])) is False:
                        logger.log('SQL', f'Cant import timetable to calendar for group = {str(row["Group-Utf"])}')
                    else:
                        logger.log('SQL', f'Calendar for group = "{str(row["Group-Utf"])}" has been successfully updated')
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
        if str(row['Date']) in dates_current_week:
            if str(row['Name']) not in teacher_list_current_week:
                if str(timetable(teacher=str(row['Name']))) != str(timetable(teacher=str(row['Name']), use_previous_timetable_db='YES')):
                    teacher_list_current_week += [str(row['Name'])]
            if str(row["Group-Utf"]) not in group_list_current_week:
                if str(timetable(group_id=str(row['Group-Utf']))) != str(timetable(group_id=str(row['Group-Utf']), use_previous_timetable_db='YES')):
                    group_list_current_week += [str(row['Group-Utf'])]
        elif str(row['Date']) in dates_next_week:
            if str(row['Name']) not in teacher_list_next_week:
                if str(timetable(teacher=str(row['Name']), next='YES')) != str(timetable(teacher=str(row['Name']), next='YES', use_previous_timetable_db='YES')):
                    teacher_list_next_week += [str(row['Name'])]
            if str(row['Group-Utf']) not in group_list_next_week:
                if str(timetable(group_id=str(row['Group-Utf']), next='YES')) != str(timetable(group_id=str(row['Group-Utf']), next='YES', use_previous_timetable_db='YES')):
                    group_list_next_week += [str(row['Group-Utf'])]
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
def search_group_and_teacher_in_request(request: str, email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    """
    Поступает запрос -> смотрим, существуют ли такие данные в бд расписания
    есть - добавляем в базу данных пользователя, нет - ищем возможные совпадения из бд расписания ->
    -> совпадения есть - отправляем пользователю возможные варианты, нет - отправляем False

    Нужно учесть что функция не должна быть False, для её отображения пользователю
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
    # Ищет группы и преподавателей для переданного запроса и сохраняет их в свой список для дальнейшего по ним поиска
    matched_group = []
    matched_teacher = []
    for row in timetable_rows:
        # Преподаватели
        if request.find(str(row['Name'])) != -1 and not str(row['Name']) in matched_teacher and not str(row['Name']) == ' ':
            matched_teacher += [str(row['Name'])]
        # Группы
        if request.find(str(row['Group-Utf'])) != -1 and not str(row['Group-Utf']) in matched_group:
            matched_group += [str(row['Group-Utf'])]
    # Если есть хоть одна распознанная группа или преподаватель
    if matched_group or matched_teacher:
        # Закрываем подключение, так как будем работать с другой бд
        c.close()
        conn.close()
        # Почта
        if email is not None and (vk_id_chat is None and vk_id_user is None and telegram is None and discord is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM email WHERE email = ?', (email,))
            email_row = c.fetchone()
            # Если запись в бд есть
            if email_row:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_teacher = ''
                response_group = ''
                if matched_teacher and email_row['teacher'] is not None:
                    for i in matched_teacher:
                        if str(email_row['teacher']).find(str(i)) != -1:
                            response_teacher += i + ' '
                if matched_group and email_row['group_id'] is not None:
                    for j in matched_group:
                        if str(email_row['group_id']).find(str(j)) != -1:
                            response_group += j + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вас уже сохранены группы: ' + response_group
                # Поиск значений, которых нет в базе данных и добавление их
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if str(email_row['teacher']).find(str(i)) == -1:
                            teacher_value_in_email_row_at_now = c.execute('SELECT * FROM email WHERE email = ?', (email,)).fetchone()[
                                'teacher']
                            if teacher_value_in_email_row_at_now is not None:
                                c.execute('UPDATE email SET teacher = ? WHERE email = ?',
                                          (teacher_value_in_email_row_at_now + '\n' + i, email))
                                response_teacher += ' ' + i
                            else:
                                c.execute('UPDATE email SET teacher = ? WHERE email = ?', (i, email))
                                response_teacher += i
                if matched_group:
                    for i in matched_group:
                        if str(email_row['group_id']).find(str(i)) == -1:
                            group_value_in_email_row_at_now = c.execute('SELECT * FROM email WHERE email = ?', (email,)).fetchone()[
                                'group_id']
                            if group_value_in_email_row_at_now is not None:
                                c.execute('UPDATE email SET group_id = ? WHERE email = ?',
                                          (group_value_in_email_row_at_now + '\n' + i, email))
                                response_group += ' ' + i
                            else:
                                c.execute('UPDATE email SET group_id = ? WHERE email = ?', (i, email))
                                response_group += i
                # Сохранение изменений и закрытие подключения
                conn.commit()
                c.close()
                conn.close()
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то Enter не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response == '' and response_group != '':
                    response += 'Добавлены группы: ' + response_group
                elif response != '' and response_group != '':
                    response += '\nДобавлены группы: ' + response_group
                logger.log('SQL', 'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" for email <' + email + '>')
            # Если записей нет для этой почты, то создаем новую
            else:
                logger.log('SQL', 'No values found for email <' + email + '>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                # Обработка строк для добавление в базу данных и вывод добавленных
                if matched_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            insert_teacher += i
                            response_teacher += i
                        else:
                            insert_teacher += i + '\n'
                            response_teacher += i + ' '
                # Для выставления NULL в базе данных, если найденных преподавателей нет
                else:
                    insert_teacher = None
                if matched_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            insert_group += i
                            response_group += i
                        else:
                            insert_group += i + '\n'
                            response_group += i + ' '
                # Для выставления NULL в базе данных, если найденных групп нет
                else:
                    insert_group = None
                # Добавление записи в пользовательскую бд
                c.execute('INSERT INTO email (email, group_id, teacher, notification, lesson_time) VALUES (?, ?, ?, 1, 1)',
                          (email, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Добавлены группы: ' + response_group
                logger.log('SQL', 'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" for email <' + email + '>')
            return response
        # ВК чат
        elif vk_id_chat is not None and (email is None and vk_id_user is None and telegram is None and discord is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
            vk_chat_row = c.fetchone()
            # Если запись в бд есть
            if vk_chat_row:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_teacher = ''
                response_group = ''
                if matched_teacher and vk_chat_row['teacher'] is not None:
                    for i in matched_teacher:
                        if str(vk_chat_row['teacher']).find(str(i)) != -1:
                            response_teacher += i + ' '
                if matched_group and vk_chat_row['group_id'] is not None:
                    for j in matched_group:
                        if str(vk_chat_row['group_id']).find(str(j)) != -1:
                            response_group += j + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Преподаватели уже сохранены: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Преподаватели уже сохранены: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Группы уже сохранены: ' + response_group
                # Поиск значений, которых нет в базе данных и добавление их
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if str(vk_chat_row['teacher']).find(str(i)) == -1:
                            teacher_value_in_vk_chat_row_at_now = \
                            c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,)).fetchone()[
                                'teacher']
                            if teacher_value_in_vk_chat_row_at_now is not None:
                                c.execute('UPDATE vk_chat SET teacher = ? WHERE vk_id = ?',
                                          (teacher_value_in_vk_chat_row_at_now + '\n' + i, vk_id_chat))
                                response_teacher += ' ' + i
                            else:
                                c.execute('UPDATE vk_chat SET teacher = ? WHERE vk_id = ?', (i, vk_id_chat))
                                response_teacher += i
                if matched_group:
                    for i in matched_group:
                        if str(vk_chat_row['group_id']).find(str(i)) == -1:
                            group_value_in_vk_chat_row_at_now = \
                            c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,)).fetchone()[
                                'group_id']
                            if group_value_in_vk_chat_row_at_now is not None:
                                c.execute('UPDATE vk_chat SET group_id = ? WHERE vk_id = ?',
                                          (group_value_in_vk_chat_row_at_now + '\n' + i, vk_id_chat))
                                response_group += ' ' + i
                            else:
                                c.execute('UPDATE vk_chat SET group_id = ? WHERE vk_id = ?', (i, vk_id_chat))
                                response_group += i
                # Сохранение изменений и закрытие подключения
                conn.commit()
                c.close()
                conn.close()
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то Enter не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response == '' and response_group != '':
                    response += 'Добавлены группы: ' + response_group
                elif response != '' and response_group != '':
                    response += '\nДобавлены группы: ' + response_group
                logger.log('SQL',
                           'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" for vk chat <' + vk_id_chat + '>')
            # Если записей нет для этой почты, то создаем новую
            else:
                logger.log('SQL', 'No values found for vk chat <' + vk_id_chat + '>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                # Обработка строк для добавление в базу данных и вывод добавленных
                if matched_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            insert_teacher += i
                            response_teacher += i
                        else:
                            insert_teacher += i + '\n'
                            response_teacher += i + ' '
                # Для выставления NULL в базе данных, если найденных преподавателей нет
                else:
                    insert_teacher = None
                if matched_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            insert_group += i
                            response_group += i
                        else:
                            insert_group += i + '\n'
                            response_group += i + ' '
                # Для выставления NULL в базе данных, если найденных групп нет
                else:
                    insert_group = None
                # Добавление записи в пользовательскую бд
                c.execute(
                    'INSERT INTO vk_chat (vk_id, group_id, teacher, notification, lesson_time) VALUES (?, ?, ?, 1, 1)',
                    (vk_id_chat, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Добавлены группы: ' + response_group
                logger.log('SQL',
                           'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" for vk chat <' + vk_id_chat + '>')
            return response
        # ВК пользователь
        elif vk_id_user is not None and (email is None and vk_id_chat is None and telegram is None and discord is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
            vk_user_row = c.fetchone()
            # Если запись в бд есть
            if vk_user_row:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_teacher = ''
                response_group = ''
                if matched_teacher and vk_user_row['teacher'] is not None:
                    for i in matched_teacher:
                        if str(vk_user_row['teacher']).find(str(i)) != -1:
                            response_teacher += i + ' '
                if matched_group and vk_user_row['group_id'] is not None:
                    for j in matched_group:
                        if str(vk_user_row['group_id']).find(str(j)) != -1:
                            response_group += j + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вас уже сохранены группы: ' + response_group
                # Поиск значений, которых нет в базе данных и добавление их
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if str(vk_user_row['teacher']).find(str(i)) == -1:
                            teacher_value_in_vk_user_row_at_now = \
                                c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,)).fetchone()[
                                    'teacher']
                            if teacher_value_in_vk_user_row_at_now is not None:
                                c.execute('UPDATE vk_user SET teacher = ? WHERE vk_id = ?',
                                          (teacher_value_in_vk_user_row_at_now + '\n' + i, vk_id_user))
                                response_teacher += ' ' + i
                            else:
                                c.execute('UPDATE vk_user SET teacher = ? WHERE vk_id = ?', (i, vk_id_user))
                                response_teacher += i
                if matched_group:
                    for i in matched_group:
                        if str(vk_user_row['group_id']).find(str(i)) == -1:
                            group_value_in_vk_user_row_at_now = \
                                c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,)).fetchone()[
                                    'group_id']
                            if group_value_in_vk_user_row_at_now is not None:
                                c.execute('UPDATE vk_user SET group_id = ? WHERE vk_id = ?',
                                          (group_value_in_vk_user_row_at_now + '\n' + i, vk_id_user))
                                response_group += ' ' + i
                            else:
                                c.execute('UPDATE vk_user SET group_id = ? WHERE vk_id = ?', (i, vk_id_user))
                                response_group += i
                # Сохранение изменений и закрытие подключения
                conn.commit()
                c.close()
                conn.close()
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то Enter не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response == '' and response_group != '':
                    response += 'Добавлены группы: ' + response_group
                elif response != '' and response_group != '':
                    response += '\nДобавлены группы: ' + response_group
                logger.log('SQL',
                           'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" for vk user <' + vk_id_user + '>')
            # Если записей нет для этой почты, то создаем новую
            else:
                logger.log('SQL', 'No values found for vk user <' + vk_id_user + '>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                # Обработка строк для добавление в базу данных и вывод добавленных
                if matched_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            insert_teacher += i
                            response_teacher += i
                        else:
                            insert_teacher += i + '\n'
                            response_teacher += i + ' '
                # Для выставления NULL в базе данных, если найденных преподавателей нет
                else:
                    insert_teacher = None
                if matched_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            insert_group += i
                            response_group += i
                        else:
                            insert_group += i + '\n'
                            response_group += i + ' '
                # Для выставления NULL в базе данных, если найденных групп нет
                else:
                    insert_group = None
                # Добавление записи в пользовательскую бд
                c.execute(
                    'INSERT INTO vk_user (vk_id, group_id, teacher, notification, lesson_time) VALUES (?, ?, ?, 1, 1)',
                    (vk_id_user, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Добавлены группы: ' + response_group
                logger.log('SQL',
                           'Added values teachers: "' + response_teacher + '", groups: "' + response_group + '" for vk user <' + vk_id_user + '>')
            return response
        # Telegram
        elif telegram is not None and (email is None and vk_id_chat is None and vk_id_user is None and discord is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM telegram WHERE telegram_id = ?', (telegram,))
            telegram_row = c.fetchone()
            # Если запись в бд есть
            if telegram_row:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_teacher = ''
                response_group = ''
                if matched_teacher and telegram_row['teacher'] is not None:
                    for i in matched_teacher:
                        if str(telegram_row['teacher']).find(str(i)) != -1:
                            response_teacher += i + ' '
                if matched_group and telegram_row['group_id'] is not None:
                    for j in matched_group:
                        if str(telegram_row['group_id']).find(str(j)) != -1:
                            response_group += j + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вас уже сохранены группы: ' + response_group
                # Поиск значений, которых нет в базе данных и добавление их
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if str(telegram_row['teacher']).find(str(i)) == -1:
                            teacher_value_in_telegram_row_at_now = \
                                c.execute('SELECT * FROM telegram WHERE telegram_id = ?', (telegram,)).fetchone()[
                                    'teacher']
                            if teacher_value_in_telegram_row_at_now is not None:
                                c.execute('UPDATE telegram SET teacher = ? WHERE telegram_id = ?',
                                          (teacher_value_in_telegram_row_at_now + '\n' + i, telegram))
                                response_teacher += ' ' + i
                            else:
                                c.execute('UPDATE telegram SET teacher = ? WHERE telegram_id = ?', (i, telegram))
                                response_teacher += i
                if matched_group:
                    for i in matched_group:
                        if str(telegram_row['group_id']).find(str(i)) == -1:
                            group_value_in_telegram_row_at_now = \
                                c.execute('SELECT * FROM telegram WHERE telegram_id = ?', (telegram,)).fetchone()[
                                    'group_id']
                            if group_value_in_telegram_row_at_now is not None:
                                c.execute('UPDATE telegram SET group_id = ? WHERE telegram_id = ?',
                                          (group_value_in_telegram_row_at_now + '\n' + i, telegram))
                                response_group += ' ' + i
                            else:
                                c.execute('UPDATE telegram SET group_id = ? WHERE telegram_id = ?', (i, telegram))
                                response_group += i
                # Сохранение изменений и закрытие подключения
                conn.commit()
                c.close()
                conn.close()
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то Enter не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response == '' and response_group != '':
                    response += 'Добавлены группы: ' + response_group
                elif response != '' and response_group != '':
                    response += '\nДобавлены группы: ' + response_group
                logger.log('SQL',
                           f'Added values teachers: "{response_teacher}", groups: "{response_group}" for telegram <{telegram}>')
            # Если записей нет для этой почты, то создаем новую
            else:
                logger.log('SQL', f'No values found for telegram <{telegram}>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                # Обработка строк для добавления в базу данных и вывод добавленных
                if matched_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            insert_teacher += i
                            response_teacher += i
                        else:
                            insert_teacher += i + '\n'
                            response_teacher += i + ' '
                # Для выставления NULL в базе данных, если найденных преподавателей нет
                else:
                    insert_teacher = None
                if matched_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            insert_group += i
                            response_group += i
                        else:
                            insert_group += i + '\n'
                            response_group += i + ' '
                # Для выставления NULL в базе данных, если найденных групп нет
                else:
                    insert_group = None
                # Добавление записи в пользовательскую бд
                c.execute(
                    'INSERT INTO telegram (telegram_id, group_id, teacher, notification, lesson_time) VALUES (?, ?, ?, 1, 1)',
                    (telegram, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Добавлены группы: ' + response_group
                logger.log('SQL',
                           f'Added values teachers: "{response_teacher}", groups: "{response_group}" for telegram <{telegram}>')
            return response
        # Discord
        elif discord is not None and (email is None and vk_id_chat is None and vk_id_user is None and telegram is None):
            response = ''
            conn = connection_to_sql('user_settings.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM discord WHERE discord_id = ?', (discord,))
            discord_row = c.fetchone()
            # Если запись в бд есть
            if discord_row:
                # Поиск значений, которые уже есть в базе данных и вывод их
                response_teacher = ''
                response_group = ''
                if matched_teacher and discord_row['teacher'] is not None:
                    for i in matched_teacher:
                        if str(discord_row['teacher']).find(str(i)) != -1:
                            response_teacher += i + ' '
                if matched_group and discord_row['group_id'] is not None:
                    for j in matched_group:
                        if str(discord_row['group_id']).find(str(j)) != -1:
                            response_group += j + ' '
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Для вас уже сохранены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Для вас уже сохранены группы: ' + response_group
                # Поиск значений, которых нет в базе данных и добавление их
                response_teacher = ''
                response_group = ''
                if matched_teacher:
                    for i in matched_teacher:
                        if str(discord_row['teacher']).find(str(i)) == -1:
                            teacher_value_in_discord_row_at_now = \
                                c.execute('SELECT * FROM discord WHERE discord_id = ?', (discord,)).fetchone()[
                                    'teacher']
                            if teacher_value_in_discord_row_at_now is not None:
                                c.execute('UPDATE discord SET teacher = ? WHERE discord_id = ?',
                                          (teacher_value_in_discord_row_at_now + '\n' + i, discord))
                                response_teacher += ' ' + i
                            else:
                                c.execute('UPDATE discord SET teacher = ? WHERE discord_id = ?', (i, discord))
                                response_teacher += i
                if matched_group:
                    for i in matched_group:
                        if str(discord_row['group_id']).find(str(i)) == -1:
                            group_value_in_discord_row_at_now = \
                                c.execute('SELECT * FROM discord WHERE discord_id = ?', (discord,)).fetchone()[
                                    'group_id']
                            if group_value_in_discord_row_at_now is not None:
                                c.execute('UPDATE discord SET group_id = ? WHERE discord_id = ?',
                                          (group_value_in_discord_row_at_now + '\n' + i, discord))
                                response_group += ' ' + i
                            else:
                                c.execute('UPDATE discord SET group_id = ? WHERE discord_id = ?', (i, discord))
                                response_group += i
                # Сохранение изменений и закрытие подключения
                conn.commit()
                c.close()
                conn.close()
                # Если ответ не пустой, преподаватели есть и группы есть, то добавить Enter в начало и конец
                if response != '' and response_teacher != '' and response_group != '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ не пустой, преподаватели есть, а групп нет, то добавить Enter в начало
                elif response != '' and response_teacher != '' and response_group == '':
                    response += '\n\nДобавлены преподаватели: ' + response_teacher
                # Если ответ пустой, преподаватели есть и группы есть, то добавить Enter в конец
                if response == '' and response_teacher != '' and response_group != '':
                    response += '\nДобавлены преподаватели: ' + response_teacher + '\n'
                # Если ответ пустой, преподаватели есть, а групп нет, то Enter не добавлять
                elif response == '' and response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response == '' and response_group != '':
                    response += 'Добавлены группы: ' + response_group
                elif response != '' and response_group != '':
                    response += '\nДобавлены группы: ' + response_group
                logger.log('SQL',
                           f'Added values teachers: "{response_teacher}", groups: "{response_group}" for discord <{discord}>')
            # Если записей нет для этой почты, то создаем новую
            else:
                logger.log('SQL', f'No values found for discord <{discord}>. Create new entry...')
                insert_group = ''
                insert_teacher = ''
                response_teacher = ''
                response_group = ''
                # Обработка строк для добавления в базу данных и вывод добавленных
                if matched_teacher:
                    for i in matched_teacher:
                        if matched_teacher[-1] == i:
                            insert_teacher += i
                            response_teacher += i
                        else:
                            insert_teacher += i + '\n'
                            response_teacher += i + ' '
                # Для выставления NULL в базе данных, если найденных преподавателей нет
                else:
                    insert_teacher = None
                if matched_group:
                    for i in matched_group:
                        if matched_group[-1] == i:
                            insert_group += i
                            response_group += i
                        else:
                            insert_group += i + '\n'
                            response_group += i + ' '
                # Для выставления NULL в базе данных, если найденных групп нет
                else:
                    insert_group = None
                # Добавление записи в пользовательскую бд
                c.execute(
                    'INSERT INTO discord (discord_id, group_id, teacher, notification, lesson_time) VALUES (?, ?, ?, 1, 1)',
                    (discord, insert_group, insert_teacher))
                conn.commit()
                c.close()
                conn.close()
                # Если преподаватели есть и группы есть, то добавить Enter
                if response_teacher != '' and response_group != '':
                    response += 'Добавлены преподаватели: ' + response_teacher + '\n'
                # Если преподаватели есть, а групп нет
                elif response_teacher != '' and response_group == '':
                    response += 'Добавлены преподаватели: ' + response_teacher
                # Если есть группы
                if response_group != '':
                    response += 'Добавлены группы: ' + response_group
                logger.log('SQL',
                           f'Added values teachers: "{response_teacher}", groups: "{response_group}" for discord <{discord}>')
            return response
        else:
            logger.error('Incorrect request to search groups and teachers')
            return False
    # Если ничего не распознано, то ищем возможные варианты, что хотел написать пользователь
    else:
        logger.log('SQL', 'No recognized groups or teachers. Start search suggestions...')
        """
        Пльзователи могут (и часто делают) написать фамилию с пробелом в инициалах
        Поэтому делаем проверку на количество символов, чтобы определить, что это точно фамилия
        И убираем последние 4 символа, чего должно быть достаточно, чтобы распознать фамилию
        
        Если меньше 6 символов, то это скорее всего группа, поэтому ищем весь запрос
        """
        if len(request) > 6:
            request_mod = '%' + request[:-4] + '%'
        else:
            request_mod = '%' + request + '%'
        # Поиск в базе данных для группы
        c.execute('SELECT * FROM timetable WHERE "Group-Utf" LIKE ?', (request_mod,))
        records_group = c.fetchall()
        # Поиск в базе данных для преподавателя
        c.execute('SELECT * FROM timetable WHERE "Name" LIKE ?', (request_mod,))
        records_teacher = c.fetchall()
        c.close()
        conn.close()
        # Перебор полученных значений
        response = ''
        # Если нашлась хоть одна группа
        if records_group is not None:
            for row in records_group:
                if response.find(row["Group-Utf"]) == -1:
                    response += row["Group-Utf"] + '\n'
        # Если есть хоть один преподаватель
        if records_teacher is not None:
            for row in records_teacher:
                if response.find(row['Name']) == -1:
                    response += row['Name'] + '\n'
        # Если есть хоть одно предположение
        if response:
            logger.log('SQL', 'Suggestions found for request')
            return 'Возможно вы имели ввиду:\n' + response
        else:
            logger.log('SQL', 'No suggestions found for request')
            return False


# Включение и отключение уведомлений об изменениях
def enable_and_disable_notifications(enable: str = None, disable: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming request to enable or disable notifications for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        email_row = c.fetchone()
        if email_row:
            if enable is not None and email_row['notification'] == 1:
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for email <' + email + '> are already enabled')
                return '\nУведомления уже включены'
            elif disable is not None and email_row['notification'] == 0:
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for email <' + email + '> are already disabled')
                return '\nУведомления уже отключены'
            elif enable is not None:
                c.execute('UPDATE email SET notification = ? WHERE email = ?', (1, email))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for email <' + email + '> are enabled')
                return '\nУведомления успешно включены'
            elif disable is not None:
                c.execute('UPDATE email SET notification = ? WHERE email = ?', (0, email))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for email <' + email + '> are disabled')
                return '\nУведомления успешно отключены'
            # Неправильный запрос
            else:
                c.close()
                conn.close()
                logger.error(
                    'Incorrect request to enable or disable lesson time for email = <' + email + '>. Enable = ' + str(
                        enable) + ' disable = ' + str(disable))
                return '\nПроизошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No values found for email <' + email + '>. Skip set notifications')
            return 'Невозможно изменить настройки уведомлений, так как для вас не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming request to enable or disable notifications for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        vk_chat_row = c.fetchone()
        if vk_chat_row:
            if enable is not None and vk_chat_row['notification'] == 1:
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for vk chat <' + vk_id_chat + '> are already enabled')
                return 'Уведомления уже включены'
            elif disable is not None and vk_chat_row['notification'] == 0:
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for vk chat <' + vk_id_chat + '> are already disabled')
                return 'Уведомления уже отключены'
            elif enable is not None:
                c.execute('UPDATE vk_chat SET notification = ? WHERE vk_id = ?', (1, vk_id_chat))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for vk chat <' + vk_id_chat + '> are enabled')
                return 'Уведомления успешно включены'
            elif disable is not None:
                c.execute('UPDATE vk_chat SET notification = ? WHERE vk_id = ?', (0, vk_id_chat))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for vk chat <' + vk_id_chat + '> are disabled')
                return 'Уведомления успешно отключены'
            # Неправильный запрос
            else:
                c.close()
                conn.close()
                logger.error(
                    'Incorrect request to enable or disable lesson time for vk chat = <' + vk_id_chat + '>. Enable = ' + str(
                        enable) + ' disable = ' + str(disable))
                return 'Произошла ошибка при выполнении запроса, пожалуйста, попробуйте позже'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No values found for vk chat <' + vk_id_chat + '>. Skip set notifications')
            return 'Невозможно изменить настройки уведомлений, так как не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming request to enable or disable notifications for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        vk_user_row = c.fetchone()
        if vk_user_row:
            if enable is not None and vk_user_row['notification'] == 1:
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for vk user <' + vk_id_user + '> are already enabled')
                return 'Уведомления уже включены'
            elif disable is not None and vk_user_row['notification'] == 0:
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for vk user <' + vk_id_user + '> are already disabled')
                return 'Уведомления уже отключены'
            elif enable is not None:
                c.execute('UPDATE vk_user SET notification = ? WHERE vk_id = ?', (1, vk_id_user))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for vk user <' + vk_id_user + '> are enabled')
                return 'Уведомления успешно включены'
            elif disable is not None:
                c.execute('UPDATE vk_user SET notification = ? WHERE vk_id = ?', (0, vk_id_user))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Notifications for vk user <' + vk_id_user + '> are disabled')
                return 'Уведомления успешно отключены'
            # Неправильный запрос
            else:
                c.close()
                conn.close()
                logger.error(
                    'Incorrect request to enable or disable lesson time for vk user = <' + vk_id_user + '>. Enable = ' + str(
                        enable) + ' disable = ' + str(disable))
                return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No values found for vk user <' + vk_id_user + '>. Skip set notifications')
            return 'Невозможно изменить настройки уведомлений, так как для вас не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'
    # Telegram
    elif telegram is not None and (email is None and vk_id_chat is None and vk_id_user is None and discord is None):
        logger.log('SQL', f'Incoming request to enable or disable notifications for telegram = <{telegram}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM telegram WHERE telegram_id = ?', (telegram,))
        telegram_row = c.fetchone()
        if telegram_row:
            if enable is not None and telegram_row['notification'] == 1:
                c.close()
                conn.close()
                logger.log('SQL', f'Notifications for telegram <{telegram}> are already enabled')
                return 'Уведомления уже включены'
            elif disable is not None and telegram_row['notification'] == 0:
                c.close()
                conn.close()
                logger.log('SQL', f'Notifications for telegram <{telegram}> are already disabled')
                return 'Уведомления уже отключены'
            elif enable is not None:
                c.execute('UPDATE telegram SET notification = ? WHERE telegram_id = ?', (1, telegram))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', f'Notifications for telegram <{telegram}> are enabled')
                return 'Уведомления успешно включены'
            elif disable is not None:
                c.execute('UPDATE telegram SET notification = ? WHERE telegram_id = ?', (0, telegram))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', f'Notifications for telegram <{telegram}> are disabled')
                return 'Уведомления успешно отключены'
            # Неправильный запрос
            else:
                c.close()
                conn.close()
                logger.error(
                    f'Incorrect request to enable or disable notifications for telegram <{telegram}>. Enable = {str(enable)}, disable = {str(disable)}')
                return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
        else:
            c.close()
            conn.close()
            logger.log('SQL', f'No values found for telegram <{telegram}>. Skip set notifications')
            return 'Невозможно изменить настройки уведомлений, так как для вас не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'
    # Discord
    elif discord is not None and (email is None and vk_id_chat is None and vk_id_user is None and telegram is None):
        logger.log('SQL', f'Incoming request to enable or disable notifications for discord = <{discord}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM discord WHERE discord_id = ?', (discord,))
        discord_row = c.fetchone()
        if discord_row:
            if enable is not None and discord_row['notification'] == 1:
                c.close()
                conn.close()
                logger.log('SQL', f'Notifications for discord <{discord}> are already enabled')
                return 'Уведомления уже включены'
            elif disable is not None and discord_row['notification'] == 0:
                c.close()
                conn.close()
                logger.log('SQL', f'Notifications for discord <{discord}> are already disabled')
                return 'Уведомления уже отключены'
            elif enable is not None:
                c.execute('UPDATE discord SET notification = ? WHERE discord_id = ?', (1, discord))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', f'Notifications for discord <{discord}> are enabled')
                return 'Уведомления успешно включены'
            elif disable is not None:
                c.execute('UPDATE discord SET notification = ? WHERE discord_id = ?', (0, discord))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', f'Notifications for discord <{discord}> are disabled')
                return 'Уведомления успешно отключены'
            # Неправильный запрос
            else:
                c.close()
                conn.close()
                logger.error(
                    f'Incorrect request to enable or disable notifications for discord <{discord}>. Enable = {str(enable)}, disable = {str(disable)}')
                return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
        else:
            c.close()
            conn.close()
            logger.log('SQL', f'No values found for discord <{discord}>. Skip set notifications')
            return 'Невозможно изменить настройки уведомлений, так как для вас не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'
    else:
        logger.error('Incorrect request to enable or disable notifications. Email, vk chat, vk user, telegram  and discord are undefined')
        return '\nПроизошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# Включение и отключение отображения времени занятий в расписании
def enable_and_disable_lesson_time(enable: str = None, disable: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None and telegram is None):
        logger.log('SQL', 'Incoming request to enable or disable lesson time for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        email_row = c.fetchone()
        if email_row:
            if enable is not None and email_row['lesson_time'] == 1:
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for email <' + email + '> already enabled')
                return '\nОтображение времени занятий уже включено'
            elif disable is not None and email_row['lesson_time'] == 0:
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for email <' + email + '> already disabled')
                return '\nОтображение времени занятий уже отключено'
            elif enable is not None:
                c.execute('UPDATE email SET lesson_time = ? WHERE email = ?', (1, email))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for email <' + email + '> are enabled')
                return '\nОтображение времени занятий успешно включено'
            elif disable is not None:
                c.execute('UPDATE email SET lesson_time = ? WHERE email = ?', (0, email))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for email <' + email + '> are disabled')
                return '\nОтображение времени занятий успешно отключено'
            # Неправильный запрос
            else:
                c.close()
                conn.close()
                logger.error(
                    'Incorrect request to enable or disable lesson time for email = <' + email + '>. Enable = ' + str(
                        enable) + ' disable = ' + str(disable))
                return '\nПроизошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No values found for email <' + email + '>. Skip set lesson time')
            return 'Невозможно изменить настройки отображения времени занятий, так как для вас не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None and telegram is None):
        logger.log('SQL', 'Incoming request to enable or disable lesson time for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        vk_chat_row = c.fetchone()
        if vk_chat_row:
            if enable is not None and vk_chat_row['lesson_time'] == 1:
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for vk chat <' + vk_id_chat + '> already enabled')
                return 'Отображение времени занятий уже включено'
            elif disable is not None and vk_chat_row['lesson_time'] == 0:
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for vk chat <' + vk_id_chat + '> already disabled')
                return 'Отображение времени занятий уже отключено'
            elif enable is not None:
                c.execute('UPDATE vk_chat SET lesson_time = ? WHERE vk_id = ?', (1, vk_id_chat))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for vk chat <' + vk_id_chat + '> are enabled')
                return 'Отображение времени занятий успешно включено'
            elif disable is not None:
                c.execute('UPDATE vk_chat SET lesson_time = ? WHERE vk_id = ?', (0, vk_id_chat))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for vk chat <' + vk_id_chat + '> are disabled')
                return 'Отображение времени занятий успешно отключено'
            # Неправильный запрос
            else:
                c.close()
                conn.close()
                logger.error(
                    'Incorrect request to enable or disable lesson time for vk chat = <' + vk_id_chat + '>. Enable = ' + str(
                        enable) + ' disable = ' + str(disable))
                return 'Произошла ошибка при выполнении запроса, пожалуйста, попробуйте позже'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No values found for vk chat <' + vk_id_chat + '>. Skip set lesson time')
            return 'Невозможно изменить настройки отображения времени занятий, так как не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None and telegram is None):
        logger.log('SQL', 'Incoming request to enable or disable lesson time for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        vk_user_row = c.fetchone()
        if vk_user_row:
            if enable is not None and vk_user_row['lesson_time'] == 1:
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for vk user <' + vk_id_user + '> already enabled')
                return 'Отображение времени занятий уже включено'
            elif disable is not None and vk_user_row['lesson_time'] == 0:
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for vk user <' + vk_id_user + '> already disabled')
                return 'Отображение времени занятий уже отключено'
            elif enable is not None:
                c.execute('UPDATE vk_user SET lesson_time = ? WHERE vk_id = ?', (1, vk_id_user))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for vk user <' + vk_id_user + '> are enabled')
                return 'Отображение времени занятий успешно включено'
            elif disable is not None:
                c.execute('UPDATE vk_user SET lesson_time = ? WHERE vk_id = ?', (0, vk_id_user))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'Lesson time for vk user <' + vk_id_user + '> are disabled')
                return 'Отображение времени занятий успешно отключено'
            # Неправильный запрос
            else:
                c.close()
                conn.close()
                logger.error(
                    'Incorrect request to enable or disable lesson time for vk user = <' + vk_id_user + '>. Enable = ' + str(
                        enable) + ' disable = ' + str(disable))
                return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No values found for vk user <' + vk_id_user + '>. Skip set lesson time')
            return 'Невозможно изменить настройки отображения времени занятий, так как для вас не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'
    # Telegram
    elif telegram is not None and (email is None and vk_id_chat is None and vk_id_user is None):
        logger.log('SQL', f'Incoming request to enable or disable lesson time for telegram = <{telegram}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM telegram WHERE telegram_id = ?', (telegram,))
        telegram_row = c.fetchone()
        if telegram_row:
            if enable is not None and telegram_row['lesson_time'] == 1:
                c.close()
                conn.close()
                logger.log('SQL', f'Lesson time for telegram <{telegram}> already enabled')
                return 'Отображение времени занятий уже включено'
            elif disable is not None and telegram_row['lesson_time'] == 0:
                c.close()
                conn.close()
                logger.log('SQL', f'Lesson time for telegram <{telegram}> already disabled')
                return 'Отображение времени занятий уже отключено'
            elif enable is not None:
                c.execute('UPDATE telegram SET lesson_time = ? WHERE telegram_id = ?', (1, telegram))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', f'Lesson time for telegram <{telegram}> are enabled')
                return 'Отображение времени занятий успешно включено'
            elif disable is not None:
                c.execute('UPDATE telegram SET lesson_time = ? WHERE telegram_id = ?', (0, telegram))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', f'Lesson time for telegram <{telegram}> are disabled')
                return 'Отображение времени занятий успешно отключено'
            # Неправильный запрос
            else:
                c.close()
                conn.close()
                logger.error(
                    f'Incorrect request to enable or disable lesson time for telegram = <{telegram}>. Enable = {str(enable)}, disable = {str(disable)}')
                return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
        else:
            c.close()
            conn.close()
            logger.log('SQL', f'No values found for telegram <{telegram}>. Skip set lesson time')
            return 'Невозможно изменить настройки отображения времени занятий, так как для вас не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'
    # Discord
    elif discord is not None and (email is None and vk_id_chat is None and vk_id_user is None and telegram is None):
        logger.log('SQL', f'Incoming request to enable or disable lesson time for discord = <{discord}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM discord WHERE discord_id = ?', (discord,))
        discord_row = c.fetchone()
        if discord_row:
            if enable is not None and discord_row['lesson_time'] == 1:
                c.close()
                conn.close()
                logger.log('SQL', f'Lesson time for discord <{discord}> already enabled')
                return 'Отображение времени занятий уже включено'
            elif disable is not None and discord_row['lesson_time'] == 0:
                c.close()
                conn.close()
                logger.log('SQL', f'Lesson time for discord <{discord}> already disabled')
                return 'Отображение времени занятий уже отключено'
            elif enable is not None:
                c.execute('UPDATE discord SET lesson_time = ? WHERE discord_id = ?', (1, discord))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', f'Lesson time for discord <{discord}> are enabled')
                return 'Отображение времени занятий успешно включено'
            elif disable is not None:
                c.execute('UPDATE discord SET lesson_time = ? WHERE discord_id = ?', (0, discord))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', f'Lesson time for discord <{discord}> are disabled')
                return 'Отображение времени занятий успешно отключено'
            # Неправильный запрос
            else:
                c.close()
                conn.close()
                logger.error(
                    f'Incorrect request to enable or disable lesson time for discord = <{discord}>. Enable = {str(enable)}, disable = {str(disable)}')
                return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'
        else:
            c.close()
            conn.close()
            logger.log('SQL', f'No values found for discord <{discord}>. Skip set lesson time')
            return 'Невозможно изменить настройки отображения времени занятий, так как для вас не найдено сохраненных параметров. Добавьте сначала группу или преподавателя'
    else:
        logger.error('Incorrect request to enable or disable notifications. Email, vk chat, vk user and telegram are undefined')
        return '\nПроизошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# Удаление сохраненных настроек групп и преподов для пользователей
def delete_all_saved_groups_and_teachers(email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming request to delete all saved groups and teachers for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        result = c.fetchone()
        if result:
            if result['group_id'] is not None or result['teacher'] is not None:
                c.execute('UPDATE email SET group_id = ? WHERE email = ?', (None, email))
                c.execute('UPDATE email SET teacher = ? WHERE email = ?', (None, email))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'All saved groups and teachers for email <' + email + '> are deleted')
                return '\nСохраненные группы и преподаватели успешно удалены'
            else:
                logger.log('SQL', 'No saved groups or teachers for email <' + email + '>')
                return '\nНет сохраненных групп или преподавателей для удаления'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No saved settings for email <' + email + '>. Skip delete groups and teachers')
            return '\nНевозможно удалить, так как для вас нет сохраненых параметров. Добавьте сначала группу или преподавателя'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming request to delete all saved groups and teachers for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        result = c.fetchone()
        if result:
            if result['group_id'] is not None or result['teacher'] is not None:
                c.execute('UPDATE vk_chat SET group_id = ? WHERE vk_id = ?', (None, vk_id_chat))
                c.execute('UPDATE vk_chat SET teacher = ? WHERE vk_id = ?', (None, vk_id_chat))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'All saved groups and teachers for vk chat <' + vk_id_chat + '> are deleted')
                return 'Сохраненные группы и преподаватели успешно удалены'
            else:
                logger.log('SQL', 'No saved groups or teachers for vk chat <' + vk_id_chat + '>')
                return 'Нет сохраненных групп или преподавателей для удаления'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No saved groups or teachers for vk chat <' + vk_id_chat + '>')
            return 'Невозможно удалить, так как нет сохраненых параметров. Добавьте сначала группу или преподавателя'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming request to delete all saved groups and teachers for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        result = c.fetchone()
        if result:
            if result['group_id'] is not None or result['teacher'] is not None:
                c.execute('UPDATE vk_user SET group_id = ? WHERE vk_id = ?', (None, vk_id_user))
                c.execute('UPDATE vk_user SET teacher = ? WHERE vk_id = ?', (None, vk_id_user))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', 'All saved groups and teachers for vk user <' + vk_id_user + '> are deleted')
                return 'Сохраненные группы и преподаватели успешно удалены'
            else:
                logger.log('SQL', 'No saved groups or teachers for vk user <' + vk_id_user + '>')
                return 'Нет сохраненных групп или преподавателей для удаления'
        else:
            c.close()
            conn.close()
            logger.log('SQL', 'No saved groups or teachers for vk user <' + vk_id_user + '>')
            return 'Нет сохраненных групп или преподавателей для удаления'
    # Telegram
    elif telegram is not None and (email is None and vk_id_chat is None and vk_id_user is None and discord is None):
        logger.log('SQL', f'Incoming request to delete all saved groups and teachers for telegram = <{telegram}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM telegram WHERE telegram_id = ?', (telegram,))
        result = c.fetchone()
        if result:
            if result['group_id'] is not None or result['teacher'] is not None:
                c.execute('UPDATE telegram SET group_id = ? WHERE telegram_id = ?', (None, telegram))
                c.execute('UPDATE telegram SET teacher = ? WHERE telegram_id = ?', (None, telegram))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', f'All saved groups and teachers for telegram <{telegram}> are deleted')
                return 'Сохраненные группы и преподаватели успешно удалены'
            else:
                logger.log('SQL', f'No saved groups or teachers for telegram <{telegram}>')
                return 'Нет сохраненных групп или преподавателей для удаления'
        else:
            c.close()
            conn.close()
            logger.log('SQL', f'No saved groups or teachers for telegram <{telegram}>')
            return 'Нет сохраненных групп или преподавателей для удаления'
    # Discord
    elif discord is not None and (email is None and vk_id_chat is None and vk_id_user is None and telegram is None):
        logger.log('SQL', f'Incoming request to delete all saved groups and teachers for discord = <{discord}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM discord WHERE discord_id = ?', (discord,))
        result = c.fetchone()
        if result:
            if result['group_id'] is not None or result['teacher'] is not None:
                c.execute('UPDATE discord SET group_id = ? WHERE discord_id = ?', (None, discord))
                c.execute('UPDATE discord SET teacher = ? WHERE discord_id = ?', (None, discord))
                conn.commit()
                c.close()
                conn.close()
                logger.log('SQL', f'All saved groups and teachers for discord <{discord}> are deleted')
                return 'Сохраненные группы и преподаватели успешно удалены'
            else:
                logger.log('SQL', f'No saved groups or teachers for discord <{discord}>')
                return 'Нет сохраненных групп или преподавателей для удаления'
        else:
            c.close()
            conn.close()
            logger.log('SQL', f'No saved groups or teachers for discord <{discord}>')
            return 'Нет сохраненных групп или преподавателей для удаления'
    else:
        logger.error('Incorrect request to delete saved groups and teachers. Email, vk chat, vk user, telegram and discord are undefined')
        return 'Невозможно удалить, так как для вас нет сохраненых параметров. Добавьте сначала группу или преподавателя'


# Отображение текущих настроек
def display_saved_settings(email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming request to display all saved settings for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Нет сохраненных групп и преподавателей\n'
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены преподаватели: ' + teachers_answer + '\n'
            if result['notification'] == 1:
                answer += 'Уведомления включены\n'
            elif result['notification'] == 0:
                answer += 'Уведомления отключены\n'
            if result['lesson_time'] == 1:
                answer += 'Отображение времени занятий включено'
            elif result['lesson_time'] == 0:
                answer += 'Отображение времени занятий отключено'
            logger.log('SQL', 'Display saved settings for email <' + email + '>')
            return answer
        else:
            logger.log('SQL', 'No saved settings for email <' + email + '>')
            return 'Для вас нет сохраненных параметров'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming request to display all saved settings for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Нет сохраненных групп и преподавателей\n'
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены преподаватели: ' + teachers_answer + '\n'
            if result['notification'] == 1:
                answer += 'Уведомления включены\n'
            elif result['notification'] == 0:
                answer += 'Уведомления отключены\n'
            if result['lesson_time'] == 1:
                answer += 'Отображение времени занятий включено'
            elif result['lesson_time'] == 0:
                answer += 'Отображение времени занятий отключено'
            logger.log('SQL', 'Display saved settings for vk chat <' + vk_id_chat + '>')
            return answer
        else:
            logger.log('SQL', 'No saved settings for vk chat <' + vk_id_chat + '>')
            return 'Нет сохраненных параметров'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming request to display all saved settings for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Нет сохраненных групп и преподавателей\n'
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены преподаватели: ' + teachers_answer + '\n'
            if result['notification'] == 1:
                answer += 'Уведомления включены\n'
            elif result['notification'] == 0:
                answer += 'Уведомления отключены\n'
            if result['lesson_time'] == 1:
                answer += 'Отображение времени занятий включено'
            elif result['lesson_time'] == 0:
                answer += 'Отображение времени занятий отключено'
            logger.log('SQL', 'Display saved settings for vk user <' + vk_id_user + '>')
            return answer
        else:
            logger.log('SQL', 'No saved settings for vk user <' + vk_id_user + '>')
            return 'Для вас нет сохраненных параметров'
    # Telegram
    elif telegram is not None and (email is None and vk_id_chat is None and vk_id_user is None and discord is None):
        logger.log('SQL', f'Incoming request to display all saved settings for telegram = <{telegram}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM telegram WHERE telegram_id = ?', (telegram,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Нет сохраненных групп и преподавателей\n'
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены преподаватели: ' + teachers_answer + '\n'
            if result['notification'] == 1:
                answer += 'Уведомления включены\n'
            elif result['notification'] == 0:
                answer += 'Уведомления отключены\n'
            if result['lesson_time'] == 1:
                answer += 'Отображение времени занятий включено'
            elif result['lesson_time'] == 0:
                answer += 'Отображение времени занятий отключено'
            logger.log('SQL', f'Display saved settings for telegram <{telegram}>')
            return answer
        else:
            logger.log('SQL', f'No saved settings for telegram <{telegram}>')
            return 'Для вас нет сохраненных параметров'
    # Discord
    elif discord is not None and (email is None and vk_id_chat is None and vk_id_user is None and telegram is None):
        logger.log('SQL', f'Incoming request to display all saved settings for discord = <{discord}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM discord WHERE discord_id = ?', (discord,))
        result = c.fetchone()
        c.close()
        conn.close()
        if result is not None:
            answer = ''
            if result['group_id'] is None and result['teacher'] is None:
                answer += 'Нет сохраненных групп и преподавателей\n'
            if result['group_id'] is not None:
                groups = str(result['group_id']).split('\n')
                groups_answer = ''
                for i in groups:
                    groups_answer += i + ' '
                answer += 'Сохранены группы: ' + groups_answer + '\n'
            if result['teacher'] is not None:
                teachers = str(result['teacher']).split('\n')
                teachers_answer = ''
                for i in teachers:
                    teachers_answer += i + ' '
                answer += 'Сохранены преподаватели: ' + teachers_answer + '\n'
            if result['notification'] == 1:
                answer += 'Уведомления включены\n'
            elif result['notification'] == 0:
                answer += 'Уведомления отключены\n'
            if result['lesson_time'] == 1:
                answer += 'Отображение времени занятий включено'
            elif result['lesson_time'] == 0:
                answer += 'Отображение времени занятий отключено'
            logger.log('SQL', f'Display saved settings for discord <{discord}>')
            return answer
        else:
            logger.log('SQL', f'No saved settings for discord <{discord}>')
            return 'Для вас нет сохраненных параметров'
    else:
        logger.error('Incorrect request to delete saved groups and teachers. Email, vk chat, vk user, telegram and discord are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# Получение расписания для пользователя
def getting_timetable_for_user(next: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming timetable request for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        email_row = c.fetchone()
        c.close()
        conn.close()
        if email_row:
            teachers_answer = ''
            groups_answer = ''
            lesson_time = None
            if email_row['lesson_time'] == 0:
                lesson_time = 'NO'
            if email_row['group_id'] is None and email_row['teacher'] is None:
                logger.log('SQL', 'No saved groups or teachers for email <' + email + '>')
                return 'Нет сохраненных групп или преподавателей для отправки расписания'
            if email_row['teacher'] is not None:
                teachers = str(email_row['teacher'])
                teachers = teachers.replace('\r', '')
                teachers = teachers.split('\n')
                for i in teachers:
                    teachers_answer += timetable(teacher=str(i), next=next, lesson_time=lesson_time) + '\n'
            if email_row['group_id'] is not None:
                groups = str(email_row['group_id'])
                groups = groups.replace('\r', '')
                groups = groups.split('\n')
                for i in groups:
                    groups_answer += timetable(group_id=str(i), next=next, lesson_time=lesson_time) + '\n'
            logger.log('SQL', 'Response to timetable request for email <' + email + '>')
            return teachers_answer + groups_answer
        else:
            logger.log('SQL', 'No saved groups or teachers for email <' + email + '>')
            return 'Нет сохраненных групп или преподавателей для отправки расписания'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming timetable request for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        vk_chat_row = c.fetchone()
        c.close()
        conn.close()
        if vk_chat_row is not None:
            teachers_answer = ''
            groups_answer = ''
            lesson_time = None
            if vk_chat_row['lesson_time'] == 0:
                lesson_time = 'NO'
            if vk_chat_row['group_id'] is None and vk_chat_row['teacher'] is None:
                logger.log('SQL', 'No saved groups or teachers for vk chat <' + vk_id_chat + '>')
                return 'Нет сохраненных групп или преподавателей для отправки расписания'
            if vk_chat_row['teacher'] is not None:
                teachers = str(vk_chat_row['teacher'])
                teachers = teachers.replace('\r', '')
                teachers = teachers.split('\n')
                for i in teachers:
                    teachers_answer += 'Cut\n' + timetable(teacher=str(i), next=next, lesson_time=lesson_time) + '\n'
            if vk_chat_row['group_id'] is not None:
                groups = str(vk_chat_row['group_id'])
                groups = groups.replace('\r', '')
                groups = groups.split('\n')
                for i in groups:
                    groups_answer += 'Cut\n' + timetable(group_id=str(i), next=next, lesson_time=lesson_time) + '\n'
            logger.log('SQL', 'Response to timetable request for vk chat <' + vk_id_chat + '>')
            return teachers_answer + groups_answer
        else:
            logger.log('SQL', 'No saved groups or teachers for vk chat <' + vk_id_chat + '>')
            return 'Нет сохраненных групп или преподавателей для отправки расписания'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming timetable request for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        vk_user_row = c.fetchone()
        c.close()
        conn.close()
        if vk_user_row is not None:
            teachers_answer = ''
            groups_answer = ''
            lesson_time = None
            if vk_user_row['lesson_time'] == 0:
                lesson_time = 'NO'
            if vk_user_row['group_id'] is None and vk_user_row['teacher'] is None:
                logger.log('SQL', 'No saved groups or teachers for vk user <' + vk_id_user + '>')
                return 'Нет сохраненных групп или преподавателей для отправки расписания'
            if vk_user_row['teacher'] is not None:
                teachers = str(vk_user_row['teacher'])
                teachers = teachers.replace('\r', '')
                teachers = teachers.split('\n')
                for i in teachers:
                    teachers_answer += 'Cut\n' + timetable(teacher=str(i), next=next, lesson_time=lesson_time) + '\n'
            if vk_user_row['group_id'] is not None:
                groups = str(vk_user_row['group_id'])
                groups = groups.replace('\r', '')
                groups = groups.split('\n')
                for i in groups:
                    groups_answer += 'Cut\n' + timetable(group_id=str(i), next=next, lesson_time=lesson_time) + '\n'
            logger.log('SQL', 'Response to timetable request for vk user <' + vk_id_user + '>')
            return teachers_answer + groups_answer
        else:
            logger.log('SQL', 'No saved groups or teachers for vk user <' + vk_id_user + '>')
            return 'Нет сохраненных групп или преподавателей для отправки расписания'
    # Telegram
    elif telegram is not None and (email is None and vk_id_chat is None and vk_id_user is None and discord is None):
        logger.log('SQL', f'Incoming timetable request for telegram = <{telegram}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM telegram WHERE telegram_id = ?', (telegram,))
        telegram_row = c.fetchone()
        c.close()
        conn.close()
        if telegram_row is not None:
            teachers_answer = ''
            groups_answer = ''
            lesson_time = None
            if telegram_row['lesson_time'] == 0:
                lesson_time = 'NO'
            if telegram_row['group_id'] is None and telegram_row['teacher'] is None:
                logger.log('SQL', f'No saved groups or teachers for telegram <{telegram}>')
                return 'Нет сохраненных групп или преподавателей для отправки расписания'
            if telegram_row['teacher'] is not None:
                teachers = str(telegram_row['teacher'])
                teachers = teachers.replace('\r', '')
                teachers = teachers.split('\n')
                for i in teachers:
                    teachers_answer += 'Cut\n' + timetable(teacher=str(i), next=next, lesson_time=lesson_time) + '\n'
            if telegram_row['group_id'] is not None:
                groups = str(telegram_row['group_id'])
                groups = groups.replace('\r', '')
                groups = groups.split('\n')
                for i in groups:
                    groups_answer += 'Cut\n' + timetable(group_id=str(i), next=next, lesson_time=lesson_time) + '\n'
            logger.log('SQL', f'Response to timetable request for telegram <{telegram}>')
            return teachers_answer + groups_answer
        else:
            logger.log('SQL', f'No saved groups or teachers for telegram <{telegram}>')
            return 'Нет сохраненных групп или преподавателей для отправки расписания'
    # Discord
    elif discord is not None and (email is None and vk_id_chat is None and vk_id_user is None and telegram is None):
        logger.log('SQL', f'Incoming timetable request for discord = <{discord}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM discord WHERE discord_id = ?', (discord,))
        discord_row = c.fetchone()
        c.close()
        conn.close()
        if discord_row is not None:
            teachers_answer = ''
            groups_answer = ''
            lesson_time = None
            if discord_row['lesson_time'] == 0:
                lesson_time = 'NO'
            if discord_row['group_id'] is None and discord_row['teacher'] is None:
                logger.log('SQL', f'No saved groups or teachers for discord <{discord}>')
                return 'Нет сохраненных групп или преподавателей для отправки расписания'
            if discord_row['teacher'] is not None:
                teachers = str(discord_row['teacher'])
                teachers = teachers.replace('\r', '')
                teachers = teachers.split('\n')
                for i in teachers:
                    teachers_answer += 'Cut\n' + timetable(teacher=str(i), next=next, lesson_time=lesson_time) + '\n'
            if discord_row['group_id'] is not None:
                groups = str(discord_row['group_id'])
                groups = groups.replace('\r', '')
                groups = groups.split('\n')
                for i in groups:
                    groups_answer += 'Cut\n' + timetable(group_id=str(i), next=next, lesson_time=lesson_time) + '\n'
            logger.log('SQL', f'Response to timetable request for discord <{discord}>')
            return teachers_answer + groups_answer
        else:
            logger.log('SQL', f'No saved groups or teachers for discord <{discord}>')
            return 'Нет сохраненных групп или преподавателей для отправки расписания'
    else:
        logger.error('Incorrect timetable request. Email, vk chat, vk user, telegram  and discord are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# Получение учебной нагрузки для пользователя
def getting_workload_for_user(next: str = None, email: str = None, vk_id_chat: str = None, vk_id_user: str = None, telegram: str = None, discord: str = None):
    # Обработка email
    if email is not None and (vk_id_chat is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming workload request for email = <' + email + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM email WHERE email = ?', (email,))
        email_row = c.fetchone()
        c.close()
        conn.close()
        if email_row:
            teachers_answer = ''
            if email_row['teacher'] is None:
                logger.log('SQL', 'No saved teachers for email <' + email + '>')
                return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
            if email_row['teacher'] is not None:
                teachers = str(email_row['teacher'])
                teachers = teachers.replace('\r', '')
                teachers = teachers.split('\n')
                for i in teachers:
                    teachers_answer += workload(teacher=str(i), next=next) + '\n'
            logger.log('SQL', 'Response to workload request for email <' + email + '>')
            return teachers_answer
        else:
            logger.log('SQL', 'No saved teachers for email <' + email + '>')
            return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
    # Обработка vk chat
    elif vk_id_chat is not None and (email is None and vk_id_user is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming workload request for vk chat = <' + vk_id_chat + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_chat WHERE vk_id = ?', (vk_id_chat,))
        vk_chat_row = c.fetchone()
        c.close()
        conn.close()
        if vk_chat_row is not None:
            teachers_answer = ''
            if vk_chat_row['teacher'] is None:
                logger.log('SQL', 'No saved teachers for vk chat <' + vk_id_chat + '>')
                return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
            if vk_chat_row['teacher'] is not None:
                teachers = str(vk_chat_row['teacher'])
                teachers = teachers.replace('\r', '')
                teachers = teachers.split('\n')
                for i in teachers:
                    teachers_answer += 'Cut\n' + workload(teacher=str(i), next=next) + '\n'
            logger.log('SQL', 'Response to workload request for vk chat <' + vk_id_chat + '>')
            return teachers_answer
        else:
            logger.log('SQL', 'No saved teachers for vk chat <' + vk_id_chat + '>')
            return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
    # Обработка vk user
    elif vk_id_user is not None and (email is None and vk_id_chat is None and telegram is None and discord is None):
        logger.log('SQL', 'Incoming workload request for vk user = <' + vk_id_user + '>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vk_user WHERE vk_id = ?', (vk_id_user,))
        vk_user_row = c.fetchone()
        c.close()
        conn.close()
        if vk_user_row is not None:
            teachers_answer = ''
            if vk_user_row['teacher'] is None:
                logger.log('SQL', 'No saved teachers for vk user <' + vk_id_user + '>')
                return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
            if vk_user_row['teacher'] is not None:
                teachers = str(vk_user_row['teacher'])
                teachers = teachers.replace('\r', '')
                teachers = teachers.split('\n')
                for i in teachers:
                    teachers_answer += 'Cut\n' + workload(teacher=str(i), next=next) + '\n'
            logger.log('SQL', 'Response to workload request for vk user <' + vk_id_user + '>')
            return teachers_answer
        else:
            logger.log('SQL', 'No saved teachers for vk user <' + vk_id_user + '>')
            return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
    # Telegram
    elif telegram is not None and (email is None and vk_id_chat is None and vk_id_user is None and discord is None):
        logger.log('SQL', f'Incoming workload request for telegram = <{telegram}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM telegram WHERE telegram_id = ?', (telegram,))
        telegram_row = c.fetchone()
        c.close()
        conn.close()
        if telegram_row is not None:
            teachers_answer = ''
            if telegram_row['teacher'] is None:
                logger.log('SQL', f'No saved teachers for telegram <{telegram}>')
                return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
            if telegram_row['teacher'] is not None:
                teachers = str(telegram_row['teacher'])
                teachers = teachers.replace('\r', '')
                teachers = teachers.split('\n')
                for i in teachers:
                    teachers_answer += 'Cut\n' + workload(teacher=str(i), next=next) + '\n'
            logger.log('SQL', f'Response to workload request for telegram <{telegram}>')
            return teachers_answer
        else:
            logger.log('SQL', f'No saved teachers for telegram <{telegram}>')
            return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
    # Discord
    elif discord is not None and (email is None and vk_id_chat is None and vk_id_user is None and telegram is None):
        logger.log('SQL', f'Incoming workload request for discord = <{discord}>')
        conn = connection_to_sql('user_settings.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM discord WHERE discord_id = ?', (discord,))
        discord_row = c.fetchone()
        c.close()
        conn.close()
        if discord_row is not None:
            teachers_answer = ''
            if discord_row['teacher'] is None:
                logger.log('SQL', f'No saved teachers for discord <{discord}>')
                return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
            if discord_row['teacher'] is not None:
                teachers = str(discord_row['teacher'])
                teachers = teachers.replace('\r', '')
                teachers = teachers.split('\n')
                for i in teachers:
                    teachers_answer += 'Cut\n' + workload(teacher=str(i), next=next) + '\n'
            logger.log('SQL', f'Response to workload request for discord <{discord}>')
            return teachers_answer
        else:
            logger.log('SQL', f'No saved teachers for discord <{discord}>')
            return 'Нет сохраненных преподавателей для отправки учебной нагрузки'
    else:
        logger.error('Incorrect workload request. Email, vk chat, vk user, telegram  and discord are undefined')
        return 'Произошла ошибка при выполнении вашего запроса, пожалуйста, попробуйте позже'


# with logger.catch():
#     getting_the_difference_in_sql_files_and_sending_them()
