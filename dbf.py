from dbfread import DBF


def connect_to_dbf():
    return DBF('downloads/*.dbf', encoding='cp866', load=True)


# for i in connect_to_dbf():
#     print(i)