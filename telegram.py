import aiogram.utils.exceptions
import aiohttp.client_exceptions
from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils.exceptions import BotBlocked
from other import read_config
from sql_db import getting_timetable_for_user, search_group_and_teacher_in_request, display_saved_settings, enable_and_disable_notifications, enable_and_disable_lesson_time, delete_all_saved_groups_and_teachers
from logger import logger
from calendar_timetable import show_calendar_url_to_user
import socket
import time

token = read_config(telegram='YES')
bot = Bot(token=token)
dp = Dispatcher(bot)

KEYBOARD_USER_MAIN = types.ReplyKeyboardMarkup(resize_keyboard=True)
buttons_user_main_1 = ['Текущая неделя', 'Следующая неделя']
KEYBOARD_USER_MAIN.add(*buttons_user_main_1)
buttons_user_main_2 = ['Календарь', 'Настройки']
KEYBOARD_USER_MAIN.add(*buttons_user_main_2)

KEYBOARD_USER_SETTINGS = types.ReplyKeyboardMarkup(resize_keyboard=True)
buttons_user_settings = ['Инструкция', 'Об авторе', 'Настроить уведомления об изменениях', 'Настроить отображение времени занятий', 'Удалить параметры групп и преподавателей', 'Вернуться назад']
KEYBOARD_USER_SETTINGS.add(buttons_user_settings[0], buttons_user_settings[1])
KEYBOARD_USER_SETTINGS.row()
KEYBOARD_USER_SETTINGS.add(buttons_user_settings[2])
KEYBOARD_USER_SETTINGS.row()
KEYBOARD_USER_SETTINGS.add(buttons_user_settings[3])
KEYBOARD_USER_SETTINGS.row()
KEYBOARD_USER_SETTINGS.add(buttons_user_settings[4])
KEYBOARD_USER_SETTINGS.row()
KEYBOARD_USER_SETTINGS.add(buttons_user_settings[5])

KEYBOARD_USER_CALENDAR = types.ReplyKeyboardMarkup(resize_keyboard=True)
buttons_user_calendars = ['Да, я прочитал инструкцию', 'Инструкция', 'Вернуться назад']
KEYBOARD_USER_CALENDAR.add(buttons_user_calendars[0])
KEYBOARD_USER_CALENDAR.row()
KEYBOARD_USER_CALENDAR.add(buttons_user_calendars[1])
KEYBOARD_USER_CALENDAR.row()
KEYBOARD_USER_CALENDAR.add(buttons_user_calendars[2])

KEYBOARD_USER_NOTI = types.ReplyKeyboardMarkup(resize_keyboard=True)
buttons_user_noti = ['Включить уведомления', 'Выключить уведомления', 'Вернуться назад']
KEYBOARD_USER_NOTI.add(buttons_user_noti[0])
KEYBOARD_USER_NOTI.row()
KEYBOARD_USER_NOTI.add(buttons_user_noti[1])
KEYBOARD_USER_NOTI.row()
KEYBOARD_USER_NOTI.add(buttons_user_noti[2])

KEYBOARD_USER_LESSON_TIME = types.ReplyKeyboardMarkup(resize_keyboard=True)
buttons_user_lesson_time = ['Включить отображение времени занятий', 'Выключить отображение времени занятий', 'Вернуться назад']
KEYBOARD_USER_LESSON_TIME.add(buttons_user_lesson_time[0])
KEYBOARD_USER_LESSON_TIME.row()
KEYBOARD_USER_LESSON_TIME.add(buttons_user_lesson_time[1])
KEYBOARD_USER_LESSON_TIME.row()
KEYBOARD_USER_LESSON_TIME.add(buttons_user_lesson_time[2])


@dp.message_handler(text=['/start', '/Start', '/Начать', '/начать', 'start', 'Start', 'Начать', 'начать'])
async def echo(message: types.Message):
    logger.log('TELEGRAM', f'Message <{str(message.text)}>, chat <{str(message.chat.id)}>')
    await message.answer(f"Привет, {str(message.from_user.username)}!\nЯ - бот, который помогает с расписанием\nНастоятельно рекомендую ознакомиться с инструкцией:\nhttps://nicarex.github.io/timetablebot-site/", reply_markup=KEYBOARD_USER_MAIN)


@dp.message_handler(text=["Текущая неделя", "/текущая", '/текущая неделя', '/Текущая неделя', 'текущая неделя', 'Текущая'])
async def timetable_now(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = str(getting_timetable_for_user(telegram=str(message.chat.id))).split('Cut\n')
    for i in answer:
        if i != '':
            if answer[-1] == i:
                await message.answer('➡ ' + i, reply_markup=KEYBOARD_USER_MAIN)
            else:
                await message.answer('➡ ' + i)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Следующая неделя", "/следующая", '/следующая неделя', '/Следующая неделя', 'следующая неделя', 'Следующая'])
async def timetable_next(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = str(getting_timetable_for_user(next='YES', telegram=str(message.chat.id))).split('Cut\n')
    for i in answer:
        if i != '':
            if answer[-1] == i:
                await message.answer('➡ ' + i, reply_markup=KEYBOARD_USER_MAIN)
            else:
                await message.answer('➡ ' + i)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Настройки", '/настройки', '/Настройки', 'настройки'])
async def settings(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = display_saved_settings(telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Календарь", '/календарь', '/Календарь', 'календарь'])
async def calendar_settings(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('❗️ВНИМАНИЕ❗️\nДля успешного использования календаря НУЖНО прочитать инструкцию, иначе вы просто не поймете, что делать с полученными ссылками', reply_markup=KEYBOARD_USER_CALENDAR)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Да, я прочитал инструкцию", '/Да, я прочитал инструкцию', '/да, я прочитал инструкцию', 'да, я прочитал инструкцию'])
async def calendar_response(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('Ваш запрос выполняется, пожалуйста, подождите...', reply_markup=KEYBOARD_USER_MAIN)
    answer = show_calendar_url_to_user(telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_MAIN)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Настроить уведомления об изменениях", '/Настроить уведомления об изменениях', '/настроить уведомления об изменениях', 'настроить уведомления об изменениях'])
async def noti_settings(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('Выберите параметры:', reply_markup=KEYBOARD_USER_NOTI)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Включить уведомления", "/Включить уведомления", "/включить уведомления", "включить уведомления"])
async def noti_enable(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = enable_and_disable_notifications(enable='YES', telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Выключить уведомления", "/Выключить уведомления", "/выключить уведомления", "выключить уведомления"])
async def noti_disable(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = enable_and_disable_notifications(disable='YES', telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Настроить отображение времени занятий", "/Настроить отображение времени занятий", "/настроить отображение времени занятий", "настроить отображение времени занятий"])
async def lesson_time_settings(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('Выберите параметры:', reply_markup=KEYBOARD_USER_LESSON_TIME)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Включить отображение времени занятий", "/Включить отображение времени занятий", "/включить отображение времени занятий", "включить отображение времени занятий"])
async def lesson_time_enable(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = enable_and_disable_lesson_time(enable='YES', telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Выключить отображение времени занятий", "/Выключить отображение времени занятий", "/выключить отображение времени занятий", "выключить отображение времени занятий"])
async def lesson_time_disable(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = enable_and_disable_lesson_time(disable='YES', telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Удалить параметры групп и преподавателей", "/Удалить параметры групп и преподавателей", "/удалить параметры групп и преподавателей", "удалить параметры групп и преподавателей"])
async def delete_saved_settings(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = delete_all_saved_groups_and_teachers(telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_MAIN)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Вернуться назад", "/Вернуться назад", "/вернуться назад", "вернуться назад"])
async def back(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('Хорошо', reply_markup=KEYBOARD_USER_MAIN)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Об авторе", "/Об авторе", "/об авторе", "об авторе"])
async def about_author(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('Автор бота:\nстудент 307 группы\nНасонов Никита\n\nКонтакты:\nVK: https://vk.com/nicarex\nEmail: my.profile.protect@gmail.com', reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler(text=["Инструкция", "/Инструкция", "/инструкция", "инструкция"])
async def instruction_link(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('https://nicarex.github.io/timetablebot-site/', reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.message_handler()
async def search_in_request(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    search_response = search_group_and_teacher_in_request(request=str(message.text), telegram=str(message.chat.id))
    if search_response is False:
        answer = 'Нет распознанных групп или преподавателей, если вы их вводили\n\nНапоминаю, что для успешного добавления параметров нужно придерживаться строгих правил ввода, которые можно посмотреть в инструкции\n'
    else:
        answer = search_response
    await message.answer(answer, reply_markup=KEYBOARD_USER_MAIN)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@dp.errors_handler(exception=BotBlocked)
async def error_bot_blocked(update: types.Update, exception: BotBlocked):
    logger.log('TELEGRAM', f'Bot has been blocked, message: {str(update)}')
    return True


# Запуск сервера
@logger.catch
def start_telegram_server():
    try:
        logger.log('TELEGRAM', 'Telegram server started...')
        executor.start_polling(dp, skip_updates=True)
    except KeyboardInterrupt:
        logger.log('TELEGRAM', 'Telegram server has been stopped by Ctrl+C')
        return False
    except aiohttp.client_exceptions.ClientConnectionError:
        logger.log('TELEGRAM', 'Exception - ClientConnectionError, wait 10 sec...')
        time.sleep(10)
    except aiogram.utils.exceptions.NetworkError:
        logger.log('TELEGRAM', 'Exception - NetworkError, wait 10 sec...')
        time.sleep(10)
    except socket.gaierror:
        logger.log('TELEGRAM', 'Exception - SocketGaierror, wait 10 sec...')
        time.sleep(10)
