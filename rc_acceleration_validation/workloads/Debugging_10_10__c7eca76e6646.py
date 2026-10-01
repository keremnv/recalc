
import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ws=wb['Model']
for row in ws.iter_rows(min_row=1,max_row=200):
    for c in row:
        if c.value is not None:
            print(c.coordinate,repr(c.value))
