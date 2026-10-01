import openpyxl

book = openpyxl.load_workbook("input.xlsx")
book.active["D4"] = "output-only"
book.save("output.xlsx")
