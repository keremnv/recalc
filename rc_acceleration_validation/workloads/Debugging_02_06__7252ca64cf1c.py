
import openpyxl
wb = openpyxl.load_workbook('input.xlsx', data_only=False)
ws = wb['Exhibit 9']
for row in ws.iter_rows(min_row=1, max_row=40, max_col=20):
    for c in row:
        if c.value is not None:
            print(c.coordinate, repr(c.value))
