from multiprocessing import Process
from vk import vk_start_server
from mail import run_program_at_time


if __name__ == '__main__':
    Process(target=vk_start_server).start()
    Process(target=run_program_at_time).start()
