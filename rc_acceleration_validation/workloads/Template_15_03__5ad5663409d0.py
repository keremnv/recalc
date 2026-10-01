
import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['LoanSizing']
for coord in ['C30','C38','E38','C39','E39','C43','E43','C44','C45','E45','C49','E49','C53','E53','C55','C56','C57']:
    c = ws[coord]
    print(coord, c.number_format)
