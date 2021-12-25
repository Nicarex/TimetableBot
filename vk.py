from log import logger
from vkbottle import GroupEventType, GroupTypes, Keyboard, Text, VKAPIError, KeyboardButtonColor, OpenLink
from vkbottle.bot import Bot, Message
from other import GROUP_TOKEN
from sql_db import search_group_and_teacher_in_request, display_saved_settings, delete_all_saved_groups_and_teachers, getting_timetable_for_user, enable_and_disable_notifications


bot = Bot(token=GROUP_TOKEN)


KEYBOARD_USER_MAIN = (
    Keyboard(one_time=False, inline=False)
    .add(Text("Текущая неделя"), color=KeyboardButtonColor.PRIMARY)
    .add(Text("Следующая неделя"), color=KeyboardButtonColor.POSITIVE)
    .row()
    .add(OpenLink(label='Расписание на сайте', link='https://www.amchs.ru/students/raspisanie/'))
    .add(Text("Настройки"), color=KeyboardButtonColor.NEGATIVE)
    .get_json()
)

KEYBOARD_USER_SETTINGS = (
    Keyboard(one_time=False, inline=False)
    .add(Text('Настроить уведомления'), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(OpenLink(label='Инструкция', link='https://vk.link/bot_agz'))
    .row()
    .add(Text('Удалить параметры групп и преподавателей'), color=KeyboardButtonColor.NEGATIVE)
    .row()
    .add(Text('Об авторе'), color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Text('Вернуться назад'), color=KeyboardButtonColor.POSITIVE)
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
    .add(Text('Настроить уведомления'), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text('Удалить параметры групп и преподавателей'), color=KeyboardButtonColor.NEGATIVE)
    .row()
    .add(Text('Вернуться назад'), color=KeyboardButtonColor.POSITIVE)
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


# Обработка личных сообщений
@bot.on.private_message(text="Текущая неделя")
async def timetable_now(message: Message):
    answer = str(getting_timetable_for_user(vk_id_user=str(message.from_id))).split('Cut\n')
    for i in answer:
        if i != '':
            await message.answer('➡ ' + i, keyboard=KEYBOARD_USER_MAIN)

@bot.on.private_message(text="Следующая неделя")
async def timetable_next(message: Message):
    answer = str(getting_timetable_for_user(next='YES', vk_id_user=str(message.from_id))).split('Cut\n')
    for i in answer:
        if i != '':
            await message.answer('➡ ' + i, keyboard=KEYBOARD_USER_MAIN)

@bot.on.private_message(text="Начать")
async def start_answer(message: Message):
    users_info = await bot.api.users.get(message.from_id)
    await message.answer("Привет, {}!\nЯ - бот, который помогает с расписанием\nНастоятельно рекомендую ознакомиться с инструкцией:\nhttps://vk.link/bot_agz\n\nАхтунг! Бот находится в стадии бета-тестирования".format(users_info[0].first_name), keyboard=KEYBOARD_USER_MAIN)

@bot.on.private_message(text="Настройки")
async def settings(message: Message):
    answer = display_saved_settings(vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_SETTINGS)

@bot.on.private_message(text="Удалить параметры групп и преподавателей")
async def delete_saved_settings(message: Message):
    answer = delete_all_saved_groups_and_teachers(vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_SETTINGS)

@bot.on.private_message(text="Вернуться назад")
async def back(message: Message):
    await message.answer('Хорошо', keyboard=KEYBOARD_USER_MAIN)

@bot.on.private_message(text="Об авторе")
async def about_author(message: Message):
    await message.answer('Автор бота:\nНасонов Никита\nстудент 307 группы\n\nКонтакты:\nVK: https://vk.com/nicarex\nEmail: my.profile.protect@gmail.com', keyboard=KEYBOARD_USER_SETTINGS)

@bot.on.private_message(text="Настроить уведомления")
async def settings_noti(message: Message):
    await message.answer('Выберите параметры', keyboard=KEYBOARD_USER_NOTI)

@bot.on.private_message(text="Включить уведомления")
async def noti_enable(message: Message):
    answer = enable_and_disable_notifications(enable='YES', vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_SETTINGS)

@bot.on.private_message(text="Выключить уведомления")
async def noti_disable(message: Message):
    answer = enable_and_disable_notifications(disable='YES', vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_SETTINGS)

@bot.on.private_message(text="<groups_and_teachers>")
async def search_in_request(message: Message, groups_and_teachers: str):
    answer = search_group_and_teacher_in_request(request=str(groups_and_teachers), vk_id_user=str(message.from_id))
    await message.answer(answer, keyboard=KEYBOARD_USER_MAIN)



# Обработка сообщений из бесед
@bot.on.chat_message(text="Текущая неделя")
async def timetable_now(message: Message):
    answer = str(getting_timetable_for_user(vk_id_chat=str(message.chat_id))).split('Cut\n')
    for i in answer:
        if i != '' and i != answer[-1]:
            await message.answer(message='➡ ' + i)
        elif i != '' and i == answer[-1]:
            await message.answer(message='➡ ' + i, keyboard=KEYBOARD_CHAT_MAIN)

@bot.on.chat_message(text="Следующая неделя")
async def timetable_next(message: Message):
    answer = str(getting_timetable_for_user(next='YES', vk_id_chat=str(message.chat_id))).split('Cut\n')
    for i in answer:
        if i != '' and i != answer[-1]:
            await message.answer(message='➡ ' + i)
        elif i != '' and i == answer[-1]:
            await message.answer(message='➡ ' + i, keyboard=KEYBOARD_CHAT_MAIN)

@bot.on.chat_message(text="Начать")
async def start_answer(message: Message):
    await message.answer("Привет!\nЯ - бот, который помогает с расписанием\nНастоятельно рекомендую ознакомиться с инструкцией:\nhttps://vk.link/bot_agz\n\nАхтунг! Бот находится в стадии бета-тестирования", keyboard=KEYBOARD_CHAT_MAIN)

@bot.on.chat_message(text=['Настройки', '/Настройки', 'настройки', '/настройки'])
async def settings(message: Message):
    answer = display_saved_settings(vk_id_chat=str(message.chat_id))
    await message.answer(message=answer, keyboard=KEYBOARD_CHAT_SETTINGS)

@bot.on.chat_message(text="Удалить параметры групп и преподавателей")
async def delete_saved_settings(message: Message):
    answer = delete_all_saved_groups_and_teachers(vk_id_chat=str(message.chat_id))
    await message.answer(answer, keyboard=KEYBOARD_CHAT_SETTINGS)

@bot.on.chat_message(text="Вернуться назад")
async def back(message: Message):
    await message.answer('Хорошо', keyboard=KEYBOARD_CHAT_MAIN)

@bot.on.chat_message(text="Об авторе")
async def about_author(message: Message):
    await message.answer('Автор бота:\nНасонов Никита\nстудент 307 группы\n\nКонтакты:\nVK: https://vk.com/nicarex\nEmail: my.profile.protect@gmail.com', keyboard=KEYBOARD_CHAT_SETTINGS)

@bot.on.chat_message(text="Настроить уведомления")
async def settings_noti(message: Message):
    await message.answer('Выберите параметры', keyboard=KEYBOARD_CHAT_NOTI)

@bot.on.chat_message(text="Включить уведомления")
async def noti_enable(message: Message):
    answer = enable_and_disable_notifications(enable='YES', vk_id_chat=str(message.chat_id))
    await message.answer(answer, keyboard=KEYBOARD_CHAT_SETTINGS)

@bot.on.chat_message(text="Выключить уведомления")
async def noti_disable(message: Message):
    answer = enable_and_disable_notifications(disable='YES', vk_id_chat=str(message.chat_id))
    await message.answer(answer, keyboard=KEYBOARD_CHAT_SETTINGS)

@bot.on.chat_message(text="<groups_and_teachers>")
async def search_in_request(message: Message, groups_and_teachers: str):
    answer = search_group_and_teacher_in_request(request=str(groups_and_teachers), vk_id_chat=str(message.chat_id))
    await message.answer(answer, keyboard=KEYBOARD_CHAT_MAIN)

@bot.on.chat_message()
async def by_name_2(message: Message):
    answer = 'Выберите параметры'
    await message.answer(answer, keyboard=KEYBOARD_CHAT_MAIN)

@bot.on.raw_event(GroupEventType.GROUP_JOIN, dataclass=GroupTypes.GroupJoin)
async def group_join_handler(event: GroupTypes.GroupJoin):
    try:
        await bot.api.messages.send(
            peer_id=event.object.user_id, message="Спасибо за подписку!", random_id=0)
    except VKAPIError[901]:
        pass


bot.run_forever()