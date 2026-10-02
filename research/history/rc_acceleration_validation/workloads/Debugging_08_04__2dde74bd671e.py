import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ws=wb['Operating Model + DCF']
for r in range(2,40):
    vals=[]
    for c in range(1,24):
        cell=ws.cell(r,c)
        if cell.value is not None: vals.append((cell.coordinate,str(cell.value)[:40]))
    print(r,vals)
