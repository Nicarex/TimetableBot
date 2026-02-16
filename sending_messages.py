from other import sendMail, connection_to_sql, NotificationError, DatabaseError, db_connection
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
    with db_connection('user_settings.db', row_factory=Row) as conn:
        c = conn.cursor()
        users = c.execute("SELECT * FROM users WHERE platform = 'email' AND notification = 1").fetchall()
    for user in users:
        try:
            sendMail(to_email=user['platform_id'], subject='Информирование об изменениях', text=message)
        except NotificationError as e:
            logger.log('SENDING', f'Failed to send email to {user["platform_id"]}: {e}')
    logger.log('SENDING', 'Email finished')

# Рассылка сообщений в ВК
if args.message is not None and (args.platform == 'all' or args.platform == 'vk'):
    logger.log('SENDING', 'Work for vk is started...')
    with db_connection('user_settings.db', row_factory=Row) as conn:
        c = conn.cursor()
        users = c.execute("SELECT * FROM users WHERE platform = 'vk_user' AND notification = 1").fetchall()
        chats = c.execute("SELECT * FROM users WHERE platform = 'vk_chat' AND notification = 1").fetchall()
    for user in users:
        asyncio.run(write_msg_vk_user(message=message, user_id=user['platform_id']))
    for chat in chats:
        asyncio.run(write_msg_vk_chat(message=message, chat_id=chat['platform_id']))
    logger.log('SENDING', 'VK finished')

# Рассылка сообщений в Telegram
if args.message is not None and (args.platform == 'all' or args.platform == 'telegram'):
    logger.log('SENDING', 'Work for telegram is started...')
    with db_connection('user_settings.db', row_factory=Row) as conn:
        c = conn.cursor()
        users = c.execute("SELECT * FROM users WHERE platform = 'telegram' AND notification = 1").fetchall()
    list_ids = [user['platform_id'] for user in users]
    asyncio.run(write_msg_telegram(message=message, tg_id=list_ids))
    logger.log('SENDING', 'Telegram finished')
