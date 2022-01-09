from multiprocessing import Process
from logger import logger
from mail import processingMail
from vk import start_vk_server
from other import create_required_dirs


if __name__ == '__main__':
    create_required_dirs()
    p1 = Process(target=processingMail)
    p2 = Process(target=start_vk_server)
    try:
        p1.start()
        p2.start()
    except KeyboardInterrupt:
        logger.success('Running servers has been stopped by Ctrl+C')
        p1.terminate()
        p2.terminate()
        p1.close()
        p2.close()
