from multiprocessing import Manager, Process
from logger import logger
from mail import processingMail
from vk import start_vk_server
from discord import start_discord_server
from telegram import start_telegram_server
from other import create_required_dirs


if __name__ == '__main__':
    # Создание директорий
    create_required_dirs()
    # Запуск процессов
    processes = []
    manager = Manager()
    p1 = Process(target=processingMail)
    p1.start()
    processes.append(p1)
    p2 = Process(target=start_vk_server)
    p2.start()
    processes.append(p2)
    p3 = Process(target=start_telegram_server)
    p3.start()
    processes.append(p3)
    p4 = Process(target=start_discord_server)
    p4.start()
    processes.append(p4)
    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        logger.warning('Catch Ctrl+C, stop processes...')
    finally:
        logger.warning('Running processes has been stopped')
