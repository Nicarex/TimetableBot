from multiprocessing import Process
from threading import Thread
from vk import vk_start_server
from mail import run_program_at_time

def test1():
    while True:
        print('1')

def test2():
    while True:
        print('2')


# threadA = Thread(target=test1())
# threadB = Thread(target=test2())
# threadA.start()
# threadB.start()
# threadA.run()
# threadB.run()
# threadA.join()
# threadB.join()


if __name__ == '__main__':
    Process(target=vk_start_server).start()
    Process(target=run_program_at_time).start()
