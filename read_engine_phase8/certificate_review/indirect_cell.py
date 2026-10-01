import openpyxl

wb = openpyxl.load_workbook("input.xlsx")
ws = wb["Sheet"]
cell_method = ws.__getattribute__("cell")
cell = cell_method(1, 2)
print(type(cell).__name__, repr(cell))
