import imaplib
from socket import gaierror
from other import read_config, check_encoding_and_move_files, convert_to_sql, sendMail
import os
import time
from logger import logger
from imap_tools import MailBox, A
from glob import glob
from pathlib import Path
from sql_db import getting_the_difference_in_sql_files_and_sending_them, search_group_and_teacher_in_request, enable_and_disable_notifications, enable_and_disable_lesson_time, delete_all_saved_groups_and_teachers, display_saved_settings, getting_timetable_for_user
from calendar_timetable import show_calendar_url_to_user


# Чтение почты и выполнение действий
@logger.catch
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
                    logger.log('MAIL', 'File <' + attachment.filename + '> is downloaded, size = ' + str(round(attachment.size / 1024, 1)) + 'KB')
                # Проверка вложений
                # Проверка кодировки
                if check_encoding_and_move_files(path=download_folder, encoding='windows-1251') is True:
                    # Конвертирование CSV в SQL
                    convert_to_sql(csv_files_directory=download_folder)
                    # Удаление прошлых сохраненных расписаний
                    list_of_files = glob('timetable-files/*')
                    for file in list_of_files:
                        os.remove(file)
                    if getting_the_difference_in_sql_files_and_sending_them() is False:
                        logger.log('MAIL', 'Difference wasnt sent')

            # Получение непрочитанных сообщений с ярлыком Settings
            messages_set = mailbox.fetch(A(seen=False, gmail_label='Settings'))
            for msg in messages_set:
                logger.log('MAIL', 'Settings message from ' + msg.from_)
                answer = ''
                if msg.text != '':
                    text = str(msg.text).replace('\n', '')
                    print(text)
                else:
                    text = str(msg.html).replace('\n', '')
                if text.lower().find('текущие') != -1:
                    answer = display_saved_settings(email=msg.from_)
                # Если нужно добавить параметры, а не посмотреть текущие
                else:
                    # Поиск группы и преподавателей в сообщении
                    search_response = search_group_and_teacher_in_request(request=text, email=msg.from_)
                    if search_response is False:
                        answer += 'Нет распознанных групп или преподавателей, если вы их вводили\n\nНапоминаю, что для успешного добавления параметров нужно придерживаться строгих правил ввода, которые можно посмотреть в инструкции\n'
                    else:
                        answer += search_response
                    # Сообщение в нижний регистр для проверки слов
                    text = text.lower()
                    if text.find('включить уведомления') != -1:
                        answer += str(enable_and_disable_notifications(enable='YES', email=msg.from_))
                    elif text.find('выключить уведомления') != -1:
                        answer += str(enable_and_disable_notifications(disable='YES', email=msg.from_))
                    if text.find('включить отображение времени занятий') != -1:
                        answer += str(enable_and_disable_lesson_time(enable='YES', email=msg.from_))
                    elif text.find('выключить отображение времени занятий') != -1:
                        answer += str(enable_and_disable_lesson_time(disable='YES', email=msg.from_))
                    if text.find('календарь') != -1:
                        answer += str(show_calendar_url_to_user(email=msg.from_))
                    if text.find('сбросить параметры отправки') != -1:
                        answer += str(delete_all_saved_groups_and_teachers(email=msg.from_))
                sendMail(to_email=msg.from_, subject=msg.subject, text=answer)

            # Получение непрочитанных сообщений с ярлыком Send
            messages_send = mailbox.fetch(A(seen=False, gmail_label='Send'))
            for msg in messages_send:
                logger.log('MAIL', 'Send message from ' + msg.from_)
                if msg.text != '':
                    text = str(msg.text).lower()
                else:
                    text = str(msg.html).lower()
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
            logger.log('MAIL', 'Email server has been stopped by Ctrl+C')
            return 'EXIT'
        # Подключение к интернету
        except gaierror:
            logger.log('MAIL', 'Network is unreachable!')
            # Ждем 2 минуты появления интернета
            time.sleep(120)
            continue
        except imaplib.IMAP4.abort:
            logger.log('MAIL', 'Imaplib error. Continue...')
            # Ждем 2 минуты появления интернета
            time.sleep(120)
            continue
        except imaplib.IMAP4.error:
            logger.log('MAIL', 'Imaplib error. Continue...')
            # Ждем 2 минуты появления интернета
            time.sleep(120)
            continue
        except OSError:
            logger.log('MAIL', 'Imaplib error. Continue...')
            # Ждем 2 минуты появления интернета
            time.sleep(120)
            continue
