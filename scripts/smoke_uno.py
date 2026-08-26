from pathlib import Path
from tempfile import TemporaryDirectory

from librecalc_mcp.backend.uno import UnoCalcBackend
from librecalc_mcp.domain.models import CalcOperation

backend = UnoCalcBackend()
health = backend.health()
print(health)
if not health.get("ok"):
    raise SystemExit(1)

fixture_path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "smoke.csv"
workbook = backend.inspect_workbook(str(fixture_path))
sheet = workbook.sheets[0].name

with TemporaryDirectory(prefix="librecalc-smoke-") as directory:
    source_path = Path(directory, "source.xlsx")
    output_path = Path(directory, "output.xlsx")

    print(
        backend.write_range(
            sheet,
            "A1:B2",
            [["Revenue", "Cost"], [100, 60]],
            path=str(fixture_path),
            output_path=str(source_path),
        )
    )
    print(
        backend.execute_program(
            [CalcOperation(op="set_formula", sheet=sheet, range="C2", formula="=A2-B2")],
            path=str(source_path),
            output_path=str(output_path),
        )
    )

    result = backend.read_range(sheet, "A1:C2", path=str(output_path))
    print(result)
    assert result["values"][1][2] == 40
    assert backend.read_range(sheet, "C2", path=str(source_path))["values"] == [[""]]
