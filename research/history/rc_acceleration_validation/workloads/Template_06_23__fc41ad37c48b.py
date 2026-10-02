
import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
for ws in wb:
    print(ws.title, ws.dimensions)
