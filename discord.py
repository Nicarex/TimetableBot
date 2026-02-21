import asyncio
import functools
import threading
import nextcord
from nextcord import Interaction, SlashOption
from nextcord.ext import commands
from other import read_config, connection_to_sql
from sql_db import getting_timetable_for_user, getting_workload_for_user, search_group_and_teacher_in_request, display_saved_settings, enable_and_disable_notifications, enable_and_disable_lesson_time, delete_all_saved_groups_and_teachers, _get_notifiable_users_with_subs, _collect_notification_messages_normalized
from logger import logger
import sqlite3
from calendar_timetable import show_calendar_url_to_user
from constants import URL_INSTRUCTIONS, AUTHOR_INFO, DISCORD_ADMIN_USERNAME, MESSAGE_PREFIX, MESSAGE_SPLIT_SENTINEL
from messaging import split_response


async def run_sync(func, *args, **kwargs):
    """Запускает синхронную функцию в thread pool, не блокируя event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))


intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)


@bot.slash_command(description="Начальное сообщение")
async def start(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    await interaction.response.send_message(f"Привет!\nЯ - бот, который помогает с расписанием\nНастоятельно рекомендую ознакомиться с инструкцией:\n{URL_INSTRUCTIONS}")
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Расписание на текущую неделю")
async def current_week(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    parts = split_response(await run_sync(getting_timetable_for_user, discord=str(interaction.channel_id)))
    for i, part in enumerate(parts):
        if i == 0:
            await interaction.response.send_message(part)
        else:
            await interaction.send(part)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Расписание на следующую неделю")
async def next_week(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    parts = split_response(await run_sync(getting_timetable_for_user, next='YES', discord=str(interaction.channel_id)))
    for i, part in enumerate(parts):
        if i == 0:
            await interaction.response.send_message(part)
        else:
            await interaction.send(part)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Просмотр текущих настроек")
async def settings(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    answer = await run_sync(display_saved_settings, discord=str(interaction.channel_id))
    await interaction.response.send_message(answer)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Получение ссылок на календарь")
async def calendar(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    answer = await run_sync(show_calendar_url_to_user, discord=str(interaction.channel_id))
    await interaction.response.send_message(answer)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Настройка отображения времени занятий в расписании")
async def lesson_time(
    interaction: Interaction,
    values: str = SlashOption(description="yes - включить, no - отключить", required=False),
):
    logger.log('DISCORD', f'Request message: "{str(values)}" from: <{str(interaction.channel_id)}>')
    if not values:
        await interaction.response.send_message("Не передано значение", ephemeral=True)
    else:
        if values.find('yes') != -1:
            answer = await run_sync(enable_and_disable_lesson_time, enable='YES', discord=str(interaction.channel_id))
            await interaction.response.send_message(answer)
        elif values.find('no') != -1:
            answer = await run_sync(enable_and_disable_lesson_time, disable='YES', discord=str(interaction.channel_id))
            await interaction.response.send_message(answer)
        else:
            await interaction.response.send_message('Неизвестный параметр')
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(name='delete_settings', description='Удаление сохраненных групп и преподавателей')
async def delete_settings(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    answer = await run_sync(delete_all_saved_groups_and_teachers, discord=str(interaction.channel_id))
    await interaction.response.send_message(answer)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Настройка уведомлений об изменениях в расписании")
async def notifications(
    interaction: Interaction,
    values: str = SlashOption(description="yes - включить, no - отключить", required=False),
):
    logger.log('DISCORD', f'Request message: "{str(values)}" from: <{str(interaction.channel_id)}>')
    if not values:
        await interaction.response.send_message("Не передано значение", ephemeral=True)
    else:
        if values.find('yes') != -1:
            answer = await run_sync(enable_and_disable_notifications, enable='YES', discord=str(interaction.channel_id))
            await interaction.response.send_message(answer)
        elif values.find('no') != -1:
            answer = await run_sync(enable_and_disable_notifications, disable='YES', discord=str(interaction.channel_id))
            await interaction.response.send_message(answer)
        else:
            await interaction.response.send_message('Неизвестный параметр')
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Учебная нагрузка на текущий месяц")
async def workload(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    parts = split_response(await run_sync(getting_workload_for_user, discord=str(interaction.channel_id)))
    for i, part in enumerate(parts):
        if i == 0:
            await interaction.response.send_message(part)
        else:
            await interaction.send(part)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Учебная нагрузка на следующий месяц")
async def workload_next(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    parts = split_response(await run_sync(getting_workload_for_user, next='YES', discord=str(interaction.channel_id)))
    for i, part in enumerate(parts):
        if i == 0:
            await interaction.response.send_message(part)
        else:
            await interaction.send(part)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(name='about', description="Об авторе")
async def about(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    await interaction.response.send_message(AUTHOR_INFO)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(name='help', description="Отображении ссылки на инструкцию")
async def help_message(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    await interaction.response.send_message(f"Инструкция: {URL_INSTRUCTIONS}")
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Добавление группы или преподавателя")
async def add(
    interaction: Interaction,
    values: str = SlashOption(description="Введите значения", required=False),
):
    logger.log('DISCORD', f'Request message: "{values}" from: <{str(interaction.channel_id)}>')
    if not values:
        await interaction.response.send_message("Не передано значение", ephemeral=True)
    else:
        search_response = await run_sync(search_group_and_teacher_in_request, request=str(values), discord=str(interaction.channel_id))
        if search_response is False:
            await interaction.response.send_message('Нет распознанных групп или преподавателей')
        else:
            await interaction.response.send_message(search_response)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.command(pass_context=True)
async def broadcast(ctx, *, msg):
    if str(ctx.author) != DISCORD_ADMIN_USERNAME:
        return True
    logger.log('DISCORD', 'Try to send broadcast messages')
    # Подключение к пользовательской базе данных
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    users = c.execute("SELECT * FROM users WHERE platform = 'discord' AND notification = 1").fetchall()
    c.close()
    conn.close()
    for user in users:
        try:
            channel = bot.get_channel(int(user['platform_id']))
            await channel.send(msg)
        except Exception as exc:
            logger.log('DISCORD', f'Error happened while try to send broadcast message to channel <{user["platform_id"]}>')
        finally:
            logger.log('DISCORD', f'Sent broadcast message to channel <{user["platform_id"]}>')


_bot_ready_event = threading.Event()


@bot.event
async def on_ready():
    _bot_ready_event.set()
    logger.log('DISCORD', f'Discord bot connected as {bot.user}')


async def _send_notifications_discord_async(group_list_current_week: list, group_list_next_week: list,
                                             teacher_list_current_week: list, teacher_list_next_week: list):
    """Рассылает Discord-уведомления через уже запущенный бот."""
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    users = _get_notifiable_users_with_subs(c, 'discord')
    c.close()
    conn.close()
    for user in users:
        messages = _collect_notification_messages_normalized(
            user, user['teachers'], user['groups'],
            group_list_current_week, group_list_next_week,
            teacher_list_current_week, teacher_list_next_week)
        channel_id = user['platform_id']
        for msg_text, tt in messages:
            try:
                channel = bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(MESSAGE_PREFIX + msg_text)
                    for part in tt.split(MESSAGE_SPLIT_SENTINEL):
                        if part:
                            await channel.send(part)
                else:
                    logger.log('DISCORD', f'Channel {channel_id} not found, skipping notification')
            except Exception as e:
                logger.log('DISCORD', f'Error sending notification to channel {channel_id}: {e}')


def _notification_listener(notification_queue):
    """Фоновый поток: ждёт готовности бота, затем слушает очередь и рассылает Discord-уведомления."""
    _bot_ready_event.wait()
    logger.log('DISCORD', 'Notification listener ready (bot is connected)')
    while True:
        try:
            event = notification_queue.get()
            logger.log('DISCORD', 'Received notification event from queue')
            future = asyncio.run_coroutine_threadsafe(
                _send_notifications_discord_async(**event), bot.loop)
            future.result()
            logger.log('DISCORD', 'Successfully sent Discord notifications from queue event')
        except Exception as e:
            logger.error(f'Error in Discord notification listener: {e}')


# Запуск сервера
@logger.catch
def start_discord_server(notification_queue=None):
    if notification_queue is not None:
        t = threading.Thread(target=_notification_listener, args=(notification_queue,), daemon=True)
        t.start()
        logger.log('DISCORD', 'Notification listener thread started')
    try:
        logger.log('DISCORD', 'Discord server started...')
        bot.run(read_config(discord='YES'))
    except KeyboardInterrupt:
        logger.log('DISCORD', 'DISCORD server has been stopped by Ctrl+C')
        return False
