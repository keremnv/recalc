import openpyxl

wb = openpyxl.load_workbook("example.xlsx")
ws = wb["Sheet1"]
ws["B2"] = "=A2*2"
wb.save("output.xlsx")
wb.close()
print("Saved output.xlsx with B2 = =A2*2")
