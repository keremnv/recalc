import openpyxl

book = openpyxl.load_workbook("input.xlsx")
sheet = book.create_sheet("Phase8 added")
sheet["A1"] = "created"
book.save("input.xlsx")
