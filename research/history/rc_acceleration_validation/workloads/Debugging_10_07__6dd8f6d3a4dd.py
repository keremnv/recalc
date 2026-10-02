
import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['FY2027P (IS)']
for row in ws.iter_rows(min_row=40, max_row=80, max_col=20):
    for c in row:
        if c.value is not None:
            print(c.coordinate, repr(c.value)[:150])
