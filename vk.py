import configparser
from vk_api import VkApi
from vk_api.utils import get_random_id
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from timetable import timetable
from dbf import connect_to_dbf
import sql_db

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
keyboard_default_peer.add_button('Расписание на текущую неделю', color=VkKeyboardColor.PRIMARY)
keyboard_default_peer.add_button('Расписание на следующую неделю', color=VkKeyboardColor.POSITIVE)
keyboard_default_peer.add_line()
keyboard_default_peer.add_openlink_button('Расписание на сайте', link="https://amchs.ru/students/raspisanie/")
keyboard_default_peer.add_button('Настройки', color=VkKeyboardColor.NEGATIVE)


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


# Основной цикл
def vk_start_server():
    print("\nServer started")
    message_typing = {}
    while True:
        try:
            for event in long_poll.listen():
                print(event)
                # Беседа
                if event.type == VkBotEventType.MESSAGE_NEW and event.from_chat:
                    request = event.obj.message['text'].lower()
                    print('[VK] CHAT message: from ' + get_user_info(event) + ' text: ' + request)
                    if "расписание на текущую неделю" in request:
                        write_msg_chat(event, 'Ведутся технические работы')
                    elif "расписание на следующую неделю" in request:
                        write_msg_chat(event, 'Ведутся технические работы')
                    elif not request.find('@all') == -1:
                        print('@all detected!')
                    elif not str(event.obj.message).find('chat_invite_user') == -1:
                        print('\nBot invited to chat')
                        write_msg_chat(event, 'Всем привет!\nЯ - бот, который помогает с расписанием\nДля вызова пропишите /чтоугодно или @bot_agz\nВНИМАНИЕ! Бот находится в стадии бета-тестирования')
                    else:
                        write_msg_chat(event, message='👇👇👇', keyboard=keyboard_default_chat)
                # Личные сообщения
                elif event.type == VkBotEventType.MESSAGE_NEW and event.from_user:
                    request = event.obj.message['text'].lower()
                    print('[VK] USER message: from ' + get_user_info(event) + ' text: ' + request)
                    if "расписание на текущую неделю" in request:
                        write_msg_user(event, 'Ведутся технические работы')
                    elif "расписание на следующую неделю" in request:
                        write_msg_user(event, 'Ведутся технические работы')
                    elif request.find('@all') != -1:
                        write_msg_user(event, 'Зачем? Это не беседа, если что')
                    else:
                        write_msg_user(event, message='Нет такой команды', keyboard=keyboard_default_peer)
                # Если человек долго печатает, то ему отправляется сообщение с инструкцией
                if event.type == VkBotEventType.MESSAGE_TYPING_STATE:
                    if message_typing.get(int(event.object['from_id'])):
                        message_typing.update(
                            {int(event.object['from_id']): plus_one(message_typing.get(int(event.object['from_id'])))})
                    else:
                        message_typing.update({int(event.object['from_id']): 1})
                    for user_id, count in message_typing.items():
                        if count == 4:
                            vk.messages.send(peer_id=user_id, message='Я вижу вы что-то долго печатаете\nЕсли что, вот наш сайт с инструкцией:\nhttps://vk.link/bot_agz', random_id=get_random_id())
        except KeyboardInterrupt:
            print('Successfully stopped')
        # except requests.exceptions.ReadTimeout as timeout:
        #     continue


vk_start_server()
