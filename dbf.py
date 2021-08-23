from dbfread import DBF


def connect_to_dbf():
    return DBF('downloads/*.dbf', encoding='cp866', load=True)



# a = []
# for i in connect_to_dbf():
#     if i[''] == '307':
#         a.append(i)
#         print(i)

# print(a)
