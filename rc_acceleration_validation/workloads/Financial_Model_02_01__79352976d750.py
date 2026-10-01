
import openpyxl
wb = openpyxl.load_workbook('input.xlsx', data_only=False)
ws = wb['Revenue & COGS Schedule']
for r in [18,19,20,21,22,23]:
    print(r, [ws.cell(row=r,column=c).value for c in range(1,17)])
