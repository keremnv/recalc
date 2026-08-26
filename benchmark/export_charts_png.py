#!/usr/bin/env python3
"""Export charts from an .xlsx to PNG using native LibreOffice GraphicExportFilter.

This is the Linux scoring bridge: agent outputs stay .xlsx; PNGs feed the VLM checklist
evaluator (OpenRouter glm-4.6v) without Windows Excel COM.

Requires a running LibreOffice UNO listener (same as LIBRECALC_RUN_UNO=1 tests).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from librecalc_mcp.backend.uno import UnoCalcBackend


def _stitch(paths: list[Path], destination: Path) -> None:
    images = [Image.open(path).convert("RGBA") for path in paths]
    width = max(image.width for image in images)
    height = sum(image.height for image in images) + 8 * (len(images) - 1)
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    y = 0
    for image in images:
        canvas.paste(image, (0, y))
        y += image.height + 8
    canvas.convert("RGB").save(destination, format="PNG")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--task-id",
        required=True,
        help="SpreadsheetBench task id; writes <task-id>_output.png for the VLM evaluator",
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2021)
    args = parser.parse_args()

    xlsx = args.xlsx.resolve()
    if not xlsx.is_file():
        raise SystemExit(f"missing workbook: {xlsx}")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    backend = UnoCalcBackend(host=args.host, port=args.port)
    health = backend.health()
    if not health.get("ok"):
        raise SystemExit(f"UNO unavailable: {health}")

    prefix = args.task_id.replace(" ", "_")
    exported = backend.export_charts_png(str(xlsx), str(output_dir), file_prefix=prefix)
    if not exported:
        raise SystemExit(f"no charts exported from {xlsx}")

    scored_name = f"{args.task_id}_output.png"
    scored_path = output_dir / scored_name
    paths = [Path(path) for path in exported]
    if len(paths) == 1:
        shutil.copy2(paths[0], scored_path)
    else:
        _stitch(paths, scored_path)

    print(
        {
            "ok": True,
            "charts": len(exported),
            "exported": exported,
            "vlm_png": str(scored_path),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
