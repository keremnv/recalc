import openpyxl

book = openpyxl.load_workbook("input.xlsx")
book.active["B2"] = "=1+2"
book.save("input.xlsx")
