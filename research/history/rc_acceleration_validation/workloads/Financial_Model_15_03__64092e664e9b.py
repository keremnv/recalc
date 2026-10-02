
import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ws=wb['IS_BS_CF']
for row in ws.iter_rows(min_row=1,max_row=181,max_col=45):
    for c in row:
        if c.value is not None:
            print(c.coordinate, repr(c.value))
