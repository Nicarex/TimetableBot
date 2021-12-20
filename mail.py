import os
import yagmail
import configparser
import time
from log import logger
from timetable import timetable
from imap_tools import MailBox, A
from main import check_encoding_and_move_files, convert_to_sql
from glob import glob
from pathlib import Path
from sql_db import getting_the_difference_in_sql_files_and_sending_them


# Загрузка данных из конфига
config = configparser.ConfigParser()
try:
    config.read("config.ini")
    USERNAME = config['TEST']['username']
    PASSWORD = config['TEST']['password']
except KeyError as e:
    logger.error('Error when try to read config data. Maybe file not exist or field is wrong')


# Отправка почты через yagmail
def sendMail(to_email, subject, text):
    # Подключение к gmail
    yag = yagmail.SMTP(USERNAME, PASSWORD)
    # Подпись, которая добавляется в конец каждого отправленного сообщения
    signature = '\n\n\nСайт-инструкция: https://vk.link/bot_agz'
    # Непосредственно отправка письма
    yag.send(to=to_email, subject=subject, contents=text + signature)
    logger.log('EMAIL', 'Message was sent to <' + to_email + '> with subject: "' + subject + '"')


# Чтение почты и выполнение действий
def processingMail():
    logger.info('Email server started...')
    while True:
        try:
            logger.debug('Start work...')
            # Подключение к gmail
            mailbox = MailBox('imap.gmail.com')
            mailbox.login(username=USERNAME, password=PASSWORD)
            # Получение непрочитанных сообщений с ярлыком CSV files
            messages_csv = mailbox.fetch(A(seen=False, gmail_label='CSV files'))
            for msg in messages_csv:
                logger.log('EMAIL', 'CSV files message from ' + msg.from_)
                download_folder = 'downloads'
                # Проверка на существование пути
                if not os.path.isdir(download_folder):
                    os.makedirs(download_folder, exist_ok=True)
                # Скачивание вложений
                for attachment in msg.attachments:
                    # Скачивание файла в расширение tmp
                    p = Path(attachment.filename)
                    filename = p.with_suffix('.tmp')
                    download_path = f"{download_folder}/{filename}"
                    with open(download_path, "wb") as f:
                        f.write(attachment.payload)
                    logger.info('File <' + attachment.filename + '> is downloaded, size = ' + str(round(attachment.size / 1024, 1)) + 'KB')
                # Проверка вложений
                # Проверка кодировки
                if check_encoding_and_move_files(path=download_folder, encoding='utf-8') is True:
                    # Конвертирование CSV в SQL
                    convert_to_sql(csv_files_directory=download_folder)
                    # Удаление прошлых сохраненных расписаний
                    # Проверка на существование директории с расписаниями
                    if not os.path.isdir('timetable-files'):  # Если пути не существует - создать
                        os.makedirs('timetable-files', exist_ok=True)
                    list_of_files = glob('timetable-files')
                    for file in list_of_files:
                        os.remove(file)
                    getting_the_difference_in_sql_files_and_sending_them()


            # Получение непрочитанных сообщений с ярлыком Settings
            messages_set = mailbox.fetch(A(seen=False, gmail_label='Settings'))
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
                        sendMail(sender, subject=msg.subject,
                                 text='Для вашего email-адреса установлены следующие параметры отправки писем:\n' + temp)
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
                        sendMail(sender, subject=msg.subject,
                                 text='Для вашего email-адреса удалены все сохраненные параметры отправки писем')
                    elif sql_db.if_record_exist_email(sender) == 'NO':
                        sendMail(sender, subject=msg.subject,
                                 text='Нечего сбрасывать, так как для вас нет сохраненных групп или преподавателей.')

            # Получение непрочитанных сообщений с ярлыком Send
            messages_send = mailbox.fetch(A(seen=False, gmail_label='Send'))
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
                    sendMail(sender, subject=msg.subject,
                             text='Не удалось распознать ваш запрос\nВозможно вы сделали орфографическую ошибку')
                else:
                    sendMail(sender, subject=msg.subject, text=temp)
            mailbox.logout()  # Выход
            logger.debug('End work')
            time.sleep(10)
        except KeyboardInterrupt:
            logger.warning('Email server has been stopped by Ctrl+C')
            return 'EXIT'


with logger.catch():
    processingMail()

