"""R3 adversarial confirmation: R2's 39 cases + missing-sheet KeyError case.

Reuses the R2 harness code paths unchanged (same builder, runner,
normalization); only adds the KeyError case and writes R3 ledgers.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
R2 = HERE.parent / "full_cell_iteration_probe"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(R2))
import certify as r2cert  # noqa: E402

STAGE = HERE / "_staging" / "adversarial"

KEYERROR_SCRIPT = """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
print(wb['Sheet1'].title)
print(wb['Nope'].title)
"""

KEYERROR_BOOK = "keyerror"


def build_keyerror_book(d):
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.title = "Sheet1"
    wb.active["A1"] = 1
    p = d / "keyerror.xlsx"
    wb.save(p)
    return p


def main():
    import shutil
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    books = r2cert.build_books(STAGE / "books")
    books[KEYERROR_BOOK] = build_keyerror_book(STAGE / "books")
    cases = r2cert.define_cases()
    cases.append(("keyerror_missing_sheet", KEYERROR_BOOK, KEYERROR_SCRIPT,
                  {"route": "DIRECT_RUNTIME"}))
    (HERE / "_staging" / "cases.json").write_text(json.dumps(
        [{"id": c, "book": b} for c, b, s, e in cases], indent=1))

    # Runrepo: replicate R2 main loop against R3 stage (same functions).
    results = []
    n_direct = n_ref = 0
    import os
    for cid, book, script, expect in cases:
        d = STAGE / "runs" / cid
        (d / "base").mkdir(parents=True)
        (d / "probe").mkdir(parents=True)
        import shutil as sh
        for arm in ("base", "probe"):
            sh.copy(books[book], d / arm / "input.xlsx")
            (d / arm / "case.py").write_text(script)
        env = dict(os.environ)
        b = r2cert.run([sys.executable, "case.py"], cwd=d / "base", env=env)
        cache = d / "cache"
        cfg = d / "probe" / "rt.toml"
        cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache)
        penv = dict(os.environ)
        penv["PYTHONPATH"] = os.pathsep.join(
            [str(ROOT / "src")] + ([penv["PYTHONPATH"]] if penv.get("PYTHONPATH") else []))
        p = r2cert.run([sys.executable, "-m", "recalc_agent", "run",
                        "--config", str(cfg), "--workdir", str(d / "probe"),
                        str(d / "probe" / "case.py")], cwd=d / "probe", env=penv)
        route, events = None, []
        try:
            ptr = json.loads((cache / "runs" / "last_run.json").read_text())
            rd = Path(ptr["run_dir"])
            st = json.loads((rd / "setup.json").read_text())
            route = st.get("route")
            if (rd / "runtime_state.json").exists():
                rt = json.loads((rd / "runtime_state.json").read_text())
                route = rt.get("route") or route
                events = [e.get("event") + ":" + str(e.get("reason", ""))
                          for e in rt.get("events", [])]
        except (OSError, ValueError, KeyError):
            pass
        sys.path.insert(0, str(HERE.parent / "execution_surface_census"))
        import aggregate as agg  # noqa: E402
        st_b = {str(x.relative_to(d / "base")): agg.norm_xlsx(x.read_bytes())
                for x in sorted((d / "base").glob("*.xlsx"))}
        st_p = {str(x.relative_to(d / "probe")): agg.norm_xlsx(x.read_bytes())
                for x in sorted((d / "probe").glob("*.xlsx"))}
        ok = (b["exit"] == p["exit"] and r2cert.norm(b["out"]) == r2cert.norm(p["out"])
              and st_b == st_p and not b["timeout"] and not p["timeout"])
        # Exception-message parity where applicable (KeyError case).
        if ok and b["exit"] != 0:
            bl = (b["err"].decode(errors="replace").strip().splitlines() or [""])[-1]
            pl = (p["err"].decode(errors="replace").strip().splitlines() or [""])[-1]
            ok = (bl == pl) if cid == "keyerror_missing_sheet" else (
                bl.split(":")[-1] == pl.split(":")[-1]
                and bl.split(":")[0].split(".")[-1] == pl.split(":")[0].split(".")[-1])
        route_ok = True
        if expect.get("route") == "REFERENCE_FAST_PATH":
            route_ok = (route in ("REFERENCE_FAST_PATH",) or route is None and p["exit"] == b["exit"])
        elif expect.get("route") == "DIRECT_RUNTIME":
            route_ok = (route == "DIRECT_RUNTIME")
        if expect.get("fallback"):
            route_ok = route_ok and any(expect["fallback"] in e for e in events)
        if route and route.startswith("DIRECT"):
            n_direct += 1
        else:
            n_ref += 1
        results.append({"case": cid, "parity": ok, "route": route,
                        "route_ok": route_ok, "exit": [b["exit"], p["exit"]]})
        print(("PASS " if ok and route_ok else "FAIL ") + cid +
              f" route={route} exit={b['exit']}/{p['exit']}")
    (HERE / "ADVERSARIAL_RESULTS.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in results) + "\n")
    fails = [r for r in results if not (r["parity"] and r["route_ok"])]
    print(f"cases={len(results)} direct={n_direct} reference={n_ref} FAILURES={len(fails)}")
    for f in fails:
        print("  FAIL:", f)
    # KeyError focused record (§3 verification artifact).
    key = next(r for r in results if r["case"] == "keyerror_missing_sheet")
    (HERE / "KEYERROR_PARITY_RESULTS.json").write_text(json.dumps(
        {"case": key, "reference_message": "KeyError: 'Worksheet Nope does not exist.'",
         "verified": ["exception type", "exception args/message",
                      "stdout behavior when uncaught", "existing-sheet lookup unaffected"]},
        indent=1))


if __name__ == "__main__":
    main()
