"""Build index.html from index.template.html + a recorded demo-run.txt.

Usage: python3 build.py [demo-run.txt]   # default: demo-run.txt next to this file
Injects the verbatim transcript (HTML-escaped) and a timing card built from
the run's own read-phase numbers. Re-run scripts/demo.sh, save the output,
then re-run this to regenerate.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]

REVIEW = [
    ("product_presentation/README_DRAFT.md", "README_DRAFT.md"),
    ("product_presentation/DIAGRAM_DRAFT.svg", "DIAGRAM_DRAFT.svg"),
    ("product_presentation/ASSETS_AND_CLAIMS.md", "ASSETS_AND_CLAIMS.md"),
    ("product_presentation/README_PRESENTATION_PLAN.md", "README_PRESENTATION_PLAN.md"),
    ("scripts/demo.sh", "demo.sh"),
    ("examples/demo/read.py", "read.py"),
    ("examples/demo/unsupported.py", "unsupported.py"),
    ("examples/demo/generate_model.py", "generate_model.py"),
    ("examples/demo/README.md", "demo-README.md"),
    ("product_presentation/site/lineage_build.py", "lineage_build.py"),
]

HERE_FILES = ["lineage_traces.svg", "lineage_composition.svg", "lineage_tasks.html"]


def main() -> None:
    run_txt = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "demo-run.txt"
    text = run_txt.read_text(encoding="utf-8")
    phases = re.findall(r"read phase: ([0-9.]+ ms)", text)
    if len(phases) != 4:
        raise SystemExit(f"expected 4 read-phase lines in {run_txt}, found {len(phases)}")
    plain, built, reused, ref = phases
    timing = (
        '<div class="timing">\n'
        f'    <div class="cell"><b>{plain}</b><span>ordinary Python (in-script)</span></div>\n'
        f'    <div class="cell"><b>{built}</b><span>first run · BUILT</span></div>\n'
        f'    <div class="cell good"><b>{reused}</b><span>second run · REUSED</span></div>\n'
        f'    <div class="cell"><b>{ref}</b><span>unsupported · openpyxl</span></div>\n'
        "  </div>"
    )
    host = re.search(r"this machine only \((.*?)\)", text)
    recorded = dt.datetime.fromtimestamp(run_txt.stat().st_mtime, dt.UTC).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    info = (
        f"Recorded {recorded} on {host.group(1) if host else 'unknown host'} "
        "via scripts/demo.sh (fresh cache, exit 0). Replay above; "
        "pacing is illustrative, output is verbatim."
    )
    transcript_json = json.dumps(text.split("\n")).replace("<", "\\u003c")
    tasks_snippet = HERE / "lineage_tasks.html"
    if not tasks_snippet.is_file():
        raise SystemExit("lineage_tasks.html missing; run lineage_build.py first")
    template = (HERE / "index.template.html").read_text(encoding="utf-8")
    page = (
        template.replace("<!--TIMING-->", timing)
        .replace("<!--TRANSCRIPT-->", html.escape(text, quote=False))
        .replace("<!--TRANSCRIPT_JSON-->", transcript_json)
        .replace("<!--RECORD_INFO-->", html.escape(info, quote=False))
        .replace("<!--LINEAGE_TABLE-->", tasks_snippet.read_text(encoding="utf-8"))
    )
    for marker in ("<!--TRANSCRIPT-->", "<!--TIMING-->", "<!--TRANSCRIPT_JSON-->",
                   "<!--RECORD_INFO-->", "<!--LINEAGE_TABLE-->"):
        if marker in page:
            raise SystemExit(f"placeholder replacement failed: {marker}")
    (HERE / "index.html").write_text(page, encoding="utf-8")
    review = HERE / "review"
    review.mkdir(exist_ok=True)
    for src, dest in REVIEW:
        shutil.copy2(ROOT / src, review / dest)
    for name in HERE_FILES:
        shutil.copy2(HERE / name, review / name)
    shutil.copy2(run_txt, review / "demo-run.txt")
    print(f"wrote index.html from {run_txt.name} (phases: {', '.join(phases)})")
    print(f"synced {len(REVIEW) + len(HERE_FILES) + 1} review files to review/")


if __name__ == "__main__":
    main()
