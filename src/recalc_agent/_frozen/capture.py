"""Frozen implementation; packaging extraction only. See extraction_manifest.json."""
from __future__ import annotations
import os
import time
from pathlib import Path
from .delta import derive_delta, replay_delta, read_parts
from .validate import validate_mechanical

def snapshot_xlsx(workdir: Path) -> dict[str, bytes]:
    snaps = {}
    for p in sorted(workdir.rglob("*.xlsx")):
        if ".tmp" in p.name:
            continue
        try:
            snaps[str(p.relative_to(workdir))] = p.read_bytes()
        except OSError:
            pass
    return snaps


def capture_wrap_timed(workdir: Path, pre: dict[str, bytes], task_id: str,
                       arm: str, call_idx: int) -> tuple[list[dict], dict]:
    """Transparent transaction with per-section monotonic timing."""
    import tempfile as _tf
    t_sections: dict[str, float] = {"snapshot_post_s": 0.0, "derive_s": 0.0,
                                    "commit_s": 0.0, "validate_s": 0.0,
                                    "replay_s": 0.0}
    t0 = time.perf_counter()
    post = snapshot_xlsx(workdir)
    t_sections["snapshot_post_s"] = time.perf_counter() - t0
    telemetry = []
    for rel in sorted(set(pre) | set(post)):
        a, b = pre.get(rel), post.get(rel)
        if a is not None and b is not None and a == b:
            continue
        target = workdir / rel
        if b is None:
            telemetry.append({"task_id": task_id, "arm": arm,
                              "call_idx": call_idx, "rel": rel,
                              "deleted": True, "runtime_failure": False})
            continue
        t1 = time.perf_counter()
        delta = derive_delta(a, b)
        t_sections["derive_s"] += time.perf_counter() - t1
        committed = b
        fd, tmp = _tf.mkstemp(dir=str(target.parent),
                              prefix=target.name + ".", suffix=".tmp")
        t2 = time.perf_counter()
        try:
            with open(fd, "wb") as h:
                h.write(committed)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        committed_b = target.read_bytes()
        t_sections["commit_s"] += time.perf_counter() - t2
        t3 = time.perf_counter()
        validation = validate_mechanical(a, b, committed_b, delta)
        t_sections["validate_s"] += time.perf_counter() - t3
        t4 = time.perf_counter()
        replayed = replay_delta(a, delta)
        try:
            f1 = read_parts(replayed) == read_parts(committed_b)
        except Exception:  # noqa: BLE001 - record-only
            f1 = False
        t_sections["replay_s"] += time.perf_counter() - t4
        telemetry.append({"task_id": task_id, "arm": arm, "call_idx": call_idx,
                          "rel": rel, "delta_id": delta.delta_id,
                          "pre_hash": delta.pre_hash,
                          "post_hash": delta.post_hash,
                          "created": delta.created,
                          "f1_part_exact": f1, "f2_state_exact": f1,
                          "opaque_preserved": list(delta.opaque_preserved),
                          "validation": dict(validation.checks),
                          "validation_passed": validation.passed,
                          "runtime_failure": (not f1) or (committed_b != b)})
    return telemetry, t_sections
