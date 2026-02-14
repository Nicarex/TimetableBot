from loguru import logger
import logging.handlers
import platform
import sys

# Удаление встроенного логгера
logger.remove()

# Добавление уровней логгирования
logger.level(name='MAIL', no=30, color='<light-yellow>')
logger.level(name='VK', no=30, color='<light-magenta>')
logger.level(name='TELEGRAM', no=30, color='<blue>')
logger.level(name='DISCORD', no=30, color='<white>')
logger.level(name='SQL', no=30, color='<light-red>')
logger.level(name='OTHER', no=30, color='<light-cyan>')
logger.level(name='TIMETABLE', no=30, color='<light-green>')
logger.level(name='CALENDAR', no=30, color='<light-blue>')
logger.level(name='SENDING', no=30, color='<light-black>')
logger.level(name='EXCEL', no=30, color='<green>')

# Вывод лога в файл и консоль
logger.add('log/file_{time}.log', level=30, rotation='30 MB', enqueue=True, encoding='utf-8', compression='zip', catch=True)
logger.add(sys.stdout, enqueue=True, level=30, catch=True)

# # Логгирование в Syslog Linux
# if platform.system() == 'Linux':
#     handler = logging.handlers.SysLogHandler(address='/dev/log')
#     logger.add(handler, format="{level} | {message}", level=30, catch=True, enqueue=True)
