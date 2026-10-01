
import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['Assumptions']
for row in ws.iter_rows(min_row=30, max_row=45, max_col=20):
    for c in row:
        if c.value is not None:
            print(c.coordinate, repr(c.value))
