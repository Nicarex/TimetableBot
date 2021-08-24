import os
from pathlib import Path
from imbox import Imbox
import yagmail
import configparser
import dbf
import sql_db
import schedule
import time
from timetable import timetable


# Загрузка данных из конфига
config = configparser.ConfigParser()
config.read("config.ini")
USERNAME = config['MAIL']['username']
PASSWORD = config['MAIL']['password']


# Отправка почты через yagmail
def sendMail(to_email, subject, text):
    # подключени к gmail
    yag = yagmail.SMTP(USERNAME, PASSWORD)
    # Подпись, которая добавляется в конец каждого отправленного сообщения
    signature = '\n\nСайт-инструкция: vk.link/bot_agz\nПо всем вопросам просьба писать на почту ' \
                'my.profile.protect@gmail.com '
    # Непосредственно отправка письма
    yag.send(to=to_email, subject=subject, contents=text + signature)


# Чтение почты и выполнение действий
def readMail():
    # Подключение к gmail
    mail = Imbox('imap.gmail.com', username=USERNAME, password=PASSWORD, ssl=True, ssl_context=None,
                 starttls=False)

    # Получение непрочитанных сообщений с ярлыком DBF files
    messages_dbf = mail.messages(unread=True, label='DBF files')
    for (uid, message) in messages_dbf:
        # Вывод сообщения
        print('[EMAIL] DBF message: from ' + str(message.sent_from[0]['email']) + ' text: ' + str(message.body['plain']))
        # Скачивание вложений
        for attachment in message.attachments:
            download_folder = 'downloads'
            if not os.path.isdir(download_folder):  # Если пути не существует - создать
                os.makedirs(download_folder, exist_ok=True)
            down_path = Path(Path.cwd() / "downloads")  # Если в downloads есть .dbf - удалить
            for filename in down_path.glob('*.dbf'):
                filename.unlink()
            att_fn = attachment.get('filename')
            download_path = f"{download_folder}/{att_fn}"
            open(download_path, "wb").write(attachment.get('content').read())  # Скачивание файла
            print('File', '<' + att_fn + '>', 'is downloaded,  size =',  # Вывод в консоль названия
                  round(int(attachment.get('size')) / 1048576, 1), 'MB\n')  # файла и его размер

            mail.mark_seen(uid)  # отмечает письмо прочитанным

    # Получение непрочитанных сообщений с ярлыком Settings
    messages_set = mail.messages(unread=True, label='Settings')
    for (uid, message) in messages_set:
        sender = str(message.sent_from[0]['email'])
        text = str(message.body['plain'])
        # Вывод сообщения
        print('[EMAIL] SETTINGS message: from ' + sender + ' text: ' + text)
        # Парсинг текста в сообщении
        # Добавление параметров в БД
        for record in dbf.connect_to_dbf():
            # Проверка на группу
            if not text.find(record['GROUP']) == -1:
                sql_db.add_values_email('students_email', sender, str(record['GROUP']))
            # Проверка на фамилию
            elif not text.find(record['NAME']) == -1:
                sql_db.add_values_email('teachers_email', sender, str(record['NAME']))

        # Чтение параметров из БД и отправка этого в ответном сообщении
        temp = ''
        # Для студентов
        for i in sql_db.read_values_all_email('students_email', sender):
            temp = temp + str(i['email']+' - '+i['group_id']+'\n')
        # Для учителей
        for i in sql_db.read_values_all_email('teachers_email', sender):
            temp = temp + str(i['email']+' - '+i['teacher_id']+'\n')
        sendMail(sender, message.subject, 'Для вашего email-адреса установлены следующие параметры отправки писем:\n'+temp)

        mail.mark_seen(uid)  # отмечает письмо прочитанным

    # Получение непрочитанных сообщений с ярлыком Send
    messages_send = mail.messages(unread=True, label='Send')
    for (uid, message) in messages_send:
        sender = str(message.sent_from[0]['email'])
        text = str(message.body['plain'])
        # Вывод сообщения
        print('[EMAIL] SEND message: from ' + sender + ' text: ' + text)
        #
        #

    mail.logout()  # Выход


# readMail()

# Прочтение сообщений раз в минуту
schedule.every(1).minute.do(readMail)
while True:
    try:
        schedule.run_pending()
        time.sleep(1)
    except KeyboardInterrupt:
        print('Program stop...')
