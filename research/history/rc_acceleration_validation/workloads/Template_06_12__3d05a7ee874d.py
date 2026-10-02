
import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['CashFlow_Build']
for r in range(8,34):
    vals=[]
    for col in 'BCDEFGHIJKLMN':
        c = ws[f'{col}{r}']
        v=c.value
        vals.append(f'{col}{r}={v!r}')
    print(' | '.join(vals))
