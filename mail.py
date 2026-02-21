import imaplib
import threading
from socket import gaierror
from other import read_config, check_encoding_and_move_files, convert_to_sql, sendMail, strip_email_quotes, strip_html_quotes, NotificationError
import os
import time
from constants import MAIL_RETRY_WAIT
from logger import logger
from imap_tools import MailBox, A
from glob import glob
from pathlib import Path
from sql_db import compute_timetable_differences, update_changed_calendars, send_notifications_email, search_group_and_teacher_in_request, enable_and_disable_notifications, enable_and_disable_lesson_time, delete_all_saved_groups_and_teachers, display_saved_settings, getting_timetable_for_user, getting_workload_excel_for_user, getting_workload_excel_all_months_for_user
from calendar_timetable import show_calendar_url_to_user


# Чтение почты и выполнение действий
@logger.catch
def processingMail(notification_queues=None):
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
                    event, difference = compute_timetable_differences()
                    if event is None:
                        logger.log('MAIL', 'Difference wasnt sent')
                    else:
                        # Email и iCal-обновление запускаем параллельно в фоновых потоках
                        email_thread = threading.Thread(
                            target=send_notifications_email, kwargs=event, daemon=True)
                        ical_thread = threading.Thread(
                            target=update_changed_calendars, args=(difference,), daemon=True)
                        email_thread.start()
                        ical_thread.start()
                        logger.log('MAIL', 'Email notifications and iCal update started in parallel')
                        # Остальным ботам — каждый получает событие из своей очереди одновременно
                        if notification_queues is not None:
                            for platform, q in notification_queues.items():
                                q.put(event)
                            logger.log('MAIL', f'Notification event put into {len(notification_queues)} queues')

            # Получение непрочитанных сообщений с ярлыком Settings
            messages_set = mailbox.fetch(A(seen=False, gmail_label='Settings'))
            for msg in messages_set:
                logger.log('MAIL', 'Settings message from ' + msg.from_)
                answer = ''
                if msg.text != '':
                    text = strip_email_quotes(str(msg.text)).replace('\n', '')
                else:
                    text = strip_html_quotes(str(msg.html)).replace('\n', '')
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
                    text = strip_email_quotes(str(msg.text)).lower()
                else:
                    text = strip_html_quotes(str(msg.html)).lower()
                answer = ''
                excel_files = []
                if text.find('нагрузк') != -1 and (text.find('excel') != -1 or text.find('файл') != -1):
                    if text.find('все месяц') != -1:
                        excel_files = getting_workload_excel_all_months_for_user(email=msg.from_)
                    else:
                        excel_files = getting_workload_excel_for_user(email=msg.from_)
                    if excel_files:
                        sendMail(to_email=msg.from_, subject=msg.subject, text='Файл(ы) нагрузки во вложении', attachments=excel_files)
                    else:
                        sendMail(to_email=msg.from_, subject=msg.subject, text='Нет сохраненных преподавателей или групп для генерации нагрузки')
                else:
                    if text.find('текущ') != -1:
                        answer += str(getting_timetable_for_user(email=msg.from_))
                    if text.find('следующ') != -1:
                        answer += str(getting_timetable_for_user(email=msg.from_, next='YES'))
                    if answer == '':
                        sendMail(to_email=msg.from_, subject=msg.subject, text='Не удалось распознать ваш запрос\nВозможно вы сделали орфографическую ошибку')
                    else:
                        sendMail(to_email=msg.from_, subject=msg.subject, text='', html=answer)

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
            time.sleep(MAIL_RETRY_WAIT)
            continue
        except imaplib.IMAP4.abort:
            logger.log('MAIL', 'Imaplib error. Continue...')
            # Ждем 2 минуты появления интернета
            time.sleep(MAIL_RETRY_WAIT)
            continue
        except imaplib.IMAP4.error:
            logger.log('MAIL', 'Imaplib error. Continue...')
            # Ждем 2 минуты появления интернета
            time.sleep(MAIL_RETRY_WAIT)
            continue
        except NotificationError as e:
            logger.log('MAIL', f'Failed to send email: {e}')
            time.sleep(MAIL_RETRY_WAIT)
            continue
        except OSError:
            logger.log('MAIL', 'Imaplib error. Continue...')
            # Ждем 2 минуты появления интернета
            time.sleep(MAIL_RETRY_WAIT)
            continue
