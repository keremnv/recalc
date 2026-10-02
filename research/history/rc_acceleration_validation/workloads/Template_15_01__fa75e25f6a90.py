
import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['DebtAnalysis']
for row in ws.iter_rows(min_row=1, max_row=50, min_col=1, max_col=6):
    for c in row:
        if c.value is not None:
            print(c.coordinate, repr(c.value), c.number_format)
