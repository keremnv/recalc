
import openpyxl
wb = openpyxl.load_workbook('input.xlsx', data_only=False)
ws = wb['Revenue & COGS Schedule']
for r in [5,13,17,20,21,23]:
    print(r, [ws.cell(row=r,column=c).value for c in range(1,17)])
