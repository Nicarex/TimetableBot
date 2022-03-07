from nextcord import Interaction, SlashOption
from nextcord.ext import commands
from other import read_config, connection_to_sql
from sql_db import getting_timetable_for_user, search_group_and_teacher_in_request, display_saved_settings, enable_and_disable_lesson_time, delete_all_saved_groups_and_teachers
from logger import logger
import sqlite3
from calendar_timetable import show_calendar_url_to_user


bot = commands.Bot(command_prefix="/")


@bot.slash_command(description="Начальное сообщение")
async def start(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    await interaction.response.send_message(f"Привет!\nЯ - бот, который помогает с расписанием\nНастоятельно рекомендую ознакомиться с инструкцией:\nhttps://nicarex.github.io/timetablebot-site/")
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Расписание на текущую неделю")
async def current_week(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    answer = str(getting_timetable_for_user(discord=str(interaction.channel_id))).split('Cut\n')
    for i in answer:
        if i != '':
            if answer[0] != i:
                await interaction.send('➡ ' + i)
            else:
                await interaction.response.send_message('➡ ' + i)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Расписание на следующую неделю")
async def next_week(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    answer = str(getting_timetable_for_user(next='YES', discord=str(interaction.channel_id))).split('Cut\n')
    for i in answer:
        if i != '':
            if answer[0] != i:
                await interaction.send('➡ ' + i)
            else:
                await interaction.response.send_message('➡ ' + i)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Просмотр текущих настроек")
async def settings(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    answer = display_saved_settings(discord=str(interaction.channel_id))
    await interaction.response.send_message(answer)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(description="Получение ссылок на календарь")
async def calendar(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    answer = show_calendar_url_to_user(discord=str(interaction.channel_id))
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
            answer = enable_and_disable_lesson_time(enable='YES', discord=str(interaction.channel_id))
            await interaction.response.send_message(answer)
        elif values.find('no') != -1:
            answer = enable_and_disable_lesson_time(disable='YES', discord=str(interaction.channel_id))
            await interaction.response.send_message(answer)
        else:
            await interaction.response.send_message('Неизвестный параметр')
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(name='delete_settings', description='Удаление сохраненных групп и преподавателей')
async def delete_settings(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    answer = delete_all_saved_groups_and_teachers(discord=str(interaction.channel_id))
    await interaction.response.send_message(answer)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(name='about', description="Об авторе")
async def about(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    await interaction.response.send_message('Автор бота:\nстудент 307 группы\nНасонов Никита\n\nКонтакты:\nVK: https://vk.com/nicarex\nEmail: my.profile.protect@gmail.com')
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.slash_command(name='help', description="Отображении ссылки на инструкцию")
async def help_message(interaction: Interaction):
    logger.log('DISCORD', f'Request message from: <{str(interaction.channel_id)}>')
    await interaction.response.send_message("Инструкция: https://nicarex.github.io/timetablebot-site/")
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
        search_response = search_group_and_teacher_in_request(request=str(values), discord=str(interaction.channel_id))
        if search_response is False:
            await interaction.response.send_message('Нет распознанных групп или преподавателей')
        else:
            await interaction.response.send_message(search_response)
    logger.log('DISCORD', f'Response to message from: <{str(interaction.channel_id)}>')


@bot.command(pass_context=True)
async def broadcast(ctx, *, msg):
    if str(ctx.author) != 'Nicare#6529':
        return True
    logger.log('DISCORD', 'Try to send broadcast messages')
    # Подключение к пользовательской базе данных
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    users = c.execute('SELECT * FROM discord WHERE notification = 1').fetchall()
    c.close()
    conn.close()
    for user in users:
        try:
            channel = bot.get_channel(int(user['discord_id']))
            await channel.send(msg)
        except:
            logger.log('DISCORD', f'Error happened while try to send broadcast message to channel <{user["discord_id"]}>')
        finally:
            logger.log('DISCORD', f'Sent broadcast message to channel <{user["discord_id"]}>')


# Запуск сервера
@logger.catch
def start_discord_server():
    try:
        logger.log('DISCORD', 'Discord server started...')
        bot.run(read_config(discord='YES'))
    except KeyboardInterrupt:
        logger.log('DISCORD', 'DISCORD server has been stopped by Ctrl+C')
        return False
