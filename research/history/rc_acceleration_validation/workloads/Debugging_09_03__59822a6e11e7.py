
import openpyxl, warnings
warnings.filterwarnings('ignore')
wb=openpyxl.load_workbook('input.xlsx')
for n,d in wb.defined_names.items(): print(n, d.value)
ws=wb['LBO']
print('validations LBO:', [(dv.sqref, dv.formula1) for dv in ws.data_validations.dataValidation])
ws2=wb['Financials']
print('validations Fin:', [(dv.sqref, dv.formula1) for dv in ws2.data_validations.dataValidation])
