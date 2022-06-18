from other import sendMail, connection_to_sql
from sql_db import write_msg_vk_chat, write_msg_vk_user, write_msg_telegram
from logger import logger
from sqlite3 import Row
import argparse
import asyncio

parser = argparse.ArgumentParser(description='Sending messages to email, VK and telegram')
parser.add_argument('--message-file', dest='message', type=str, help='Message from file that will be sent.\n--message-file "file.txt"')
parser.add_argument('--platform', dest='platform', type=str, help='Platform to be used.\nVK: --platform "vk", email: --platform "email", telegram: --platform "telegram", all: --platform "all"')

args = parser.parse_args()

logger.log('SENDING', f'Run "sending_messages.py", args: message-file - <{args.message}>, platform - <{args.platform}>')

with open(args.message, 'r', encoding='utf-8') as f:
    message = f.read()

# Рассылка сообщений в почту
if args.message is not None and (args.platform == 'all' or args.platform == 'email'):
    logger.log('SENDING', 'Work for email is started...')
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = Row
    c = conn.cursor()
    users = c.execute('SELECT * FROM email WHERE notification = 1').fetchall()
    c.close()
    conn.close()
    for user in users:
        sendMail(to_email=user['email'], subject='Информирование об изменениях', text=message)
    logger.log('SENDING', 'Email finished')

# Рассылка сообщений в ВК
if args.message is not None and (args.platform == 'all' or args.platform == 'vk'):
    logger.log('SENDING', 'Work for vk is started...')
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = Row
    c = conn.cursor()
    users = c.execute('SELECT * FROM vk_user WHERE notification = 1').fetchall()
    chats = c.execute('SELECT * FROM vk_chat WHERE notification = 1').fetchall()
    c.close()
    conn.close()
    for user in users:
        asyncio.run(write_msg_vk_user(message=message, user_id=user['vk_id']))
    for chat in chats:
        asyncio.run(write_msg_vk_chat(message=message, chat_id=chat['vk_id']))
    logger.log('SENDING', 'VK finished')

# Рассылка сообщений в Telegram
if args.message is not None and (args.platform == 'all' or args.platform == 'telegram'):
    logger.log('SENDING', 'Work for telegram is started...')
    conn = connection_to_sql('user_settings.db')
    conn.row_factory = Row
    c = conn.cursor()
    users = c.execute('SELECT * FROM telegram WHERE notification = 1').fetchall()
    c.close()
    conn.close()
    list_ids = []
    for user in users:
        list_ids += [user['telegram_id']]
    asyncio.run(write_msg_telegram(message=message, tg_id=list_ids))
    logger.log('SENDING', 'Telegram finished')
