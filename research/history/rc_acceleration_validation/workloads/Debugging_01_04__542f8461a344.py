
import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
for ws in wb.worksheets:
    print('='*80)
    print('SHEET:', ws.title, ws.dimensions)
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None:
                print(c.coordinate, repr(c.value))
