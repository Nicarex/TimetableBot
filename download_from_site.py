# скачивание файлов с сайта
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings()  # отключение уведомлений


def DownloadFile(file):
    url = 'https://amchs.ru/students/raspisanie/'  # адрес сайта
    result = requests.get(url, verify=False) # игнор сертификата
    soup = BeautifulSoup(result.text, 'html.parser')
    for a in soup.find_all(class_='fz16', href=True):  # файлы с ссылками
        post = 'https://amchs.ru' + a['href']
        r = requests.get(post, verify=False)
        filename = post.split('/')[-1]
        if filename == file:  # если файл со страницы совпадает с запросом
            open(filename, 'wb').write(r.content)
            print('File', filename, 'downloaded')
