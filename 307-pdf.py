from dbfread import DBF
table = DBF('КИФ, ФПИС, ФРС - 1 семестр 20-21 учебного года.DBF', encoding='cp866', load=True)
for record in table:
    if record['GROUP'] == '307':
        print(record)

