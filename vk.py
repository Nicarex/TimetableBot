import configparser
from vk_api import VkApi
from vk_api.utils import get_random_id
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import group307


config = configparser.ConfigParser()
config.read("config.ini")
GROUP_ID = config['VK']['group_id']
GROUP_TOKEN = config['VK']['group_token']
API_VERSION = '5.120'

# Запускаем бот
vk_session = VkApi(token=GROUP_TOKEN, api_version=API_VERSION)
vk = vk_session.get_api()
long_poll = VkBotLongPoll(vk_session, group_id=GROUP_ID)


# Сообщение в беседу
def write_msg_chat(chat_id, message):
    vk.messages.send(chat_id=chat_id, message=message, random_id=get_random_id())


# Сообщение в чат с пользователем
def write_msg_peer(peer_id, message):
    vk.messages.send(peer_id=peer_id, message=message, random_id=get_random_id())


# Имя и фамилия человека
def get_user_info(page_id):
    user_get = vk.users.get(user_ids=page_id)
    user_get = user_get[0]
    first_name = user_get['first_name']
    last_name = user_get['last_name']
    full_name = first_name + " " + last_name
    return full_name


# Клавиатура
keyboard_1_chat = VkKeyboard(one_time=False, inline=True)
keyboard_1_chat.add_button('Расписание на текущую неделю', color=VkKeyboardColor.PRIMARY)
keyboard_1_chat.add_line()
keyboard_1_chat.add_button('Расписание на следующую неделю', color=VkKeyboardColor.POSITIVE)
keyboard_1_chat.add_line()
keyboard_1_chat.add_openlink_button('Расписание на сайте', link="https://amchs.ru/students/raspisanie/")

keyboard_1_peer = VkKeyboard(one_time=False)
keyboard_1_peer.add_button('Расписание на текущую неделю', color=VkKeyboardColor.PRIMARY)
keyboard_1_peer.add_line()
keyboard_1_peer.add_button('Расписание на следующую неделю', color=VkKeyboardColor.POSITIVE)
keyboard_1_peer.add_line()
keyboard_1_peer.add_openlink_button('Расписание на сайте', link="https://amchs.ru/students/raspisanie/")

keyboard_2 = VkKeyboard(one_time=False)
keyboard_2.add_button('На текущую неделю', color=VkKeyboardColor.SECONDARY)
keyboard_2.add_line()
keyboard_2.add_button('На следующую неделю', color=VkKeyboardColor.SECONDARY)

# Основной цикл
print("\nServer started")
while True:
    try:
        for event in long_poll.listen():
            print(event)

            if event.type == VkBotEventType.MESSAGE_NEW and event.from_chat:
                print(event.chat_id)
                request = event.obj.message["text"]
                request = request.lower()
                print('\nNew message:')
                print('For me by:', get_user_info(event.obj.message['from_id']), end=' ')
                print('Text:', request)

                if "расписание на текущую неделю" in request:
                    # write_msg_chat(int(event.chat_id),
                    #                'Работа бота в настоящий момент приостановлена, так как расписание на сайте с '
                    #                'Нового года представлено в виде pdf-файлов, а не Excel')
                    group307.timetable_now()
                    write_msg_chat(int(event.chat_id), "Хай, вот расписание:\n")
                    f = open('timetable.txt')
                    write_msg_chat(int(event.chat_id), f.read())
                elif "расписание на следующую неделю" in request:
                    # write_msg_chat(int(event.chat_id),
                    #                'Работа бота в настоящий момент приостановлена, так как расписание на сайте с '
                    #                'Нового года представлено в виде pdf-файлов, а не Excel')
                    group307.timetable_next()
                    write_msg_chat(int(event.chat_id), "Вот расписание:\n")
                    f = open('timetable.txt')
                    write_msg_chat(int(event.chat_id), f.read())
                # elif "пока" in request:
                #     write_msg_chat(int(event.chat_id), "Пока((")
                elif not request.find('@all') == -1:
                    print('@all detected!')
                elif not str(event.obj.message).find('chat_invite_user') == -1:
                    print('\nBot invited to chat')
                    write_msg_chat(int(event.chat_id),
                                   'Всем привет!\nЯ - бот, который помогает с расписанием\nДля вызова пропишите '
                                   '/чтоугодно или @bot_agz\nВНИМАНИЕ! Бот находится в стадии бета-тестирования')
                else:
                    vk.messages.send(
                        chat_id=int(event.chat_id),
                        random_id=get_random_id(),
                        keyboard=keyboard_1_chat.get_keyboard(),
                        message='👇👇👇')
            elif event.type == VkBotEventType.MESSAGE_NEW and event.from_user:
                print(int(event.object.message['peer_id']))
                request = event.obj.message["text"]
                request = request.lower()
                for_me_by = str(get_user_info(event.obj.message['from_id']))
                print('\nNew message:')
                print('For me by:', get_user_info(event.obj.message['from_id']), end=' ')
                print('Text:', request)
                #                log_write('\nNew message:')
                #                log_write('For me by:', get_user_info(event.obj.message['from_id']), end=' ')
                #                log_write('Text:', request)
                if "расписание на текущую неделю" in request:
                    # write_msg_peer(int(event.object.message['peer_id']),
                    #                'Работа бота в настоящий момент приостановлена, так как расписание на сайте с '
                    #                'Нового года представлено в виде pdf-файлов, а не Excel')
                    group307.timetable_now()
                    write_msg_peer(int(event.object.message['peer_id']), "Хай, вот расписание:\n")
                    f = open('timetable.txt')
                    write_msg_peer(int(event.object.message['peer_id']), f.read())
                elif "расписание на следующую неделю" in request:
                    # write_msg_peer(int(event.object.message['peer_id']),
                    #                'Работа бота в настоящий момент приостановлена, так как расписание на сайте с '
                    #                'Нового года представлено в виде pdf-файлов, а не Excel')
                    group307.timetable_next()
                    write_msg_peer(int(event.object.message['peer_id']), "Хай, вот расписание:\n")
                    f = open('timetable.txt')
                    write_msg_peer(int(event.object.message['peer_id']), f.read())
                # elif "пока" in request:
                #     write_msg_peer(int(event.object.message['peer_id']), "Пока((")
                elif not request.find('@all') == -1:
                    write_msg_peer(int(event.object.message['peer_id']), 'Зачем? Это не беседа, если что')
                else:
                    vk.messages.send(
                        peer_id=int(event.object.message['peer_id']),
                        random_id=get_random_id(),
                        message='Нет такой команды')
            # elif event.type == VkBotEventType.MESSAGE_EVENT:
    except:
        continue
    # except requests.exceptions.ReadTimeout as timeout:
    #     continue

# import json
# CALLBACK_TYPES = []
# f_toggle: bool = False
# for event in long_poll.listen():
#     # отправляем меню 1го вида на любое текстовое сообщение от пользователя
#     if event.type == VkBotEventType.MESSAGE_NEW:
#         if event.obj.message['text'] != '':
#             if event.from_user:
#                 # Если клиент пользователя не поддерживает callback-кнопки,
#                 # нажатие на них будет отправлять текстовые
#                 # сообщения. Т.е. они будут работать как обычные inline кнопки.
#                 if 'callback' not in event.obj.client_info['button_actions']:
#                     print(f'Клиент {event.obj.message["from_id"]} не поддерж. callback')
#
#                 vk.messages.send(
#                     user_id=event.obj.message['from_id'],
#                     random_id=get_random_id(),
#                     peer_id=event.obj.message['from_id'],
#                     keyboard=keyboard_1_chat.get_keyboard(),
#                     message=event.obj.message['text'])
#     # обрабатываем клики по callback кнопкам
#     elif event.type == VkBotEventType.MESSAGE_EVENT:
#         # если это одно из 3х встроенных действий:
#         if event.object.payload.get('type') in CALLBACK_TYPES:
#             # отправляем серверу указания как какую из кнопок обработать. Это заложено в
#             # payload каждой callback-кнопки при ее создании.
#             # Но можно сделать иначе: в payload положить свои собственные
#             # идентификаторы кнопок, а здесь по ним определить
#             # какой запрос надо послать. Реализован первый вариант.
#             r = vk.messages.sendMessageEventAnswer(
#                 event_id=event.object.event_id,
#                 user_id=event.object.user_id,
#                 peer_id=event.object.peer_id,
#                 event_data=json.dumps(event.object.payload))
#         # если это наша "кастомная" (т.е. без встроенного действия) кнопка, то мы можем
#         # выполнить edit сообщения и изменить его меню. Но при желании мы могли бы
#         # на этот клик открыть ссылку/приложение или показать pop-up. (см.анимацию ниже)
#         elif event.object.payload.get('type') == 'my_own_100500_type_edit':
#             last_id = vk.messages.edit(
#                 peer_id=event.obj.peer_id,
#                 message='ola',
#                 conversation_message_id=event.obj.conversation_message_id,
#                 keyboard=(keyboard_1_chat if f_toggle else keyboard_2).get_keyboard())
#             f_toggle = not f_toggle
