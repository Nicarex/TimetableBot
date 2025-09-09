from multiprocessing import Manager, Process
from logger import logger
from mail import processingMail
from vk import start_vk_server
from discord import start_discord_server
from telegram import start_telegram_server
from other import create_required_dirs


import time

def start_service(target, name):
    try:
        p = Process(target=target)
        p.start()
        logger.info(f'Started {name} (pid={p.pid})')
        return p
    except Exception as e:
        logger.critical(f'Failed to start {name}: {e}')
        return None

import os

def config_exists():
    return os.path.isfile('config.ini')

if __name__ == '__main__':
    # Проверка наличия config.ini
    if not config_exists():
        logger.critical('Config file config.ini not found. Application will exit gracefully.')
        exit(0)
    # Создание директорий
    try:
        create_required_dirs()
        logger.info('Required directories created successfully')
    except Exception as e:
        logger.critical(f'Failed to create required directories: {e}')
        exit(1)

    services = [
        (processingMail, 'Mail service'),
        (start_vk_server, 'VK service'),
        (start_telegram_server, 'Telegram service'),
        (start_discord_server, 'Discord service')
    ]
    manager = Manager()
    processes = []
    for target, name in services:
        p = start_service(target, name)
        processes.append({'process': p, 'target': target, 'name': name})

    try:
        while True:
            for proc_info in processes:
                p = proc_info['process']
                name = proc_info['name']
                target = proc_info['target']
                if p is not None and not p.is_alive():
                    logger.warning(f'{name} (pid={p.pid}) stopped unexpectedly. Restarting...')
                    p.terminate()
                    new_p = start_service(target, name)
                    proc_info['process'] = new_p
            time.sleep(5)
    except KeyboardInterrupt:
        logger.warning('Catch Ctrl+C, stopping all processes...')
    finally:
        for proc_info in processes:
            p = proc_info['process']
            name = proc_info['name']
            if p is not None and p.is_alive():
                p.terminate()
                logger.info(f'{name} terminated')
        logger.warning('All running processes have been stopped')
