import os
import yagmail
import configparser
from dbf import connect_to_dbf
import sql_db
import schedule
import time
from timetable import timetable
from imap_tools import MailBox, AND


# Загрузка данных из конфига
config = configparser.ConfigParser()
config.read("config.ini")
USERNAME = config['TEST']['username']
PASSWORD = config['TEST']['password']


# Отправка почты через yagmail
def sendMail(to_email, subject, text):
    # подключени к gmail
    yag = yagmail.SMTP(USERNAME, PASSWORD)
    # Подпись, которая добавляется в конец каждого отправленного сообщения
    signature = '\n\nСайт-инструкция: https://vk.link/bot_agz'
    # Непосредственно отправка письма
    yag.send(to=to_email, subject=subject, contents=text + signature)


# Чтение почты и выполнение действий
def processingMail():
    # Подключение к gmail
    mailbox = MailBox('imap.gmail.com')
    mailbox.login(username=USERNAME, password=PASSWORD)

    # Получение непрочитанных сообщений с ярлыком DBF files
    messages_dbf = mailbox.fetch(AND(seen=False, gmail_label='DBF files'))
    for msg in messages_dbf:
        # Вывод сообщения
        print('[EMAIL] DBF message: from ' + msg.from_)
        # Скачивание вложений
        for attachment in msg.attachments:
            download_folder = 'downloads'
            if not os.path.isdir(download_folder):  # Если пути не существует - создать
                os.makedirs(download_folder, exist_ok=True)
            att_fn = attachment.filename
            download_path = f"{download_folder}/{att_fn}"
            open(download_path, "wb").write(attachment.payload)  # Скачивание файла
            print('File', '<' + att_fn + '>', 'is downloaded,  size =',  # Вывод в консоль названия
                  round(attachment.size / 1048576, 1), 'MB')  # файла и его размер

    # Получение непрочитанных сообщений с ярлыком Settings
    messages_set = mailbox.fetch(AND(seen=False, gmail_label='Settings'))
    for msg in messages_set:
        sender = msg.from_
        text = msg.text
        # Вывод сообщения
        print('[EMAIL] SETTINGS message: from ' + sender)
        # Парсинг текста в сообщении
        # Добавление параметров в БД
        for record in connect_to_dbf():
            # Проверка на группу
            if text.find(record['GROUP']) != -1:
                sql_db.add_values_email('students_email', sender, str(record['GROUP']))
            # Проверка на фамилию
            elif text.find(record['NAME']) != -1:
                sql_db.add_values_email('teachers_email', sender, str(record['NAME']))

        # Сообщение в нижний регистр для проверки слов
        text = text.lower()
        # Если сбросить не найдено
        if text.find('сбросить') == -1:
            # Чтение параметров из БД и отправка этого в ответном сообщении
            temp = ''
            if sql_db.if_record_exist_email(sender) == 'YES':
                # Для студентов
                for i in sql_db.read_values_all_email('students_email', sender):
                    temp = temp + str(i['email'] + ' - ' + i['group_id'] + '\n')
                # Для учителей
                for i in sql_db.read_values_all_email('teachers_email', sender):
                    temp = temp + str(i['email'] + ' - ' + i['teacher_id'] + '\n')
                sendMail(sender, subject=msg.subject, text='Для вашего email-адреса установлены следующие параметры отправки писем:\n' + temp)
            elif sql_db.if_record_exist_email(sender) == 'NO':
                sendMail(sender, subject=msg.subject, text='Нет распознанных групп или преподавателей.')
        # Если сбросить найдено
        else:
            temp = ''
            if sql_db.if_record_exist_email(sender) == 'YES':
                # Для студентов
                sql_db.delete_values_all_email('students_email', sender)
                # Для учителей
                sql_db.delete_values_all_email('teachers_email', sender)
                sendMail(sender, subject=msg.subject, text='Для вашего email-адреса удалены все сохраненные параметры отправки писем')
            elif sql_db.if_record_exist_email(sender) == 'NO':
                sendMail(sender, subject=msg.subject, text='Нечего сбрасывать, так как для вас нет сохраненных групп или преподавателей.')

    # Получение непрочитанных сообщений с ярлыком Send
    messages_send = mailbox.fetch(AND(seen=False, gmail_label='Send'))
    for msg in messages_send:
        sender = msg.from_
        text = msg.text.lower()
        # Вывод сообщения
        print('[EMAIL] SEND message: from ' + sender)
        temp = ''
        if text.find('текущ') != -1:
            if sql_db.if_record_exist_email(sender=sender) == 'YES':
                for i in sql_db.read_values_all_email('students_email', sender):
                    temp = temp + timetable(group=i['group_id']) + '\n'
                for i in sql_db.read_values_all_email('teachers_email', sender):
                    temp = temp + timetable(group='', teacher=i['teacher_id']) + '\n'
            elif sql_db.if_record_exist_email(sender=sender) == 'NO':
                temp = temp + 'Для вас не найдено настроенных групп или преподавателей'
        if text.find('следующ') != -1:
            if sql_db.if_record_exist_email(sender=sender) == 'YES':
                for i in sql_db.read_values_all_email('students_email', sender):
                    temp = temp + timetable(group=i['group_id'], next='YES') + '\n'
                for i in sql_db.read_values_all_email('teachers_email', sender):
                    temp = temp + timetable(group='', teacher=i['teacher_id'], next='YES') + '\n'
            elif sql_db.if_record_exist_email(sender=sender) == 'NO':
                temp = temp + 'Для вас не найдено настроенных групп или преподавателей'
        if temp == '':
            sendMail(sender, subject=msg.subject, text='Не удалось распознать ваш запрос\nВозможно вы сделали орфографическую ошибку')
        else:
            sendMail(sender, subject=msg.subject, text=temp)

    mailbox.logout()  # Выход


# Прочтение сообщений раз в минуту
schedule.every(1).minute.do(processingMail)


def run_program_at_time():
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print('Program stop...')
