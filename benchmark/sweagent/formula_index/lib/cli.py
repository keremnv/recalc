"""formula_index CLI — unranked relative-formula equivalence index."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from render import render_classes
from workbook import build_index


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Unranked index of mechanically established relative-formula equivalence "
            "in an existing workbook. Opaque formulas are not grouped."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    range_cmd = sub.add_parser("range", help="classes represented by formulas in a range")
    range_cmd.add_argument("xlsx")
    range_cmd.add_argument("sheet")
    range_cmd.add_argument("a1_range")

    axis_cmd = sub.add_parser("axis", help="classes with a member on a row and/or column")
    axis_cmd.add_argument("xlsx")
    axis_cmd.add_argument("sheet")
    axis_cmd.add_argument("--row", type=int)
    axis_cmd.add_argument("--col", type=int)

    lookup_cmd = sub.add_parser("lookup", help="full compressed membership for one eq_id")
    lookup_cmd.add_argument("xlsx")
    lookup_cmd.add_argument("eq_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    path = Path(args.xlsx)
    if not path.is_file():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 2
    index = build_index(path)
    if args.command == "range":
        records = index.classes_in_range(args.sheet, args.a1_range)
        print(
            render_classes(
                kind="range",
                header_fields=[f"sheet={args.sheet}", f"range={args.a1_range}"],
                records=records,
            ),
            end="",
        )
        return 0
    if args.command == "axis":
        if args.row is None and args.col is None:
            print("Error: axis requires --row and/or --col", file=sys.stderr)
            return 2
        records = index.classes_on_axis(args.sheet, row=args.row, col=args.col)
        fields = [f"sheet={args.sheet}"]
        if args.row is not None:
            fields.append(f"row={args.row}")
        if args.col is not None:
            fields.append(f"col={args.col}")
        print(render_classes(kind="axis", header_fields=fields, records=records), end="")
        return 0
    if args.command == "lookup":
        record = index.lookup(args.eq_id)
        if record is None:
            print(
                f"formula_index lookup eq_id={args.eq_id} classes=0 "
                "truncated=false omitted_geometry=0"
            )
            print("not_found true")
            return 0
        print(
            render_classes(
                kind="lookup",
                header_fields=[f"eq_id={args.eq_id}"],
                records=[record],
            ),
            end="",
        )
        return 0
    return 2
