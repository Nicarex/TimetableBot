from loguru import logger
import vk


# Remove default logger handler settings
logger.remove(0)

# Обработка ERROR сообщений
logger.add('log_files/error.log', enqueue=True, encoding='utf-8', level='ERROR')
handler = vk.vk.messages.send(peer_id=235876671, message='Произошла ошибка в боте!', random_id=vk.get_random_id())
logger.add(handler, enqueue=True, encoding='utf-8', level='ERROR')


# Сообщения из сервисов
def incoming_message(message):
    id_handler = logger.add('log_files/incoming_messages.log', format='{time:YYYY-MM-DD HH:mm:ss} | {message}', rotation='1 week', compression='zip', enqueue=True, encoding='utf-8', level='INFO')
    logger.info(message)
    logger.remove(id_handler)


# Debug сообщения из сервисов
def debug_message(message):
    id_handler = logger.add('log_files/debug.log', format='{time:YYYY-MM-DD HH:mm:ss} | {message}', rotation='1 month', compression='zip', enqueue=True, encoding='utf-8', level='DEBUG')
    logger.debug(message)
    logger.remove(id_handler)


incoming_message(message='Test message')
debug_message(message='All ok!')
incoming_message(message='All fine!')
debug_message(message='End!')
incoming_message(message='Oopss...')
debug_message(message='Who?')
