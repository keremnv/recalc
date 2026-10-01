"""Offline Phase-2 persistence wrappers around the frozen Phase-1 decoder."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import pickle
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "read_engine_phase1"))
from prototype import SQLiteBook, SQLiteSink, decode_xlsx  # noqa: E402

DECODER = "a6e95f1503ec6090d6176065471372924bf447f907a2a428faceee12a2f72473"
CONTRACT = "PHASE1_NARROW_V5"
FORMATS = {"P2": "P2_SQLITE_V1", "P3": "P3_PICKLE_V1"}


def tick() -> int:
    return time.perf_counter_ns()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def key_for(source_sha: str, variant: str) -> str:
    return hashlib.sha256(f"{source_sha}|{DECODER}|{CONTRACT}|{FORMATS[variant]}".encode()).hexdigest()


def paths(root: Path, source_sha: str, variant: str) -> tuple[Path, Path, str]:
    key = key_for(source_sha, variant)
    artifact = root / variant / f"{key}{'.sqlite' if variant == 'P2' else '.pkl'}"
    return artifact, Path(str(artifact) + ".json"), key


def _meta(source_sha: str, variant: str, key: str) -> dict:
    return {"source_sha256": source_sha, "decoder_id": DECODER,
            "contract_id": CONTRACT, "format_version": FORMATS[variant], "key": key}


def _validate(artifact: Path, sidecar: Path, expected: dict, variant: str, profile: dict) -> tuple[bool, str]:
    t = tick()
    try:
        manifest = json.loads(sidecar.read_text())
        if any(manifest.get(k) != v for k, v in expected.items()):
            return False, "manifest_identity"
        if not artifact.is_file() or artifact.stat().st_size != manifest.get("artifact_bytes"):
            return False, "artifact_missing_or_size"
        profile["manifest_discovery_ns"] = tick() - t
        t = tick()
        if sha(artifact) != manifest.get("artifact_sha256"):
            return False, "artifact_hash"
        profile["artifact_hash_ns"] = tick() - t
        t = tick()
        if variant == "P2":
            with sqlite3.connect(artifact.resolve().as_uri() + "?mode=ro", uri=True) as con:
                stored = dict(con.execute("SELECT key,value FROM artifact_meta"))
                if any(stored.get(k) != str(v) for k, v in expected.items()):
                    return False, "internal_identity"
                if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    return False, "sqlite_integrity"
        profile["format_validation_ns"] = tick() - t
        return True, "valid"
    except (OSError, ValueError, KeyError, sqlite3.DatabaseError, TypeError) as exc:
        return False, f"invalid:{type(exc).__name__}"


def _publish(source: Path, artifact: Path, sidecar: Path, meta: dict, variant: str, profile: dict) -> None:
    artifact.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=artifact.parent, prefix="phase2-", suffix=".tmp")
    os.close(fd)
    tmp = Path(name)
    try:
        if variant == "P2":
            t = tick()
            sink = SQLiteSink(tmp)
            try:
                book = decode_xlsx(source, sink)
                profile["decoder_profile"] = book.profile
                sink.put_sheets(list(book._sheets.values()))
                sink.finish()
            except BaseException:
                sink.con.close()
                raise
            profile["decode_storage_ns"] = tick() - t
            t = tick()
            with sqlite3.connect(tmp) as con:
                con.execute("CREATE TABLE artifact_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL) WITHOUT ROWID")
                con.executemany("INSERT INTO artifact_meta VALUES (?,?)", ((k, str(v)) for k, v in meta.items()))
            profile["metadata_write_ns"] = tick() - t
        else:
            t = tick()
            book = decode_xlsx(source)
            profile["decoder_profile"] = book.profile.copy()
            book.profile = {}
            profile["decode_ns"] = tick() - t
            t = tick()
            envelope = {"meta": meta, "book": book}
            with tmp.open("wb") as f:
                pickle.dump(envelope, f, protocol=5)
                f.flush()
                os.fsync(f.fileno())
            profile["serialize_ns"] = tick() - t
        t = tick()
        with tmp.open("rb") as f:
            os.fsync(f.fileno())
        artifact_sha = sha(tmp)
        size = tmp.stat().st_size
        os.replace(tmp, artifact)
        sync_dir(artifact.parent)
        manifest = {**meta, "artifact_bytes": size, "artifact_sha256": artifact_sha,
                    "source_bytes": source.stat().st_size}
        fd, mname = tempfile.mkstemp(dir=artifact.parent, prefix="phase2-manifest-", suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(manifest, f, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(mname, sidecar)
        sync_dir(artifact.parent)
        profile["publication_ns"] = tick() - t
        profile["artifact_bytes"] = size
    finally:
        tmp.unlink(missing_ok=True)


def acquire(source: Path, root: Path, variant: str) -> tuple[object, str, dict]:
    """Return book, BUILT/REUSED witness, and non-overlapping phase timings."""
    import openpyxl
    profile: dict = {}
    start = tick()
    if variant == "P0":
        book = openpyxl.load_workbook(source, data_only=False)
        profile["build_ns"] = tick() - start
        profile["attach_ns"] = 0
        return book, "REFERENCE", profile
    if variant == "P1":
        book = decode_xlsx(source)
        profile["decoder_profile"] = book.profile.copy()
        profile["build_ns"] = tick() - start
        profile["attach_ns"] = 0
        return book, "BUILT", profile
    t = tick()
    source_sha = sha(source)
    profile["source_hash_ns"] = tick() - t
    artifact, sidecar, key = paths(root, source_sha, variant)
    meta = _meta(source_sha, variant, key)
    good, reason = _validate(artifact, sidecar, meta, variant, profile)
    if good:
        witness = "REUSED"
        profile["build_ns"] = 0
    else:
        witness = "BUILT"
        profile["rebuild_reason"] = reason
        t = tick()
        _publish(source, artifact, sidecar, meta, variant, profile)
        profile["build_ns"] = tick() - start
    t = tick()
    if variant == "P2":
        book = SQLiteBook(artifact, {})
    else:
        with artifact.open("rb") as f:
            envelope = pickle.load(f)
        if envelope["meta"] != meta:
            raise ValueError("P3 envelope identity mismatch")
        book = envelope["book"]
    profile["attach_ns"] = tick() - t
    profile["artifact_bytes"] = artifact.stat().st_size
    profile["source_bytes"] = source.stat().st_size
    profile["acquire_ns"] = tick() - start
    return book, witness, profile


@contextlib.contextmanager
def no_openpyxl_load():
    import openpyxl
    import openpyxl.reader.excel
    before = openpyxl.load_workbook, openpyxl.reader.excel.load_workbook
    def forbidden(*args, **kwargs):
        raise AssertionError("Treatment invoked openpyxl.load_workbook")
    openpyxl.load_workbook = forbidden
    openpyxl.reader.excel.load_workbook = forbidden
    try:
        yield
    finally:
        openpyxl.load_workbook, openpyxl.reader.excel.load_workbook = before
