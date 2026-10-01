import openpyxl

book = openpyxl.load_workbook("input.xlsx")
sheet = book.active
for row in range(1, 21):
    sheet.cell(row=row, column=3).value = row * 2
book.save("input.xlsx")
