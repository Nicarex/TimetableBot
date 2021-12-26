from socket import gaierror
from other import read_config, check_encoding_and_move_files, convert_to_sql, sendMail
import os
import time
from log import logger
from imap_tools import MailBox, A
from glob import glob
from pathlib import Path
from sql_db import getting_the_difference_in_sql_files_and_sending_them, search_group_and_teacher_in_request, enable_and_disable_notifications, delete_all_saved_groups_and_teachers, display_saved_settings, getting_timetable_for_user


# Чтение почты и выполнение действий
def processingMail():
    logger.log('MAIL', 'Email server started...')
    login_info = read_config(email='YES')
    while True:
        try:
            # Подключение к gmail
            mailbox = MailBox(login_info[0])
            mailbox.login(username=login_info[1], password=login_info[2])
            # Получение непрочитанных сообщений с ярлыком CSV files
            messages_csv = mailbox.fetch(A(seen=False, gmail_label='CSV files'))
            for msg in messages_csv:
                logger.log('MAIL', 'CSV files message from ' + msg.from_)
                download_folder = 'downloads'
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
                    list_of_files = glob('timetable-files/*')
                    for file in list_of_files:
                        os.remove(file)
                    getting_the_difference_in_sql_files_and_sending_them()

            # Получение непрочитанных сообщений с ярлыком Settings
            messages_set = mailbox.fetch(A(seen=False, gmail_label='Settings'))
            for msg in messages_set:
                logger.log('MAIL', 'Settings message from ' + msg.from_)
                answer = ''
                if msg.text.lower().find('текущие') != -1:
                    answer = display_saved_settings(email=msg.from_)
                # Если нужно добавить параметры, а не посмотреть текущие
                else:
                    # Поиск группы и преподов
                    response = search_group_and_teacher_in_request(request=msg.text, email=msg.from_)
                    if response:
                        answer += str(response)
                    else:
                        answer += 'Нет распознанных групп или преподавателей, если вы их вводили\n\nНапоминаю, что для успешного добавления параметров нужно придерживаться строгих правил ввода, которые можно посмотреть в инструкции'
                    # Сообщение в нижний регистр для проверки слов
                    text = msg.text.lower()
                    # Проверка на уведомления
                    if text.find('включить уведомления') != -1:
                        answer += str(enable_and_disable_notifications(enable='YES', email=msg.from_))
                    elif text.find('выключить уведомления') != -1:
                        answer += str(enable_and_disable_notifications(disable='YES', email=msg.from_))
                    if text.find('сбросить параметры отправки') != -1:
                        answer += str(delete_all_saved_groups_and_teachers(email=msg.from_))
                sendMail(to_email=msg.from_, subject=msg.subject, text=answer)

            # Получение непрочитанных сообщений с ярлыком Send
            messages_send = mailbox.fetch(A(seen=False, gmail_label='Send'))
            for msg in messages_send:
                logger.log('MAIL', 'Send message from ' + msg.from_)
                text = msg.text.lower()
                answer = ''
                if text.find('текущ') != -1:
                    answer += str(getting_timetable_for_user(email=msg.from_))
                if text.find('следующ') != -1:
                    answer += str(getting_timetable_for_user(email=msg.from_, next='YES'))
                if answer == '':
                    sendMail(to_email=msg.from_, subject=msg.subject, text='Не удалось распознать ваш запрос\nВозможно вы сделали орфографическую ошибку')
                else:
                    sendMail(to_email=msg.from_, subject=msg.subject, text=answer)

            mailbox.logout()  # Выход
            # logger.debug('End work')
            time.sleep(10)
        except KeyboardInterrupt:
            logger.warning('Email server has been stopped by Ctrl+C')
            return 'EXIT'
        # Подключение к интернету
        except gaierror:
            logger.log('EMAIL', 'Network is unreachable!')
            # Ждем 2 минуты появления интернета
            time.sleep(120)
            continue


with logger.catch():
    processingMail()

