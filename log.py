from loguru import logger


logger.add('log/file_{time}.log', level='INFO', rotation='30 MB', enqueue=True, encoding='utf-8', compression='zip', catch=True)


logger.info('Start logging...')