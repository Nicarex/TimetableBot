import configparser
from vk_api import VkApi
from vk_api.utils import get_random_id
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from timetable import timetable
from dbf import connect_to_dbf
from sql_db import read_values_all_vk, add_values_vk, if_record_exist_vk, delete_values_all_vk

config = configparser.ConfigParser()
config.read("config.ini")
GROUP_ID = config['VK']['group_id']
GROUP_TOKEN = config['VK']['group_token']
API_VERSION = '5.120'


# Кнопки
keyboard_default_chat = VkKeyboard(one_time=False, inline=True)
keyboard_default_chat.add_button('Расписание на текущую неделю', color=VkKeyboardColor.PRIMARY)
keyboard_default_chat.add_line()
keyboard_default_chat.add_button('Расписание на следующую неделю', color=VkKeyboardColor.POSITIVE)
keyboard_default_chat.add_line()
keyboard_default_chat.add_openlink_button('Расписание на сайте', link="https://amchs.ru/students/raspisanie/")
keyboard_default_chat.add_line()
keyboard_default_chat.add_button('Настройки', color=VkKeyboardColor.NEGATIVE)

keyboard_default_peer = VkKeyboard(one_time=False)
keyboard_default_peer.add_button('Текущая неделя', color=VkKeyboardColor.PRIMARY)
keyboard_default_peer.add_button('Следующая неделя', color=VkKeyboardColor.POSITIVE)
keyboard_default_peer.add_line()
keyboard_default_peer.add_openlink_button('Расписание на сайте', link="https://amchs.ru/students/raspisanie/")
keyboard_default_peer.add_button('Настройки', color=VkKeyboardColor.NEGATIVE)

keyboard_settings_peer = VkKeyboard(one_time=False)
keyboard_settings_peer.add_button('Настроить отправку', color=VkKeyboardColor.PRIMARY)
keyboard_settings_peer.add_openlink_button('Открыть инструкцию', link="https://vk.link/bot_agz")
keyboard_settings_peer.add_line()
keyboard_settings_peer.add_button('Удалить параметры групп и преподавателей', color=VkKeyboardColor.POSITIVE)
keyboard_settings_peer.add_line()
keyboard_settings_peer.add_button('Вернуться назад', color=VkKeyboardColor.NEGATIVE)

keyboard_settings_chat = VkKeyboard(one_time=False, inline=True)
keyboard_settings_chat.add_button('Настроить отправку', color=VkKeyboardColor.PRIMARY)
keyboard_settings_chat.add_line()
keyboard_settings_chat.add_openlink_button('Открыть инструкцию', link="https://vk.link/bot_agz")
keyboard_settings_chat.add_line()
keyboard_settings_chat.add_button('Удалить параметры групп и преподавателей', color=VkKeyboardColor.POSITIVE)
keyboard_settings_chat.add_line()
keyboard_settings_chat.add_button('Вернуться назад', color=VkKeyboardColor.NEGATIVE)


# Инициализация
vk_session = VkApi(token=GROUP_TOKEN, api_version=API_VERSION)
vk = vk_session.get_api()
long_poll = VkBotLongPoll(vk_session, group_id=GROUP_ID)


# Сообщение в беседу
def write_msg_chat(event, message, keyboard=None):
    if keyboard is not None:
        keyboard = keyboard.get_keyboard()
    vk.messages.send(chat_id=int(event.chat_id), message=message, keyboard=keyboard, random_id=get_random_id())


# Сообщение в чат с пользователем
def write_msg_user(event, message, keyboard=None):
    if keyboard is not None:
        keyboard = keyboard.get_keyboard()
    vk.messages.send(peer_id=int(event.obj.message['peer_id']), message=message, keyboard=keyboard, random_id=get_random_id())


# Имя и фамилия человека
def get_user_info(event):
    user_get = vk.users.get(user_ids=event.obj.message['from_id'])[0]
    return user_get['first_name'] + " " + user_get['last_name']


# Возвращает к заданному значению +1
def plus_one(number):
    if number == 1:
        return 2
    elif number == 2:
        return 3
    elif number == 3:
        return 4
    elif number == 4:
        return 5


# Добавление параметров в БД
def search_and_add_to_db(event, user=None, chat=None):
    text = event.obj.message['text']
    answer = ''
    # Для корректного отображения сообщения
    q = []
    for record in connect_to_dbf():
        # Если это пользователь
        if user is not None and chat is None:
            # Проверка на группу
            if not text.find(record['GROUP']) == -1 and q.count(record['GROUP']) == 0:
                q.append(record['GROUP'])
                add_values_vk('vk_user_student', value=str(record['GROUP']), user_id_event=event)
                answer = answer + ' ' + record['GROUP']
            # Проверка на фамилию
            elif not text.find(record['NAME']) == -1 and q.count(record['NAME']) == 0:
                q.append(record['NAME'])
                add_values_vk('vk_user_teacher', value=str(record['NAME']), user_id_event=event)
                answer = answer + ' ' + record['NAME']
        # Если это беседа
        elif chat is not None and user is None:
            # Проверка на группу
            if not text.find(record['GROUP']) == -1 and q != record['GROUP']:
                q = record['GROUP']
                add_values_vk('vk_chat_student', value=str(record['GROUP']), chat_id_event=event)
                answer = answer + ' ' + record['GROUP']
            # Проверка на фамилию
            elif not text.find(record['NAME']) == -1 and q != record['NAME']:
                q = record['NAME']
                add_values_vk('vk_chat_teacher', value=str(record['NAME']), chat_id_event=event)
                answer = answer + ' ' + record['NAME']
    if answer != '':
        if user is not None and chat is None:
            write_msg_user(event=event, message='Добавлены следующие параметры:' + answer, keyboard=keyboard_default_peer)
            return 'YES'
        elif chat is not None and user is None:
            write_msg_chat(event=event, message='Добавлены следующие параметры:' + answer, keyboard=keyboard_default_chat)
            return 'YES'
    else:
        return None


# Основной цикл
def vk_start_server():
    print("\nServer started")
    message_typing = {}
    while True:
        try:
            for event in long_poll.listen():
                # print(event)
                # Беседа
                if event.type == VkBotEventType.MESSAGE_NEW and event.from_chat:
                    request = event.obj.message['text'].lower()
                    print('[VK] CHAT message: from ' + get_user_info(event) + ' text: ' + request)
                    if "расписание на текущую неделю" in request:
                        if if_record_exist_vk(event, chat='YES') == 'YES':
                            for i in read_values_all_vk('vk_chat_student', chat_id_event=event):
                                write_msg_chat(event, message=timetable(i['group_id']), keyboard=keyboard_default_chat)
                            for i in read_values_all_vk('vk_chat_teacher', chat_id_event=event):
                                write_msg_chat(event, message=timetable(group='', teacher=i['teacher_id']),
                                               keyboard=keyboard_default_chat)
                        if if_record_exist_vk(event, chat='YES') == 'NO':
                            write_msg_chat(event, message='Не найдено настроенных групп или преподавателей\nРекомендую обратиться к инструкции:\nhttps://vk.link/bot_agz',
                                           keyboard=keyboard_default_chat)
                    elif "расписание на следующую неделю" in request:
                        if if_record_exist_vk(event, chat='YES') == 'YES':
                            for i in read_values_all_vk('vk_chat_student', chat_id_event=event):
                                write_msg_chat(event, message=timetable(i['group_id'], next='YES'), keyboard=keyboard_default_chat)
                            for i in read_values_all_vk('vk_chat_teacher', chat_id_event=event):
                                write_msg_chat(event, message=timetable(group='', teacher=i['teacher_id'], next='YES'),
                                               keyboard=keyboard_default_chat)
                        if if_record_exist_vk(event, chat='YES') == 'NO':
                            write_msg_chat(event,
                                           message='Не найдено настроенных групп или преподавателей\nРекомендую обратиться к инструкции:\nhttps://vk.link/bot_agz',
                                           keyboard=keyboard_default_chat)
                    elif not request.find('@all') == -1:
                        print('@all detected!')
                    elif "настройки" in request:
                        if if_record_exist_vk(event, chat='YES') == 'YES':
                            temp = 'Установлены следующие настройки:'
                            for i in read_values_all_vk('vk_chat_student', chat_id_event=event):
                                temp = temp + ' ' + i['group_id']
                            for i in read_values_all_vk('vk_chat_teacher', chat_id_event=event):
                                temp = temp + ' ' + i['teacher_id']
                            write_msg_chat(event, message=temp, keyboard=keyboard_settings_chat)
                        elif if_record_exist_vk(event, chat='YES') == 'NO':
                            write_msg_chat(event, message='Нет настроенных групп или преподавателей', keyboard=keyboard_settings_chat)
                    elif "удалить параметры групп и преподавателей" in request:
                        if if_record_exist_vk(event, chat='YES') == 'YES':
                            delete_values_all_vk('vk_chat_student', chat_id_event=event)
                            delete_values_all_vk('vk_chat_teacher', chat_id_event=event)
                            write_msg_chat(event, message='Сохраненные группы и преподаватели успешно удалены', keyboard=keyboard_settings_chat)
                        elif if_record_exist_vk(event, chat='NO') == 'NO':
                            write_msg_chat(event, message='Нечего удалять, так как для вас нет настроенных групп или преподавателей', keyboard=keyboard_settings_chat)
                    elif "настроить отправку" in request:
                        write_msg_chat(event, message='Ведутся технические работы\nПопробуйте позже', keyboard=keyboard_settings_chat)
                    elif "вернуться назад" in request:
                        write_msg_chat(event, message='Хорошо', keyboard=keyboard_default_chat)
                    elif "расписание на сайте" in request:
                        write_msg_chat(event, message='https://amchs.ru/students/raspisanie/', keyboard=keyboard_default_chat)
                    elif not str(event.obj.message).find('chat_invite_user') == -1:
                        print('\nBot invited to chat')
                        write_msg_chat(event, 'Всем привет!\nЯ - бот, который помогает с расписанием\nДля вызова пропишите /чтоугодно или @bot_agz\nВНИМАНИЕ! Бот находится в стадии бета-тестирования')
                    else:
                        if search_and_add_to_db(event, chat='YES') is None:
                            write_msg_chat(event, message='👇👇👇', keyboard=keyboard_default_chat)

                # Личные сообщения
                elif event.type == VkBotEventType.MESSAGE_NEW and event.from_user:
                    # Текст сообщения
                    request = event.obj.message['text'].lower()
                    # Сообщение в вывод
                    print('[VK] USER message: from ' + get_user_info(event) + ' text: ' + request)
                    if "начать" in request:
                        write_msg_user(event, message='Привет!\nЯ - бот, который помогает с расписанием\nНастоятельно рекомендую ознакомиться с инструкцией:\nhttps://vk.link/bot_agz\n\nАхтунг! Бот находится в стадии бета-тестирования', keyboard=keyboard_default_peer)
                    elif "текущая неделя" in request:
                        if if_record_exist_vk(event, user='YES') == 'YES':
                            for i in read_values_all_vk('vk_user_student', user_id_event=event):
                                write_msg_user(event, message=timetable(i['group_id']), keyboard=keyboard_default_peer)
                            for i in read_values_all_vk('vk_user_teacher', user_id_event=event):
                                write_msg_user(event, message=timetable(group='', teacher=i['teacher_id']), keyboard=keyboard_default_peer)
                        elif if_record_exist_vk(event, user='YES') == 'NO':
                            write_msg_user(event, message='Для вас не найдено настроенных групп или преподавателей\nРекомендую обратиться к инструкции:\nhttps://vk.link/bot_agz', keyboard=keyboard_default_peer)
                    elif "следующая неделя" in request:
                        if if_record_exist_vk(event, user='YES') == 'YES':
                            for i in read_values_all_vk('vk_user_student', user_id_event=event):
                                write_msg_user(event, message=timetable(i['group_id'], next='YES'), keyboard=keyboard_default_peer)
                            for i in read_values_all_vk('vk_user_teacher', user_id_event=event):
                                write_msg_user(event, message=timetable(group='', teacher=i['teacher_id'], next='YES'), keyboard=keyboard_default_peer)
                        if if_record_exist_vk(event, user='YES') == 'NO':
                            write_msg_user(event, message='Для вас не найдено настроенных групп или преподавателей\nРекомендую обратиться к инструкции:\nhttps://vk.link/bot_agz', keyboard=keyboard_default_peer)
                    elif "настройки" in request:
                        if if_record_exist_vk(event, user='YES') == 'YES':
                            temp = 'Для вас установлены следующие настройки:'
                            for i in read_values_all_vk('vk_user_student', user_id_event=event):
                                temp = temp + ' ' + i['group_id']
                            for i in read_values_all_vk('vk_user_teacher', user_id_event=event):
                                temp = temp + ' ' + i['teacher_id']
                            write_msg_user(event, message=temp, keyboard=keyboard_settings_peer)
                        elif if_record_exist_vk(event, user='YES') == 'NO':
                            write_msg_user(event, message='Нет настроенных групп или преподавателей', keyboard=keyboard_settings_peer)
                    elif "удалить параметры групп и преподавателей" in request:
                        if if_record_exist_vk(event, user='YES') == 'YES':
                            delete_values_all_vk('vk_user_student', user_id_event=event)
                            delete_values_all_vk('vk_user_teacher', user_id_event=event)
                            write_msg_user(event, message='Сохраненные группы и преподаватели успешно удалены', keyboard=keyboard_settings_peer)
                        elif if_record_exist_vk(event, user='NO') == 'NO':
                            write_msg_user(event, message='Нечего удалять, так как для вас нет настроенных групп или преподавателей', keyboard=keyboard_settings_peer)
                    elif "настроить отправку" in request:
                        write_msg_user(event, message='Ведутся технические работы\nПопробуйте позже', keyboard=keyboard_settings_peer)
                    elif "вернуться назад" in request:
                        write_msg_user(event, message='Хорошо', keyboard=keyboard_default_peer)
                    elif "расписание на сайте" in request:
                        write_msg_user(event, message='https://amchs.ru/students/raspisanie/', keyboard=keyboard_default_peer)
                    else:
                        if search_and_add_to_db(event, user='YES') is None:
                            write_msg_user(event, message='Такой команды не найдено', keyboard=keyboard_default_peer)
        except:
            continue
