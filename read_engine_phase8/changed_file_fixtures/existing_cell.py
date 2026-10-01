import openpyxl

book = openpyxl.load_workbook("input.xlsx")
book.active["A1"] = "phase8-value"
book.save("input.xlsx")
