
import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ws=wb.active
for r in range(23,33):
    for c in range(2,11):
        cell=ws.cell(r,c)
        if cell.value is not None:
            print(cell.coordinate, repr(cell.value), cell.number_format)
