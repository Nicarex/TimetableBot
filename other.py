from logger import logger
from glob import glob
import os
from chardet import detect
import sqlite3
from pathlib import Path
import pendulum
import pandas
import configparser
import yagmail
import time
from constants import (
    TIMEZONE, URL_INSTRUCTIONS, SQL_TIMEOUT, MAIL_RETRY_WAIT,
    DIR_TIMETABLE_DBS, DIR_TIMETABLE_FILES, DIR_DOWNLOADS, DIR_LOG, DIR_CALENDARS, DIR_DBS,
)


def read_config(email: str = None, vk: str = None, vk_send: str = None, github: str = None, telegram: str = None, discord: str = None):
    # Загрузка данных из конфига
    config = configparser.ConfigParser()
    try:
        config.read("config.ini")
        if email is not None:
            imap_server = str(config['MAIL']['imap_server'])
            username = str(config['MAIL']['username'])
            password = str(config['MAIL']['password'])
            return imap_server, username, password
        elif vk is not None:
            group_token = str(config['VK']['group_token'])
            return group_token
        elif vk_send is not None:
            group_token = str(config['VK']['group_token2'])
            return group_token
        elif github is not None:
            github_token = str(config['GITHUB']['token'])
            return github_token
        elif telegram is not None:
            token = str(config['TELEGRAM']['tg_token'])
            return token
        elif discord is not None:
            token = str(config['DISCORD']['token'])
            return token
    except KeyError:
        logger.critical('Error when try to read config data. Maybe file not exist or fields are wrong')


def create_required_dirs():
    for d in (DIR_TIMETABLE_DBS, DIR_TIMETABLE_FILES, DIR_DOWNLOADS, DIR_LOG, DIR_CALENDARS, DIR_DBS):
        os.makedirs(d, exist_ok=True)


# Отправка почты через yagmail
def sendMail(to_email, subject, text):
    try:
        # Подключение к gmail
        user_info = read_config(email='YES')
        yag = yagmail.SMTP(user=user_info[1], password=user_info[2])
        # Подпись, которая добавляется в конец каждого отправленного сообщения
        signature = f'\n\n\nСайт-инструкция: {URL_INSTRUCTIONS}'
        # Непосредственно отправка письма
        yag.send(to=to_email, subject=subject, contents=text + signature)
        logger.log('MAIL', 'Message was sent to <' + to_email + '>, with subject: "' + subject + '"')
    except Exception as exc:
        logger.log('MAIL', f'Cant send mail to {to_email}: {exc}, wait {MAIL_RETRY_WAIT} sec...')
        time.sleep(MAIL_RETRY_WAIT)

# Получает последний измененный файл
def get_latest_file(path: str):
    """
    example path = 'timetable-dbs/timetable*.db'
    """
    list_of_files = glob(path)
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
        logger.log('OTHER', 'Check encoding of file <' + file + '>...')
        with open(file, 'rb') as f:
            rawfile = f.read()
        result_encoding = detect(rawfile)
        if result_encoding['encoding'] == encoding:
            logger.log('OTHER', 'Encoding of file <' + file + '> is ' + str(result_encoding['encoding']))
            return True
        else:
            logger.error('Encoding of file <' + file + '> doest match with request! Encoding is ' + str(
                result_encoding['encoding']))
            return False
    # Проверка на существование хоть одного файла .tmp
    # Если есть - проверка кодировки
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
        return False
    """
    Если дошли досюда, то всё правильно
    Удаляем оригинальные файлы и переименовываем полученные, возвращаем True
    """
    list_of_files_csv = glob(path + '/*.csv')
    for file in list_of_files_csv:
        os.remove(file)
    logger.log('OTHER', 'All previous csv-files are deleted')
    for file in list_of_files_tmp:
        p = Path(file)
        p.rename(p.with_suffix('.csv'))
    logger.log('OTHER', 'Tmp-files are renamed to csv')
    return True


def get_row_value(row, column_name, default=''):
    """Safely get a column value from a sqlite3.Row object."""
    try:
        return row[column_name]
    except (IndexError, KeyError):
        return default


def connection_to_sql(name: str):
    try:
        if name == "user_settings.db" or name == "calendars_list.db":
            name=f'dbs/{name}'
        conn = sqlite3.connect(database=name, timeout=SQL_TIMEOUT)
        try:
            # Improve concurrency for multiple processes by enabling WAL mode
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute('PRAGMA synchronous=NORMAL;')
            conn.execute('PRAGMA foreign_keys=ON;')
        except Exception:
            # If PRAGMA execution fails, continue with the connection (best-effort)
            pass
        logger.log('SQL', 'Successfully connect to sql db <' + name + '>')
    except sqlite3.Error as error:
        logger.error('Failed to read data from sql, error: ' + str(error))
        return None
    return conn


# Конвертирует CSV-файлы в SQL-файл
def convert_to_sql(csv_files_directory: str):
    logger.log('OTHER', 'Request to convert csv to sql')
    # Текущая дата для filename
    date = pendulum.now(tz=TIMEZONE).format('YYYY-MM-DD_HH-mm-ss')
    # Если есть хоть один файл, который заканчивается на csv
    list_of_files = glob(csv_files_directory + '/*.csv')
    if list_of_files:
        pass
    else:
        logger.error('Cant convert to sql because no file exist in <' + csv_files_directory + '>')
        return False
    conn = connection_to_sql(name='timetable-dbs/timetable_' + date + '.db')
    for csv_file in list_of_files:
        logger.log('OTHER', 'Convert <' + csv_file + '> to SQL...')
        timetable_csv = pandas.read_csv(csv_file, encoding='windows-1251', sep=';')
        
        # Преобразование столбцов с ID и номерами в целые числа
        # Это обеспечивает консистентность типов данных независимо от кодировки CSV
        int_columns = ['Les', 'Subg', 'CafID', 'Subj_CafID']
        for col in int_columns:
            if col in timetable_csv.columns:
                # Заполняем NaN значения нулём, затем преобразуем в int
                timetable_csv[col] = timetable_csv[col].fillna(0).astype('int64')
        
        timetable_csv['Group'] = timetable_csv['Group'].astype(str)

        # Удаление пробелов только из значений в колонке 'Group'
        timetable_csv['Group'] = timetable_csv['Group'].str.replace(' ', '')
        
        # Замена значений, содержащих только пробелы, на None в колонке 'Name'
        timetable_csv['Name'] = timetable_csv['Name'].replace(r'^\s*$', None, regex=True)        
        
        timetable_csv.to_sql(name='timetable', con=conn, if_exists='append', index=False)
        logger.log('OTHER', 'File <' + csv_file + '> successfully converted to timetable_' + date + '.db')
    conn.commit()
    conn.close()
    return True

