import openpyxl

wb = openpyxl.load_workbook("example.xlsx")
ws = wb["Sheet1"]
print(ws["A2"].value)
wb.close()
