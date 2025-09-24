import aiogram.exceptions
import aiohttp.client_exceptions
from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError
from aiogram import Router
from other import read_config
from sql_db import getting_timetable_for_user, search_group_and_teacher_in_request, display_saved_settings, enable_and_disable_notifications, enable_and_disable_lesson_time, delete_all_saved_groups_and_teachers
from logger import logger
from calendar_timetable import show_calendar_url_to_user
import socket
import time

token = read_config(telegram='YES')
bot = Bot(token=token)
dp = Dispatcher()
router = Router()

KEYBOARD_USER_MAIN = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text='Текущая неделя'), types.KeyboardButton(text='Следующая неделя')],
        [types.KeyboardButton(text='Календарь'), types.KeyboardButton(text='Настройки')]
    ],
    resize_keyboard=True
)

KEYBOARD_USER_SETTINGS = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text='Инструкция'), types.KeyboardButton(text='Об авторе')],
        [types.KeyboardButton(text='Настроить уведомления об изменениях')],
        [types.KeyboardButton(text='Настроить отображение времени занятий')],
        [types.KeyboardButton(text='Удалить параметры групп и преподавателей')],
        [types.KeyboardButton(text='Вернуться назад')]
    ],
    resize_keyboard=True
)

KEYBOARD_USER_CALENDAR = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text='Да, я прочитал инструкцию')],
        [types.KeyboardButton(text='Инструкция')],
        [types.KeyboardButton(text='Вернуться назад')]
    ],
    resize_keyboard=True
)

KEYBOARD_USER_NOTI = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text='Включить уведомления')],
        [types.KeyboardButton(text='Выключить уведомления')],
        [types.KeyboardButton(text='Вернуться назад')]
    ],
    resize_keyboard=True
)

KEYBOARD_USER_LESSON_TIME = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text='Включить отображение времени занятий')],
        [types.KeyboardButton(text='Выключить отображение времени занятий')],
        [types.KeyboardButton(text='Вернуться назад')]
    ],
    resize_keyboard=True
)


@router.message(lambda message: message.text in ['/start', '/Start', '/Начать', '/начать', 'start', 'Start', 'Начать', 'начать'])
async def echo(message: types.Message):
    logger.log('TELEGRAM', f'Message <{str(message.text)}>, chat <{str(message.chat.id)}>')
    await message.answer(f"Привет, {str(message.from_user.username)}!\nЯ - бот, который помогает с расписанием\nНастоятельно рекомендую ознакомиться с инструкцией:\nhttps://nicarex.github.io/timetablebot-site/", reply_markup=KEYBOARD_USER_MAIN)


@router.message(lambda message: message.text in ["Текущая неделя", "/текущая", '/текущая неделя', '/Текущая неделя', 'текущая неделя', 'Текущая'])
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


@router.message(lambda message: message.text in ["Следующая неделя", "/следующая", '/следующая неделя', '/Следующая неделя', 'следующая неделя', 'Следующая'])
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


@router.message(lambda message: message.text in ["Настройки", '/настройки', '/Настройки', 'настройки'])
async def settings(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = display_saved_settings(telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Календарь", '/календарь', '/Календарь', 'календарь'])
async def calendar_settings(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('❗️ВНИМАНИЕ❗️\nДля успешного использования календаря НУЖНО прочитать инструкцию, иначе вы просто не поймете, что делать с полученными ссылками', reply_markup=KEYBOARD_USER_CALENDAR)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Да, я прочитал инструкцию", '/Да, я прочитал инструкцию', '/да, я прочитал инструкцию', 'да, я прочитал инструкцию'])
async def calendar_response(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('Ваш запрос выполняется, пожалуйста, подождите...', reply_markup=KEYBOARD_USER_MAIN)
    answer = show_calendar_url_to_user(telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_MAIN)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Настроить уведомления об изменениях", '/Настроить уведомления об изменениях', '/настроить уведомления об изменениях', 'настроить уведомления об изменениях'])
async def noti_settings(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('Выберите параметры:', reply_markup=KEYBOARD_USER_NOTI)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Включить уведомления", "/Включить уведомления", "/включить уведомления", "включить уведомления"])
async def noti_enable(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = enable_and_disable_notifications(enable='YES', telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Выключить уведомления", "/Выключить уведомления", "/выключить уведомления", "выключить уведомления"])
async def noti_disable(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = enable_and_disable_notifications(disable='YES', telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Настроить отображение времени занятий", "/Настроить отображение времени занятий", "/настроить отображение времени занятий", "настроить отображение времени занятий"])
async def lesson_time_settings(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('Выберите параметры:', reply_markup=KEYBOARD_USER_LESSON_TIME)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Включить отображение времени занятий", "/Включить отображение времени занятий", "/включить отображение времени занятий", "включить отображение времени занятий"])
async def lesson_time_enable(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = enable_and_disable_lesson_time(enable='YES', telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Выключить отображение времени занятий", "/Выключить отображение времени занятий", "/выключить отображение времени занятий", "выключить отображение времени занятий"])
async def lesson_time_disable(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = enable_and_disable_lesson_time(disable='YES', telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Удалить параметры групп и преподавателей", "/Удалить параметры групп и преподавателей", "/удалить параметры групп и преподавателей", "удалить параметры групп и преподавателей"])
async def delete_saved_settings(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    answer = delete_all_saved_groups_and_teachers(telegram=str(message.chat.id))
    await message.answer(answer, reply_markup=KEYBOARD_USER_MAIN)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Вернуться назад", "/Вернуться назад", "/вернуться назад", "вернуться назад"])
async def back(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('Хорошо', reply_markup=KEYBOARD_USER_MAIN)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Об авторе", "/Об авторе", "/об авторе", "об авторе"])
async def about_author(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('Автор бота:\nстудент 307 группы\nНасонов Никита\n\nКонтакты:\nVK: https://vk.com/nicarex\nEmail: my.profile.protect@gmail.com', reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message(lambda message: message.text in ["Инструкция", "/Инструкция", "/инструкция", "инструкция"])
async def instruction_link(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    await message.answer('https://nicarex.github.io/timetablebot-site/', reply_markup=KEYBOARD_USER_SETTINGS)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')


@router.message()
async def search_in_request(message: types.Message):
    logger.log('TELEGRAM', f'Request message: "{str(message.text)}" from: <{str(message.chat.id)}>')
    search_response = search_group_and_teacher_in_request(request=str(message.text), telegram=str(message.chat.id))
    if search_response is False:
        answer = 'Нет распознанных групп или преподавателей, если вы их вводили\n\nНапоминаю, что для успешного добавления параметров нужно придерживаться строгих правил ввода, которые можно посмотреть в инструкции\n'
    else:
        answer = search_response
    await message.answer(answer, reply_markup=KEYBOARD_USER_MAIN)
    logger.log('TELEGRAM', f'Response to message from: <{str(message.chat.id)}>')



async def error_bot_blocked(*args, **kwargs):
    """Flexible error handler for aiogram error middleware.

    Aiogram may call error handlers with different signatures depending on
    the middleware/version (for example, sometimes only the exception is
    passed). Accept arbitrary args/kwargs and extract an update and an
    exception when possible so the handler never raises TypeError.
    """
    update = None
    exception = None

    # Try to find exception in kwargs
    if 'exception' in kwargs:
        exception = kwargs.get('exception')

    # Try to find update in kwargs
    if 'update' in kwargs:
        update = kwargs.get('update')

    # If not found in kwargs, inspect positional args
    if exception is None or update is None:
        for arg in args:
            # Prefer aiogram Update for update
            try:
                from aiogram.types import Update
                if update is None and isinstance(arg, Update):
                    update = arg
                    continue
            except Exception:
                pass

            # Pick first Exception-like object as exception
            if exception is None and isinstance(arg, BaseException):
                exception = arg

    logger.log('TELEGRAM', f'Bot error handler triggered, update: {str(update)}, exception: {str(exception)}')
    return True



# Запуск сервера для aiogram 3.x
import asyncio

@logger.catch
def start_telegram_server():
    async def main():
        try:
            logger.log('TELEGRAM', 'Telegram server started...')
            dp.include_router(router)
            dp.errors.register(error_bot_blocked)
            await dp.start_polling(bot)
        except KeyboardInterrupt:
            logger.log('TELEGRAM', 'Telegram server has been stopped by Ctrl+C')
            return False
        except aiohttp.client_exceptions.ClientConnectionError:
            logger.log('TELEGRAM', 'Exception - ClientConnectionError, wait 10 sec...')
            time.sleep(10)
        except TelegramNetworkError:
            logger.log('TELEGRAM', 'Exception - NetworkError, wait 10 sec...')
            time.sleep(10)
        except socket.gaierror:
            logger.log('TELEGRAM', 'Exception - SocketGaierror, wait 10 sec...')
            time.sleep(10)
    asyncio.run(main())
