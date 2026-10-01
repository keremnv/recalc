import openpyxl
wb = openpyxl.load_workbook('input.xlsx', data_only=False)
ws = wb['Balance Sheet']
print('--- Balance Sheet rows 6-34 (cols B-H) ---')
for r in range(6, 35):
    vals = []
    for c in range(2, 10):
        v = ws.cell(row=r, column=c).value
        if v is not None:
            vals.append((ws.cell(row=r, column=c).coordinate, repr(v)[:90]))
    if vals:
        print(r, vals)
