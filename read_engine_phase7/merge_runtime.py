"""Only Phase-7 treatment change: certified covered-child cell routing."""
from __future__ import annotations

from read_engine_phase3 import runtime as frozen


def install_cell_route() -> None:
    def cell(self, row=1, column=1):
        if not isinstance(row, int) or not isinstance(column, int) or row < 1 or column < 1:
            raise ValueError("Row or column values must be at least 1")
        for r1, c1, r2, c2 in self._sheet.info.merged:
            if r1 <= row <= r2 and c1 <= column <= c2 and (row, column) != (r1, c1):
                runtime = self._workbook._runtime
                runtime.record("merged_child_contact", sheet=self.title, row=row, column=column)
                if runtime.context.get("merged_terminal_certified", False):
                    runtime.record("merged_child_direct", sheet=self.title, row=row, column=column)
                    runtime.counts["direct_served_reads"] += 1
                    return frozen.ProxyCell(self, row, column)
                runtime.record("merged_child_reference", sheet=self.title, row=row, column=column)
                return self._real_sheet().cell(row=row, column=column)
        self._workbook._runtime.counts["direct_served_reads"] += 1
        return frozen.ProxyCell(self, row, column)

    frozen.ProxyWorksheet.cell = cell
