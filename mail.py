import os
from imbox import Imbox
import configparser
import traceback

config = configparser.ConfigParser()
config.read("config.ini")
USERNAME = config['MAIL']['username']
PASSWORD = config['MAIL']['password']


def connectMail():
    # Подключение к gmail
    mail = Imbox('imap.gmail.com', username=USERNAME, password=PASSWORD, ssl=True, ssl_context=None,
                 starttls=False)
    while True:
        # Проверка соединения
        try:
            # Получение непрочитанных сообщений с ярлыком DBF files
            messages = mail.messages(unread=True, label='DBF files')
            for (uid, message) in messages:
                mail.mark_seen(uid)  # отмечает письмо прочитанным
                for attachment in message.attachments:
                    download_folder = 'downloads'
                    if not os.path.isdir(download_folder):  # Если пути не существует - создать
                        os.makedirs(download_folder, exist_ok=True)
                    att_fn = attachment.get('filename')
                    download_path = f"{download_folder}/{att_fn}"
                    open(download_path, "wb").write(attachment.get('content').read())  # Скачивание файла
                    print('File', '<' + att_fn + '>', 'is downloaded,  size =',  # Вывод в консоль названия
                          round(int(attachment.get('size')) / 1048576, 1), 'MB')  # файла и его размер
        except ConnectionAbortedError:
            print('Соединение разорвано')
            # print(traceback.print_exc())


connectMail()
