
import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ws=wb.active
for r in (24,25,26):
    for c in range(3,11):
        cell=ws.cell(r,c)
        v=cell.value
        if hasattr(v,'text'): print(cell.coordinate, v.ref, repr(v.text))
