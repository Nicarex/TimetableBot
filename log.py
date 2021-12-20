from loguru import logger


logger.add('log/file_{time}.log', level='TRACE', rotation='30 MB', enqueue=True, encoding='utf-8', compression='zip', catch=True)
logger.level(name='EMAIL', no=20, color='<yellow>')
logger.level(name='VK', no=20, color='<red>')

logger.info('Start logging...')