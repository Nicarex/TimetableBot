from multiprocessing import Manager, Process
from logger import logger
from mail import processingMail
from vk import start_vk_server
from other import create_required_dirs


if __name__ == '__main__':
    # Создание директорий
    create_required_dirs()
    # Запуск процессов
    processes = []
    manager = Manager()
    p1 = Process(target=processingMail)
    p2 = Process(target=start_vk_server)
    p1.start()
    processes.append(p1)
    p2.start()
    processes.append(p2)
    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        logger.warning('Catch Ctrl+C, stop processes...')
    finally:
        logger.warning('Running processes has been stopped')
