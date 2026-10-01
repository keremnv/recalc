
import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ws=wb['IS,BS,CF']
for row in ws.iter_rows(min_row=1,max_row=121):
    for c in row:
        if c.value is not None:
            print(c.coordinate, repr(c.value))
