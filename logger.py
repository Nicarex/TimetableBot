from loguru import logger
import sys

# Удаление встроенного логгера
logger.remove()

# Добавление уровней логгирования
logger.level(name='MAIL', no=30, color='<light-yellow>')
logger.level(name='VK', no=30, color='<light-magenta>')
logger.level(name='SQL', no=30, color='<light-red>')
logger.level(name='OTHER', no=30, color='<light-cyan>')
logger.level(name='TIMETABLE', no=30, color='<light-green>')
logger.level(name='CALENDAR', no=30, color='<light-blue>')

# Вывод лога
logger.add('log/file_{time}.log', level=30, rotation='30 MB', enqueue=True, encoding='utf-8', compression='zip', catch=True)
logger.add(sys.stderr, level=30, enqueue=True, catch=True)

