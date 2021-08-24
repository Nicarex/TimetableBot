from dbfread import DBF
from operator import itemgetter


def connect_to_dbf():
    return DBF('downloads/*.dbf', encoding='cp866', load=True)


# for record in connect_to_dbf():
#     if record['GROUP'] == '307' and record['WEEK'] == '40':
#         print(record)
#
#
#
# print()
#
# a = []
# for i in connect_to_dbf():
#     if i['NAME'] == 'Будыкина Т.А.' and i['WEEK'] == '40':
#         a.append(i)
#         # print(i)
#
#
# def sort_by_day_and_les(item):
#     return int(item['WEEK']), int(item['DAY']), int(item['LES']), str(item['GROUP'])
#
#
# a.sort(key=sort_by_day_and_les)
# for i in a:
#     print(i)



