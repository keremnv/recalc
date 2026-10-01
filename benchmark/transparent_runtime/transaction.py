"""Transparent workbook transaction: the H1 runtime.

Stage semantics (mechanical only):
  1. canonical pre-state: hash + byte snapshot of the target workbook
     (None when the mutation is expected to create the file);
  2. run agent Python unchanged: subprocess, no monkeypatching, no new
     imports, no source rewriting;
  3. capture effects: hash + byte snapshot of the Python-produced post-state;
  4. derive internal WorkbookDelta from pre/post bytes (observed, not inferred);
  5. validate mechanical invariants only;
  6. preserve normalized + opaque parts (unchanged parts carried byte-exact);
  7. commit atomically: committed bytes == Python-produced bytes;
  8. provenance: generation id + delta id + script hash + pre/post hashes.

Model surface stays byte-identical to H0: bash, view_xlsx, submit.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from benchmark.transparent_runtime.delta import (
    WorkbookDelta,
    derive_delta,
    read_parts,
    replay_delta,
    sha256,
)
from benchmark.transparent_runtime.telemetry import MutationTelemetry
from benchmark.transparent_runtime.validate import ValidationReport, validate_mechanical

# H0 tool surface, frozen. No new model-facing tools may be added here.
MODEL_SURFACE: tuple[str, ...] = ("bash", "view_xlsx", "submit")


@dataclass(frozen=True)
class ScriptOutcome:
    returncode: int
    stdout: str
    stderr: str
    script_hash: str


@dataclass(frozen=True)
class TransactionResult:
    outcome: ScriptOutcome
    delta: WorkbookDelta | None
    validation: ValidationReport | None
    telemetry: MutationTelemetry
    committed_path: str | None
    aborted: bool


@dataclass
class WorkbookTransaction:
    """One transparent mutation transaction."""

    target: Path
    script_path: Path
    committed_path: Path | None = None
    timeout_s: int = 300
    telemetry_log: list[MutationTelemetry] = field(default_factory=list)

    def run(self) -> TransactionResult:
        generation_id = uuid.uuid4().hex
        script_bytes = self.script_path.read_bytes()
        script_hash = hashlib.sha256(script_bytes).hexdigest()

        pre_bytes = self._snapshot()
        pre_hash = sha256(pre_bytes) if pre_bytes is not None else None

        outcome = run_python_unchanged(self.script_path, self.timeout_s)

        committed_target = self.committed_path or self.target
        if outcome.returncode != 0 or not committed_target.exists():
            telemetry = MutationTelemetry(
                delta_id=uuid.uuid4().hex,
                generation_id=generation_id,
                pre_hash=pre_hash,
                post_hash=None,
                fidelity_f0_exact=False,
                fidelity_f1_part_exact=False,
                fidelity_f2_state_exact=False,
                status="aborted_script_failed"
                if outcome.returncode != 0
                else "aborted_no_output",
                validation={},
            )
            self.telemetry_log.append(telemetry)
            return TransactionResult(
                outcome=outcome,
                delta=None,
                validation=None,
                telemetry=telemetry,
                committed_path=None,
                aborted=True,
            )

        post_bytes = committed_target.read_bytes()
        post_hash = sha256(post_bytes)

        cell_effects = observe_cell_effects(pre_bytes, post_bytes)
        delta = derive_delta(pre_bytes, post_bytes, cell_effects)

        # Commit: the Python-produced file already holds post_bytes. Commit
        # atomically so committed == produced even under races: copy through
        # a temp file in the same directory, then verify the hash.
        committed_bytes = self._atomic_commit(committed_target, post_bytes)

        validation = validate_mechanical(pre_bytes, post_bytes, committed_bytes, delta)

        f0 = pre_bytes is not None and _zip_part_map_equal(
            _try_parts(pre_bytes), _try_parts(post_bytes)
        )
        replayed = replay_delta(pre_bytes, delta)
        f1 = _parts_equal(replayed, committed_bytes)
        telemetry = MutationTelemetry(
            delta_id=delta.delta_id,
            generation_id=generation_id,
            pre_hash=pre_hash,
            post_hash=post_hash,
            fidelity_f0_exact=False if pre_bytes is None else f0,
            fidelity_f1_part_exact=f1,
            fidelity_f2_state_exact=f1,
            opaque_parts=delta.opaque_preserved,
            validation=dict(validation.checks),
            status="committed" if validation.passed else "committed_validation_failed",
        )
        self.telemetry_log.append(telemetry)
        _ = script_hash  # recorded by caller via outcome.script_hash
        return TransactionResult(
            outcome=outcome,
            delta=delta,
            validation=validation,
            telemetry=telemetry,
            committed_path=str(committed_target),
            aborted=False,
        )

    def _snapshot(self) -> bytes | None:
        if not self.target.exists():
            return None
        return self.target.read_bytes()

    @staticmethod
    def _atomic_commit(path: Path, post_bytes: bytes) -> bytes:
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "wb") as handle:
                handle.write(post_bytes)
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return path.read_bytes()


def run_python_unchanged(script_path: Path, timeout_s: int = 300) -> ScriptOutcome:
    """Execute agent Python exactly as written; no patching, no wrapping."""
    script_hash = hashlib.sha256(Path(script_path).read_bytes()).hexdigest()
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout_s,
    )
    return ScriptOutcome(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        script_hash=script_hash,
    )


def observe_cell_effects(
    pre_bytes: bytes | None, post_bytes: bytes
) -> list[dict]:
    """Read-only observed (address, before, after) value/formula changes.

    Uses data_only=False snapshots via openpyxl without writing anything.
    """
    import openpyxl

    def snapshot(data: bytes | None) -> dict:
        if data is None:
            return {}
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            wb = openpyxl.load_workbook(tmp_path, data_only=False)
            cells: dict = {}
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for c in row:
                        if c.value is not None or (c.data_type == "f"):
                            cells[(ws.title, c.coordinate)] = (
                                c.value if c.data_type != "f" else None,
                                c.value if c.data_type == "f" else None,
                            )
            wb.close()
            return cells
        finally:
            os.unlink(tmp_path)

    before, after = snapshot(pre_bytes), snapshot(post_bytes)
    effects: list[dict] = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            effects.append(
                {
                    "sheet": key[0],
                    "address": key[1],
                    "before": [before.get(key, (None, None))[0], before.get(key, (None, None))[1]],
                    "after": [after.get(key, (None, None))[0], after.get(key, (None, None))[1]],
                }
            )
    return effects


def run_transaction(
    target: str | Path,
    script: str | Path,
    committed_path: str | Path | None = None,
    timeout_s: int = 300,
) -> TransactionResult:
    """One-shot helper: snapshot, run, capture, derive, validate, commit."""
    txn = WorkbookTransaction(
        target=Path(target),
        script_path=Path(script),
        committed_path=Path(committed_path) if committed_path else None,
        timeout_s=timeout_s,
    )
    return txn.run()


def _try_parts(data: bytes) -> dict | None:
    try:
        return read_parts(data)
    except Exception:  # noqa: BLE001 -- mechanical probe
        return None


def _parts_equal(a: bytes, b: bytes) -> bool:
    pa, pb = _try_parts(a), _try_parts(b)
    return pa is not None and pa == pb


def _zip_part_map_equal(pa: dict | None, pb: dict | None) -> bool:
    return pa is not None and pa == pb
