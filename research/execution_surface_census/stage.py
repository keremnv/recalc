"""Stage census workloads into isolated workdirs (no behavior change).

Pop A/B: exact script bytes + workbook copied as input.xlsx.
Pop C: single workbook-literal normalization (RC-study style): absolute
/mnt/... directory prefixes are stripped to workdir-relative basenames and
input workbooks are copied under those basenames. Both hashes recorded.
"""
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path(__file__).parent / "_staging" / "rc_acceleration_validation"

_MNT_XLSX = re.compile(r"/mnt/[A-Za-z0-9_./ ()-]*?([^/'\"()\s]+\.xlsx)")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def workbook_index():
    idx = {}
    for p in (ROOT / "benchmark-data").rglob("*.xlsx"):
        idx.setdefault(p.name, []).append(p)
    return idx


def stage_ab(workload_id, script_sha, workbook_path, dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    src = STAGE / "workloads" / (workload_id + ".py")
    raw = src.read_bytes()
    assert sha_bytes(raw) == script_sha, workload_id
    (dest / "workload.py").write_bytes(raw)
    wb = Path(workbook_path)
    shutil.copy(wb, dest / "input.xlsx")
    return {"script": "workload.py", "script_sha256": script_sha,
            "workbook": "input.xlsx",
            "workbook_sha256": sha_bytes((dest / "input.xlsx").read_bytes()),
            "normalization": None}


def stage_c(source, dest, index):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    orig_hash = sha_bytes(source.encode())
    norm = source
    staged = []
    missing = []
    # Replace every /mnt/.../NAME.xlsx occurrence with NAME (workdir-local).
    norm = _MNT_XLSX.sub(lambda m: m.group(1), source)
    # Redirect container scratch dirs to the workdir (makedirs/listdir refs).
    norm = norm.replace("/mnt/spreadsheet_output", ".")
    norm = re.sub(r"/mnt/spreadsheet_data(?:/[A-Za-z0-9_.\- ()]*)*(?=['\"])",
                  ".", norm)
    for base in sorted(set(re.findall(r"([A-Za-z0-9_.\- ()]+\.xlsx)", norm))):
        if "output" in base.lower():
            continue
        hits = index.get(base, [])
        if hits:
            shutil.copy(hits[0], dest / base)
            staged.append({"basename": base, "source": str(hits[0]),
                           "sha256": sha_bytes((dest / base).read_bytes())})
        else:
            missing.append(base)
    (dest / "script.py").write_bytes(norm.encode())
    return {"script": "script.py", "script_sha256_orig": orig_hash,
            "script_sha256_staged": sha_bytes(norm.encode()),
            "normalization": "strip /mnt/ directory prefixes to basenames",
            "workbooks_staged": staged, "workbooks_missing": missing}
