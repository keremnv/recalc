import os
import signal
import openpyxl

book = openpyxl.load_workbook("input.xlsx")
book.active["A1"] = "phase8a-fatal-signal"
book.save("input.xlsx")
os.kill(os.getpid(), signal.SIGTERM)
