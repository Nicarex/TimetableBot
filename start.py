from multiprocessing import Manager, Process
from logger import logger
from mail import processingMail
from vk import start_vk_server
from discord import start_discord_server
from telegram import start_telegram_server
from other import create_required_dirs


if __name__ == '__main__':
    # Создание директорий
    try:
        create_required_dirs()
        logger.info('Required directories created successfully')
    except Exception as e:
        logger.critical(f'Failed to create required directories: {e}')
        exit(1)

    # Сервисы для запуска
    services = [
        (processingMail, 'Mail service'),
        (start_vk_server, 'VK service'),
        (start_telegram_server, 'Telegram service'),
        (start_discord_server, 'Discord service')
    ]
    processes = []
    manager = Manager()
    for target, name in services:
        try:
            p = Process(target=target)
            p.start()
            processes.append(p)
            logger.info(f'Started {name}')
        except Exception as e:
            logger.critical(f'Failed to start {name}: {e}')

    try:
        for process, (_, name) in zip(processes, services):
            process.join()
            logger.info(f'{name} finished')
    except KeyboardInterrupt:
        logger.warning('Catch Ctrl+C, stopping all processes...')
    finally:
        for process, (_, name) in zip(processes, services):
            if process.is_alive():
                process.terminate()
                logger.info(f'{name} terminated')
        logger.warning('All running processes have been stopped')
