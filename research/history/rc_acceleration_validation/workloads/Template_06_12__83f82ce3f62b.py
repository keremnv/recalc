
import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['CashFlow_Build']
for r in range(6,15):
    for col in 'BCDEFGHIJKLMN':
        c = ws[f'{col}{r}']
        print(c.coordinate, c.number_format, c.font.b, c.font.i, c.fill.fgColor.rgb if c.fill and c.fill.patternType else None, c.border.left.style, c.border.top.style)
