import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ws=wb["Model"]
for row in ws.iter_rows(min_row=23,max_row=77,min_col=2,max_col=27):
    for c in row:
        if c.value is not None:
            print(c.coordinate, repr(c.value))
