import os
import openpyxl

book = openpyxl.load_workbook("input.xlsx")
book.active["A1"] = "phase8a-abrupt-exit"
book.save("input.xlsx")
os._exit(7)
