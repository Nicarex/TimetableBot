from dbfread import DBF
import os


def connect_to_dbf():
    records = []
    for filename in os.listdir('downloads'):
        table = DBF('downloads/'+filename, encoding='cp866', load=True)
        for record in table:
            records.append(record)
    return records
