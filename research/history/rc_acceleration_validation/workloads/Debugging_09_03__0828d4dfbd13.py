
import openpyxl, warnings
warnings.filterwarnings('ignore')
wb=openpyxl.load_workbook('input.xlsx')
ws=wb['Operating Cases']
for row in ws.iter_rows():
    vals=[(c.coordinate,c.value) for c in row if c.value is not None]
    if vals: print(vals)
