import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ws=wb["Financial Performance"]
for r in range(4,21):
    print(r,[ws.cell(row=r,column=c).value for c in range(2,23)])
