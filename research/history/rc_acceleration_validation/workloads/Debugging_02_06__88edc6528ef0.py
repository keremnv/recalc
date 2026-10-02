
import openpyxl
from openpyxl.cell.cell import MergedCell
wb = openpyxl.load_workbook('input.xlsx', data_only=False)
ws = wb['Exhibit 9']
for r in range(1,28):
    for col in ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q']:
        c = ws[f'{col}{r}']
        if not isinstance(c, MergedCell) and c.value is not None:
            print(col+str(r), repr(c.value))
