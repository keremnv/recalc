from librecalc_mcp.backend.uno import UnoCalcBackend

backend = UnoCalcBackend()
print(backend.health())
if backend.health().get("ok"):
    print(backend.inspect_workbook())
