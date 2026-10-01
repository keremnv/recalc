import openpyxl

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Sheet1"
ws["A2"] = 21
wb.save("example.xlsx")
wb.close()
