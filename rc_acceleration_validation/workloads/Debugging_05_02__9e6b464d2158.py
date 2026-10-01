import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ws=wb["Model"]
for r in [11,39,40,41,43,44,45,46,63,71,72,80]:
    print(r,[ws.cell(row=r,column=c).value for c in range(2,28)])
