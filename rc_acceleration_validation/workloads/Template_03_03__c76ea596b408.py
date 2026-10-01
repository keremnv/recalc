import openpyxl
wbi=openpyxl.load_workbook('input.xlsx')
wsi=wbi["Consolidation"]
print("input E41:", repr(wsi["E41"].value))
for r in range(40,44):
    print(r, [wsi.cell(row=r,column=c).value for c in range(2,7)])
