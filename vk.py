import asyncio.exceptions
import aiohttp.client_exceptions
import random
import time
from logger import logger
from vkbottle import GroupEventType, GroupTypes, Keyboard, Text, VKAPIError, KeyboardButtonColor, OpenLink
from vkbottle.bot import Bot, Message
from other import read_config
from calendar_timetable import show_calendar_url_to_user
from sql_db import search_group_and_teacher_in_request, display_saved_settings, delete_all_saved_groups_and_teachers, getting_timetable_for_user, enable_and_disable_notifications, enable_and_disable_lesson_time, getting_workload_for_user


group_token = read_config(vk='YES')
bot = Bot(token=group_token)


KEYBOARD_USER_MAIN = (
    Keyboard(one_time=False, inline=False)
    .add(Text("Текущая неделя"), color=KeyboardButtonColor.PRIMARY)
    .add(Text("Следующая неделя"), color=KeyboardButtonColor.POSITIVE)
    .row()
    .add(Text("Календарь"), color=KeyboardButtonColor.SECONDARY)
    .add(Text("Настройки"), color=KeyboardButtonColor.NEGATIVE)
    .get_json()
)

KEYBOARD_USER_SETTINGS = (
    Keyboard(one_time=False, inline=False)
    .add(OpenLink(label='Инструкция', link='https://nicarex.github.io/timetablebot-site/'))
    .add(Text('Об авторе'), color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Text('Настроить уведомления об изменениях'), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text('Настроить отображение времени занятий'), color=KeyboardButtonColor.POSITIVE)
    .row()
    .add(Text('Удалить параметры групп и преподавателей'), color=KeyboardButtonColor.NEGATIVE)
    .row()
    .add(Text('Вернуться назад'), color=KeyboardButtonColor.SECONDARY)
    .get_json()
)

KEYBOARD_USER_CALENDAR = (
    Keyboard(one_time=False, inline=False)
    .add(Text('Да, я прочитал(а) инструкцию'), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(OpenLink(label='Инструкция', link='https://nicarex.github.io/timetablebot-site/'))
    .row()
    .add(Text('Вернуться назад'), color=KeyboardButtonColor.NEGATIVE)
    .get_json()
)

KEYBOARD_USER_NOTI = (
    Keyboard(one_time=False, inline=False)
    .add(Text('Включить уведомления'), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text('Выключить уведомления'), color=KeyboardButtonColor.NEGATIVE)
    .row()
    .add(Text('Вернуться назад'), color=KeyboardButtonColor.POSITIVE)
    .get_json()
)

KEYBOARD_USER_LESSON_TIME = (
    Keyboard(one_time=False, inline=False)
    .add(Text('Включить отображение времени занятий'), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text('Выключить отображение времени занятий'), color=KeyboardButtonColor.NEGATIVE)
    .row()
    .add(Text('Вернуться назад'), color=KeyboardButtonColor.POSITIVE)
    .get_json()
)


KEYBOARD_CHAT_MAIN = (
    Keyboard(one_time=False, inline=True)
    .add(Text("Текущая неделя"), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text("Следующая неделя"), color=KeyboardButtonColor.POSITIVE)
    .row()
    .add(Text("Настройки"), color=KeyboardButtonColor.NEGATIVE)
    .get_json()
)

KEYBOARD_CHAT_SETTINGS = (
    Keyboard(one_time=False, inline=True)
    .add(OpenLink(label='Инструкция', link='https://nicarex.github.io/timetablebot-site/'))
    .add(Text('Календарь'), color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Text('Настроить уведомления об изменениях'), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text('Настроить отображение времени занятий'), color=KeyboardButtonColor.POSITIVE)
    .row()
    .add(Text('Удалить параметры групп и преподавателей'), color=KeyboardButtonColor.NEGATIVE)
    .row()
    .add(Text('Об авторе'), color=KeyboardButtonColor.SECONDARY)
    .add(Text('Вернуться назад'), color=KeyboardButtonColor.POSITIVE)
    .get_json()
)

KEYBOARD_CHAT_CALENDAR = (
    Keyboard(one_time=False, inline=True)
    .add(Text('Да, я знаю, что делаю'), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(OpenLink(label='Инструкция', link='https://nicarex.github.io/timetablebot-site/'))
    .row()
    .add(Text('Вернуться назад'), color=KeyboardButtonColor.NEGATIVE)
    .get_json()
)

KEYBOARD_CHAT_NOTI = (
    Keyboard(one_time=False, inline=True)
    .add(Text('Включить уведомления'), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text('Выключить уведомления'), color=KeyboardButtonColor.NEGATIVE)
    .row()
    .add(Text('Вернуться назад'), color=KeyboardButtonColor.POSITIVE)
    .get_json()
)

KEYBOARD_CHAT_LESSON_TIME = (
    Keyboard(one_time=False, inline=True)
    .add(Text('Включить отображение времени занятий'), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text('Выключить отображение времени занятий'), color=KeyboardButtonColor.NEGATIVE)
    .row()
    .add(Text('Вернуться назад'), color=KeyboardButtonColor.POSITIVE)
    .get_json()
)


# Обработка личных сообщений
@bot.on.private_message(text="Текущая неделя")
async def user_timetable_now(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    answer = str(getting_timetable_for_user(vk_id_user=str(message.from_id))).split('Cut\n')
    for i in answer:
        if i != '':
            if answer[-1] == i:
                await message.answer('➡ ' + i, keyboard=KEYBOARD_USER_MAIN)
            else:
                await message.answer('➡ ' + i)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Следующая неделя")
async def user_timetable_next(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    answer = str(getting_timetable_for_user(next='YES', vk_id_user=str(message.from_id))).split('Cut\n')
    for i in answer:
        if i != '':
            if answer[-1] == i:
                await message.answer('➡ ' + i, keyboard=KEYBOARD_USER_MAIN)
            else:
                await message.answer('➡ ' + i)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Учебная нагрузка на текущую неделю")
async def user_work_load(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    answer = str(getting_workload_for_user(vk_id_user=str(message.from_id))).split('Cut\n')
    for i in answer:
        if i != '':
            if answer[-1] == i:
                await message.answer('➡ ' + i, keyboard=KEYBOARD_USER_MAIN)
            else:
                await message.answer('➡ ' + i)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Учебная нагрузка на следующую неделю")
async def user_work_load(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    answer = str(getting_workload_for_user(next='YES', vk_id_user=str(message.from_id))).split('Cut\n')
    for i in answer:
        if i != '':
            if answer[-1] == i:
                await message.answer('➡ ' + i, keyboard=KEYBOARD_USER_MAIN)
            else:
                await message.answer('➡ ' + i)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Начать")
async def user_start_message(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    # noinspection PyTypeChecker
    users_info = await bot.api.users.get(message.from_id)
    await message.answer("Привет, {}!\nЯ - бот, который помогает с расписанием\nНастоятельно рекомендую ознакомиться с инструкцией:\nhttps://nicarex.github.io/timetablebot-site/\n\nАхтунг! Бот находится в стадии бета-тестирования".format(users_info[0].first_name), keyboard=KEYBOARD_USER_MAIN)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Настройки")
async def user_settings(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    answer = display_saved_settings(vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_SETTINGS)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Календарь")
async def user_calendar_settings(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    await message.answer(message='❗️ВНИМАНИЕ❗️\nДля успешного использования календаря НУЖНО прочитать инструкцию, иначе вы просто не поймете, что делать с полученными ссылками.', keyboard=KEYBOARD_USER_CALENDAR)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Да, я прочитал(а) инструкцию")
async def user_calendar_response(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    await message.answer('Ваш запрос выполняется, пожалуйста, подождите...', keyboard=KEYBOARD_USER_MAIN)
    answer = show_calendar_url_to_user(vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_MAIN)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Настроить уведомления об изменениях")
async def user_noti_settings(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    await message.answer('Выберите параметры:', keyboard=KEYBOARD_USER_NOTI)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Включить уведомления")
async def user_noti_enable(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    answer = enable_and_disable_notifications(enable='YES', vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_SETTINGS)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Выключить уведомления")
async def user_noti_disable(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    answer = enable_and_disable_notifications(disable='YES', vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_SETTINGS)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Настроить отображение времени занятий")
async def user_lesson_time_settings(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    await message.answer('Выберите параметры:', keyboard=KEYBOARD_USER_LESSON_TIME)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Включить отображение времени занятий")
async def user_lesson_time_enable(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    answer = enable_and_disable_lesson_time(enable='YES', vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_SETTINGS)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Выключить отображение времени занятий")
async def user_lesson_time_disable(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    answer = enable_and_disable_lesson_time(disable='YES', vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_SETTINGS)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Удалить параметры групп и преподавателей")
async def user_delete_saved_settings(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    answer = delete_all_saved_groups_and_teachers(vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_SETTINGS)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Вернуться назад")
async def user_back(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    await message.answer('Хорошо', keyboard=KEYBOARD_USER_MAIN)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Об авторе")
async def user_about_author(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    await message.answer('Автор бота:\nстудент 307 группы\nНасонов Никита\n\nКонтакты:\nVK: https://vk.com/nicarex\nEmail: my.profile.protect@gmail.com', keyboard=KEYBOARD_USER_SETTINGS)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="Инструкция")
async def user_instruction_link(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    await message.answer('https://nicarex.github.io/timetablebot-site/', keyboard=KEYBOARD_USER_SETTINGS)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


@bot.on.private_message(text="<groups_and_teachers>")
async def user_search_in_request(message: Message, groups_and_teachers: str):
    logger.log('VK', 'Request message: "' + message.text + '" from vk user: "' + str(message.from_id) + '"')
    search_response = search_group_and_teacher_in_request(request=str(groups_and_teachers), vk_id_user=str(message.from_id))
    if search_response is False:
        answer = 'Нет распознанных групп или преподавателей, если вы их вводили\n\nНапоминаю, что для успешного добавления параметров нужно придерживаться строгих правил ввода, которые можно посмотреть в инструкции\n'
    else:
        answer = search_response
    await message.answer(answer, keyboard=KEYBOARD_USER_MAIN)
    logger.log('VK', 'Response to message from vk user: "' + str(message.from_id) + '"')


# Обработка сообщений из бесед
@bot.on.chat_message(text=["Текущая неделя", "/текущая", '/текущая неделя', '/Текущая неделя', 'текущая неделя', 'Текущая'])
async def chat_timetable_now(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    answer = str(getting_timetable_for_user(vk_id_chat=str(message.chat_id))).split('Cut\n')
    for i in answer:
        if i != '':
            if answer[-1] == i:
                await message.answer('➡ ' + i, keyboard=KEYBOARD_CHAT_MAIN)
            else:
                await message.answer('➡ ' + i)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text=["Следующая неделя", "/следующая", '/следующая неделя', '/Следующая неделя', 'следующая неделя', 'Следующая'])
async def chat_timetable_next(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    answer = str(getting_timetable_for_user(next='YES', vk_id_chat=str(message.chat_id))).split('Cut\n')
    for i in answer:
        if i != '':
            if answer[-1] == i:
                await message.answer('➡ ' + i, keyboard=KEYBOARD_CHAT_MAIN)
            else:
                await message.answer('➡ ' + i)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text=["Начать", 'начать', '/начать', '/Начать'])
async def chat_start_message(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    await message.answer("Привет!\nЯ - бот, который помогает с расписанием\nНастоятельно рекомендую ознакомиться с инструкцией:\nhttps://nicarex.github.io/timetablebot-site/\n\nАхтунг! Бот находится в стадии бета-тестирования", keyboard=KEYBOARD_CHAT_MAIN)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text=['Настройки', 'настройки', '/настройки', '/Настройки'])
async def chat_settings(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    answer = display_saved_settings(vk_id_chat=str(message.chat_id))
    await message.answer(message=answer, keyboard=KEYBOARD_CHAT_SETTINGS)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text=["Календарь", 'календарь', '/календарь', '/Календарь'])
async def chat_calendar_settings(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    await message.answer(message='❗️ВНИМАНИЕ❗️\nДля успешного использования календаря НУЖНО прочитать инструкцию, иначе вы просто не поймете, что делать с полученными ссылками.', keyboard=KEYBOARD_CHAT_CALENDAR)
    logger.log('VK', 'Response to message from vk user: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="Да, я знаю, что делаю")
async def chat_calendar_response(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    await message.answer('Запрос выполняется, пожалуйста, подождите...')
    answer = show_calendar_url_to_user(vk_id_chat=str(message.chat_id))
    await message.answer(answer, keyboard=KEYBOARD_CHAT_MAIN)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="Настроить уведомления об изменениях")
async def chat_noti_settings(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    await message.answer('Выберите параметры:', keyboard=KEYBOARD_CHAT_NOTI)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="Включить уведомления")
async def chat_noti_enable(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    answer = enable_and_disable_notifications(enable='YES', vk_id_chat=str(message.chat_id))
    await message.answer(answer, keyboard=KEYBOARD_CHAT_SETTINGS)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="Выключить уведомления")
async def chat_noti_disable(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    answer = enable_and_disable_notifications(disable='YES', vk_id_chat=str(message.chat_id))
    await message.answer(answer, keyboard=KEYBOARD_CHAT_SETTINGS)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="Настроить отображение времени занятий")
async def user_lesson_time_settings(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    await message.answer('Выберите параметры:', keyboard=KEYBOARD_CHAT_LESSON_TIME)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="Включить отображение времени занятий")
async def user_lesson_time_enable(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    answer = enable_and_disable_lesson_time(enable='YES', vk_id_chat=str(message.chat_id))
    await message.answer(answer, keyboard=KEYBOARD_CHAT_SETTINGS)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="Выключить отображение времени занятий")
async def user_lesson_time_disable(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    answer = enable_and_disable_lesson_time(disable='YES', vk_id_chat=str(message.chat_id))
    await message.answer(answer, keyboard=KEYBOARD_CHAT_SETTINGS)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="Удалить параметры групп и преподавателей")
async def chat_delete_saved_settings(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    answer = delete_all_saved_groups_and_teachers(vk_id_chat=str(message.chat_id))
    await message.answer(answer, keyboard=KEYBOARD_CHAT_SETTINGS)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="Вернуться назад")
async def chat_back(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    await message.answer('Хорошо', keyboard=KEYBOARD_CHAT_MAIN)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="Об авторе")
async def chat_about_author(message: Message):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    await message.answer('Автор бота:\nстудент 307 группы\nНасонов Никита\n\nКонтакты:\nVK: https://vk.com/nicarex\nEmail: my.profile.protect@gmail.com', keyboard=KEYBOARD_CHAT_SETTINGS)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message(text="<groups_and_teachers>")
async def chat_search_in_request(message: Message, groups_and_teachers: str):
    logger.log('VK', 'Request message: "' + message.text + '" from vk chat: "' + str(message.chat_id) + '"')
    if str(groups_and_teachers).find('@all') != -1 or str(groups_and_teachers).find('*all') != -1 or str(groups_and_teachers).find('@все') != -1 or str(groups_and_teachers).find('*все') != -1:
        return False
    search_response = search_group_and_teacher_in_request(request=str(groups_and_teachers), vk_id_chat=str(message.chat_id))
    if search_response is False:
        answer = 'Нет распознанных групп или преподавателей, если вы их вводили\n\nНапоминаю, что для успешного добавления параметров нужно придерживаться строгих правил ввода, которые можно посмотреть в инструкции\n'
    else:
        answer = search_response
    await message.answer(answer, keyboard=KEYBOARD_CHAT_MAIN)
    logger.log('VK', 'Response to message from vk chat: "' + str(message.chat_id) + '"')


@bot.on.chat_message()
async def ping(message: Message):
    if str(message.text).find('@all') != -1 or str(message.text).find('*all') != -1 or str(message.text).find('@все') != -1 or str(message.text).find('*все') != -1:
        return False
    answer = 'Выберите параметры'
    await message.answer(answer, keyboard=KEYBOARD_CHAT_MAIN)


# Вступление пользователя в сообщество
@bot.on.raw_event(GroupEventType.GROUP_JOIN, dataclass=GroupTypes.GroupJoin)
async def group_join_handler(event: GroupTypes.GroupJoin):
    try:
        await bot.api.messages.send(
            peer_id=event.object.user_id, message="Спасибо за подписку!", random_id=0)
    except VKAPIError[901]:
        pass


# Запуск сервера
@logger.catch
def start_vk_server():
    logger.log('VK', 'VK server started...')
    try:
        bot.run_forever()
    except KeyboardInterrupt:
        logger.log('VK', 'VK server has been stopped by Ctrl+C')
        return False
    except aiohttp.client_exceptions.ServerDisconnectedError:
        wait_seconds_to_retry = random.randint(1, 10)
        logger.log('VK', f'VK server has been disconnected, wait <{str(wait_seconds_to_retry)}> seconds to retry')
        time.sleep(wait_seconds_to_retry)
    except asyncio.exceptions.TimeoutError:
        wait_seconds_to_retry = random.randint(1, 10)
        logger.log('VK', f'VK server timeout, wait <{str(wait_seconds_to_retry)}> seconds to retry')
        time.sleep(wait_seconds_to_retry)
