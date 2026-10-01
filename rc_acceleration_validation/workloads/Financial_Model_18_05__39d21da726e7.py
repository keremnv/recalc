
import openpyxl
wb=openpyxl.load_workbook('input.xlsx')
ms=wb['Milestones']; cb=wb['Cash Budget']
print(repr(ms['B9'].value), ms['B9'].data_type, repr(ms['E8'].value))
print(repr(cb['T35'].value), repr(cb['C5'].value), repr(cb['R41'].value))
