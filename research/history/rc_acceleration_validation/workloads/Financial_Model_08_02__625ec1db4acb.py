
import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ws=wb['Capex and Debt Assumptions ']
for row in ws.iter_rows(min_row=1,max_row=200,max_col=40):
    for c in row:
        if c.value is not None:
            print(c.coordinate, repr(c.value))
