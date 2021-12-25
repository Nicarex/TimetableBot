from log import logger
from glob import glob
import os
from chardet import detect
import sqlite3
from pathlib import Path
import pendulum
import pandas
import configparser
import yagmail


# Загрузка данных из конфига
config = configparser.ConfigParser()
try:
    config.read("config.ini")
    USERNAME = config['TEST']['username']
    PASSWORD = config['TEST']['password']
    GROUP_TOKEN = config['TEST']['group_token']
except KeyError as e:
    logger.critical('Error when try to read config data. Maybe file not exist or fields is wrong')


# Отправка почты через yagmail
def sendMail(to_email, subject, text):
    # Подключение к gmail
    yag = yagmail.SMTP(USERNAME, PASSWORD)
    # Подпись, которая добавляется в конец каждого отправленного сообщения
    signature = '\n\n\nСайт-инструкция: https://vk.link/bot_agz'
    # Непосредственно отправка письма
    yag.send(to=to_email, subject=subject, contents=text + signature)
    logger.log('EMAIL', 'Message was sent to <' + to_email + '> with subject: "' + subject + '"')


# Получает последний измененный файл
def get_latest_file(path: str):
    """
    example path = 'timetable-dbs/timetable*.db'
    """
    list_of_files = glob(path)  # * means all if need specific format then *.csv
    # Если есть хоть один файл
    if list_of_files:
        latest_file = max(list_of_files, key=os.path.getmtime)
        logger.log('OTHER', 'Latest file is <' + latest_file + '>')
        return latest_file
    else:
        logger.warning('No files in this path ' + path)
        return None


# Проверка кодировки файла и перемещение файлов
def check_encoding_and_move_files(path: str, encoding: str):
    # Проверка кодировки
    def check_encoding(file: str):
        logger.info('Check encoding of file <' + file + '>...')
        with open(file, 'rb') as f:
            rawfile = f.read()
        result_encoding = detect(rawfile)
        if result_encoding['encoding'] == encoding:
            logger.success('Encoding of file <' + file + '> is ' + str(result_encoding['encoding']))
            return True
        else:
            logger.error('Encoding of file <' + file + '> doest match with request! Encoding is ' + str(
                result_encoding['encoding']))
            return False
    # Проверка на существование хоть одного файла .tmp
    list_of_files_tmp = glob(path + '/*.tmp')
    if list_of_files_tmp:
        for file in list_of_files_tmp:
            # Если кодировка неправильная, то все tmp-файлы удаляются
            if check_encoding(file=file) is False:
                for file_delete in list_of_files_tmp:
                    os.remove(file_delete)
                return False
    else:
        logger.error('No tmp-files in this path ' + path)
        return None
    """
    Если дошли досюда, то всё правильно
    Удаляем оригинальные файлы и переименовываем полученные, возвращаем True
    """
    list_of_files_csv = glob(path + '/*.csv')
    for file in list_of_files_csv:
        os.remove(file)
    logger.debug('All previous csv-files are deleted')
    for file in list_of_files_tmp:
        p = Path(file)
        p.rename(p.with_suffix('.csv'))
    logger.debug('Tmp-files are renamed to csv')
    return True


def connection_to_sql(name: str):
    try:
        conn = sqlite3.connect(database=name, timeout=20)
        logger.log('OTHER', 'Successfully connect to sql db <' + name + '>')
    except sqlite3.Error as error:
        logger.error('Failed to read data from sql, error: ' + str(error))
        return None
    return conn


# Конвертирует CSV-файлы в SQL-файл
def convert_to_sql(csv_files_directory: str):
    """
    example:
    for file in os.listdir('downloads'):
        convert_to_sql()
    """
    # Если пути не существует - создать
    if not os.path.isdir('timetable-dbs'):
        os.makedirs('timetable-dbs', exist_ok=True)
    date = pendulum.now(tz='Europe/Moscow').format('YYYY-MM-DD_HH-mm-ss')
    # Если есть хоть один файл, который заканчивается на csv
    list_of_files = glob(csv_files_directory + '/*.csv')
    if list_of_files:
        pass
    else:
        logger.error('Cant convert to sql because no file exist in <' + csv_files_directory + '>')
        return False
    conn = connection_to_sql(name='timetable-dbs/timetable_' + date + '.db')
    for csv_file in list_of_files:
        logger.info('Convert <' + csv_file + '> to SQL...')
        timetable_csv = pandas.read_csv(csv_file, encoding='utf-8', sep=';')
        timetable_csv.to_sql(name='timetable', con=conn, if_exists='append', index=False)
        logger.success('File <' + csv_file + '> successfully converted to timetable_' + date + '.db')
    conn.close()
    return True

# convert_to_sql('downloads')

