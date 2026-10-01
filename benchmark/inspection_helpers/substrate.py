"""Fail-closed publication of the optional, parent-maintained Candidate-A index."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path

from benchmark.inspection_helpers import index


def _write_manifest(path: Path, value: dict) -> None:
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def prepare(workdir: Path, shared: Path, phase="refresh", serves_roles=()) -> dict:
    manifest = {"workbooks": {}, "refreshes": [], "failures": [],
                "phase": phase, "serves_roles": list(serves_roles)}
    ensure_total = backup_total = 0.0
    rebuilt_count = 0
    stage = "substrate_initialization"
    try:
        shared.mkdir(parents=True, exist_ok=True)
        # Revoke previous publication before attempting any refresh/build.
        _write_manifest(shared / "manifest.json", manifest)
        for path in sorted(workdir.glob("*.xlsx")):
            if ".tmp" in path.name:
                continue
            resolved = str(path.resolve())
            handle = target = None
            temporary = None
            started = time.perf_counter()
            ensure_s = backup_s = 0.0
            stage = "freshness_initialization"
            try:
                handle, rebuilt = index.ensure_fresh(resolved)
                ensure_s = time.perf_counter() - started
                stage = "compiled_database_publication"
                db_path = shared / f"{handle['workbook_hash']}.sqlite"
                if rebuilt or not db_path.exists():
                    t1 = time.perf_counter()
                    fd, name = tempfile.mkstemp(dir=shared, suffix=".sqlite.tmp")
                    os.close(fd)
                    temporary = Path(name)
                    target = sqlite3.connect(str(temporary))
                    handle["db"].backup(target)
                    target.commit()
                    target.close()
                    target = None
                    os.replace(temporary, db_path)
                    backup_s = time.perf_counter() - t1
                entry = {"path": resolved, "db_path": str(db_path.resolve()),
                         "workbook_hash": handle["workbook_hash"],
                         "index_generation": handle["index_generation"],
                         "rebuilt": rebuilt, "ensure_s": ensure_s,
                         "backup_s": backup_s, "freshness_s": ensure_s + backup_s}
                manifest["workbooks"][resolved] = entry
                manifest["refreshes"].append(entry)
                rebuilt_count += int(rebuilt)
            except Exception as exc:  # noqa: BLE001 - optional boundary records state and falls back
                event = (exc.event if isinstance(exc, index.SubstrateDisabled) else
                         index.disable(resolved, handle["workbook_hash"] if handle else None,
                                       stage, exc, partial=handle is not None))
                manifest["failures"].append(event)
                ensure_s = time.perf_counter() - started
            finally:
                if target is not None:
                    target.close()
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
                ensure_total += ensure_s
                backup_total += backup_s
        stage = "manifest_publication"
        _write_manifest(shared / "manifest.json", manifest)
        db_bytes = sum(p.stat().st_size for p in shared.glob("*.sqlite"))
    except Exception as exc:  # noqa: BLE001 - optional boundary records state and falls back
        event = index.disable(str(shared), None, stage, exc,
                              partial=bool(manifest["workbooks"]))
        manifest["failures"].append(event)
        manifest["workbooks"].clear()
        # Storage failure may prevent revocation on disk. Descendant Python
        # processes must not consult that manifest for this runner lifetime.
        os.environ["CANDIDATE_A_SUBSTRATE_DISABLED"] = "publication unavailable"
        db_bytes = 0
    manifest.update(total_s=ensure_total + backup_total, ensure_s=ensure_total,
                    backup_s=backup_total, n_workbooks=len(manifest["workbooks"]),
                    n_rebuilt=rebuilt_count, db_bytes=db_bytes)
    return manifest
