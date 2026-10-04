"""README vignette generator (documentation-only).

Verifies frozen inputs, recomputes derived numbers, renders the workbook crop
via LibreOffice, and composes docs/assets/recalc-performance-vignette.svg.

Usage:
  python3 docs/evidence/readme_vignette/generate.py --verify   # checks only
  python3 docs/evidence/readme_vignette/generate.py --build    # verify + render + compose
Requires: soffice, pdftoppm, PIL, openpyxl (render path only).
"""
import base64
import hashlib
import io
import json
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
ASSET = ROOT / "docs" / "assets" / "recalc-performance-vignette.svg"
CROP_PNG = HERE / "sheet_crop.png"


def load():
    scenario = json.loads((HERE / "scenario.json").read_text())
    timing = json.loads((HERE / "timing.json").read_text())
    prompt = (HERE / "prompt.txt").read_text()
    code = (HERE / "code_excerpt.py").read_text()
    return scenario, timing, prompt, code


def verify():
    scenario, timing, prompt, code = load()
    errors = []
    # 1. workbook hash (frozen benchmark input)
    wb = ROOT / scenario["input_workbook"]
    sha = hashlib.sha256(wb.read_bytes()).hexdigest()
    if sha != scenario["input_workbook_sha256"]:
        errors.append(f"workbook sha mismatch: {sha}")
    # 2. script hash
    csha = hashlib.sha256(code.encode()).hexdigest()
    if csha != scenario["frozen_script_sha256"]:
        errors.append(f"script sha mismatch: {csha}")
    # 3. prompt is a byte substring of the benchmark dataset instruction
    ds = json.loads((ROOT / "benchmark-data/SpreadsheetBench-2/data/Financial_Model/dataset.json").read_text())
    inst = [t for t in ds if t["id"] == "08_02"][0]["instruction"]
    if prompt.strip() != inst.strip():
        errors.append("prompt.txt is not the exact FM:08_02 instruction")
    # 4. recompute medians/saved/pct from raw reps
    bmed = statistics.median(timing["base_wall_s"])
    rmed = statistics.median(timing["recalc_wall_s"])
    saved = round(bmed - rmed, 4)
    pct = round(100 * saved / bmed, 2)
    if timing["base_median_s"] != bmed or timing["recalc_median_s"] != rmed:
        errors.append("median mismatch")
    if timing["saved_s"] != saved or timing["pct_lower"] != pct:
        errors.append(f"derived mismatch: {saved} {pct}")
    if timing["display"] != {"base": "3.69 s", "recalc": "0.73 s",
                             "saved": "2.95 s", "pct": "80.1% lower"}:
        errors.append("display strings mismatch")
    # 5. gates: exits/routes/status
    if timing["base_exits"] != [0, 0, 0] or timing["recalc_exits"] != [0, 0, 0]:
        errors.append("exit gate")
    if timing["routes"] != ["DIRECT_RUNTIME"] * 3:
        errors.append("route gate")
    if timing["artifact_status"] != [["REUSED"]] * 3:
        errors.append("reuse gate")
    if not timing["stdout_normalized_identical"]:
        errors.append("parity gate")
    if errors:
        print("VERIFY FAIL:")
        [print(" -", e) for e in errors]
        return False
    print("VERIFY PASS: hashes, prompt, medians (%.4f/%.4f), saved %.4fs, %.2f%% lower, "
          "DIRECTx3/REUSEDx3, normalized-stdout parity" % (bmed, rmed, saved, pct))
    return True


def render_crop():
    """LibreOffice render of the real Assumptions tab; trims to content."""
    import openpyxl
    from PIL import Image, ImageChops
    scenario = json.loads((HERE / "scenario.json").read_text())
    tmp = HERE / "_render_tmp"
    if tmp.exists():
        import shutil
        shutil.rmtree(tmp)
    tmp.mkdir()
    wb = openpyxl.load_workbook(ROOT / scenario["input_workbook"])
    for ws in wb.worksheets:
        if ws.title != "Assumptions - Line 01":
            ws.sheet_state = "hidden"
    ws = wb["Assumptions - Line 01"]
    ws.print_area = "A1:H24"
    ws.sheet_properties.pageSetUpPr = openpyxl.worksheet.properties.PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    wb.active = wb.sheetnames.index("Assumptions - Line 01")
    wb.save(tmp / "render.xlsx")
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "render.xlsx"],
                   cwd=tmp, capture_output=True, check=True)
    subprocess.run(["pdftoppm", "-png", "-r", "200", "-f", "1", "-l", "1",
                    "render.pdf", "crop"], cwd=tmp, capture_output=True, check=True)
    im = Image.open(tmp / "crop-1.png").convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bbox = ImageChops.difference(im, bg).getbbox()
    m = 24
    im = im.crop((max(0, bbox[0] - m), max(0, bbox[1] - m),
                  min(im.width, bbox[2] + m), min(im.height, bbox[3] + m)))
    im.save(CROP_PNG)
    import shutil
    shutil.rmtree(tmp)
    print(f"crop: {CROP_PNG} {im.size}")


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def compose():
    scenario, timing, prompt, code = load()
    d = timing["display"]
    with open(CROP_PNG, "rb") as f:
        png_b64 = base64.b64encode(f.read()).decode()
    from PIL import Image
    cw, ch = Image.open(CROP_PNG).size
    # Layout: 1200 wide. Left panel workbook (700), right panel code (440).
    W = 1200
    code_lines = [ln for ln in code.splitlines()]
    findings = [
        "B6 'Volume distribution per month'",
        "D6 'Volume % '",
        "B7 'Plant Capacity  '",
        "D7 'In KG'",
        "B8 'Base'",
        "F8 105000",
        "… (3,544 more lines, identical)",
    ]
    left_w, gap, right_w = 668, 24, W - 668 - 24 - 48
    img_h = int(left_w * ch / cw)
    top_h = 172
    mid_y = top_h + 8
    code_h = 60 + 24 * (len(code_lines) + 1) + 60
    mid_h = max(img_h + 92, code_h + 40)
    time_y = mid_y + mid_h + 8
    time_h = 210
    bot_y = time_y + time_h + 8
    bot_h = 76 + 24 * len(findings) + 64
    H = bot_y + bot_h + 24
    L, R = 24, 24 + left_w + gap

    def panel(x, y, w, h, title):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#ffffff" '
                f'stroke="#d0d7de" stroke-width="1.5"/>'
                f'<text x="{x + 16}" y="{y + 30}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" '
                f'font-size="15" font-weight="700" fill="#57606a">{esc(title)}</text>')

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" role="img">']
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="#f6f8fa"/>')
    # Prompt header
    parts.append(panel(24, 16, W - 48, top_h - 24, "SPREADSHEETBENCH-2 · FM:08_02 · PROJECT SEAFOOD MODEL"))
    parts.append(f'<text x="40" y="80" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="14" fill="#57606a">'
                 f'Public benchmark task — full 5-part instruction in docs/evidence/readme_vignette/prompt.txt</text>')
    parts.append(f'<text x="40" y="104" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="14" fill="#57606a">'
                 f'Full task includes modeling work across several sheets.</text>')
    parts.append(f'<text x="40" y="130" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="15" font-weight="700" fill="#1f2328">'
                 f'Measured here: read-only inspection of \u2018Assumptions - Line 01\u2019 — one step, not the whole task</text>')
    parts.append(f'<text x="{W//2}" y="{mid_y - 12}" text-anchor="middle" font-size="22" fill="#57606a">↓</text>')
    # Left: workbook
    parts.append(panel(L, mid_y, left_w, mid_h, "REAL WORKBOOK — input.xlsx · \u2018Assumptions - Line 01\u2019 (LibreOffice render)"))
    parts.append(f'<image x="{L}" y="{mid_y + 44}" width="{left_w}" height="{img_h}" '
                 f'href="data:image/png;base64,{png_b64}"/>')
    parts.append(f'<text x="{L + 16}" y="{mid_y + 44 + img_h + 26}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" '
                 f'font-size="14" fill="#1f2328">Scan region A1:AN120 · 4,800 cells served directly · values identical</text>')
    # Right: code
    parts.append(panel(R, mid_y, right_w, mid_h, "ORDINARY AGENT PYTHON"))
    y = mid_y + 66
    for ln in code_lines:
        parts.append(f'<text x="{R + 16}" y="{y}" font-family="ui-monospace,SFMono-Regular,Consolas,monospace" '
                     f'font-size="13.5" fill="#1f2328">{esc(ln) if ln.strip() else " "}</text>')
        y += 24
    parts.append(f'<text x="{R + 16}" y="{y + 34}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" '
                 f'font-size="14" fill="#57606a">No Recalc API · frozen agent scan step</text>')
    parts.append(f'<text x="{W//2}" y="{time_y - 12}" text-anchor="middle" font-size="22" fill="#57606a">↓</text>')
    # Timing
    parts.append(panel(24, time_y, W - 48, time_h, "LOCAL EXECUTION — SAME CODE, SAME VALUES DELIVERED"))
    parts.append(f'<text x="60" y="{time_y + 78}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="17" fill="#57606a">BASE (plain Python)</text>')
    parts.append(f'<text x="60" y="{time_y + 116}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="34" font-weight="800" fill="#1f2328">{d["base"]}</text>')
    parts.append(f'<text x="430" y="{time_y + 78}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="17" fill="#57606a">RECALC (warm, DIRECT_RUNTIME)</text>')
    parts.append(f'<text x="430" y="{time_y + 116}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="34" font-weight="800" fill="#0969da">{d["recalc"]}</text>')
    parts.append(f'<text x="820" y="{time_y + 78}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="17" fill="#57606a">Saved</text>')
    parts.append(f'<text x="820" y="{time_y + 116}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="34" font-weight="800" fill="#1a7f37">{d["saved"]} · {d["pct"]}</text>')
    parts.append(f'<text x="60" y="{time_y + 162}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="14" fill="#57606a">Medians of 3 warm reps, same window · artifact REUSED · model-provider latency excluded</text>')
    parts.append(f'<text x="60" y="{time_y + 186}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="14" fill="#57606a">Read-only inspection step; workbook bytes unchanged · Same agent code, same findings</text>')
    parts.append(f'<text x="{W//2}" y="{bot_y - 12}" text-anchor="middle" font-size="22" fill="#57606a">↓</text>')
    # Findings
    parts.append(panel(24, bot_y, W - 48, bot_h, "DELIVERED FINDINGS — IDENTICAL UNDER BASE AND RECALC"))
    y = bot_y + 62
    for ln in findings:
        parts.append(f'<text x="40" y="{y}" font-family="ui-monospace,SFMono-Regular,Consolas,monospace" '
                     f'font-size="14.5" fill="#1f2328">{esc(ln)}</text>')
        y += 24
    parts.append(f'<text x="40" y="{y + 22}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="14" fill="#57606a">'
                 f'3,550 finding lines, address-normalized stdout identical · read step of the Line-01 completion workflow</text>')
    parts.append("</svg>")
    ASSET.parent.mkdir(parents=True, exist_ok=True)
    ASSET.write_text("\n".join(p for p in parts if p), encoding="utf-8")
    print(f"asset: {ASSET} ({ASSET.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    if "--verify" in sys.argv:
        sys.exit(0 if verify() else 1)
    if "--build" in sys.argv:
        if not verify():
            sys.exit(1)
        render_crop()
        compose()
    else:
        print("usage: generate.py --verify | --build")
