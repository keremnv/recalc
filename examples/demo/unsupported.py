import sys
import time

import openpyxl

t0 = time.perf_counter()
wb = openpyxl.load_workbook("model.xlsx")
ws = wb["Forecast"]
count = 0
seen_total = None
for row in ws.iter_rows(values_only=True):
    count += 1
    if count == 402:
        seen_total = row[7]
print("rows seen:", count)
print("H402 via iteration:", seen_total)
wb.close()
t1 = time.perf_counter()
print(f"read phase: {(t1 - t0) * 1000:.1f} ms", file=sys.stderr)
