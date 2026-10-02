"""Mechanical-only validation for the transparent transaction.

Allowed checks (no semantics, no intent, no verifiers):
  exists / readable / persisted / serialization valid /
  relationships preserved / captured == committed.

Anything else (formula correctness, task completion, target inference) is
forbidden here and lives nowhere in this package.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field

from .delta import WorkbookDelta, read_parts, replay_delta, sha256


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    checks: dict[str, bool]
    detail: dict[str, str]


# Package metadata parts parsed here ([Content_Types].xml, *.rels) are small
# in every legitimate workbook. The ceiling keeps a hostile part from turning
# validation into a memory-exhaustion probe.
_MAX_XML_PART = 64 * 1024 * 1024


def _safe_fromstring(data: bytes, what: str):
    """Parse one package metadata part without entity expansion.

    stdlib ElementTree expands internal entities, so any DOCTYPE declaration
    (the only carrier of entity definitions in XML) is rejected before
    parsing. Legitimate OOXML metadata parts never contain one.
    """
    if len(data) > _MAX_XML_PART:
        raise ValueError(f"{what} exceeds XML size limit")
    upper = data.upper()
    if b"<!DOCTYPE" in upper:
        raise ValueError(f"{what} contains a DOCTYPE declaration")
    if b"<!ENTITY" in upper:
        raise ValueError(f"{what} contains an ENTITY declaration")
    return ET.fromstring(data)


def validate_mechanical(
    pre_bytes: bytes | None,
    post_bytes: bytes,
    committed_bytes: bytes,
    delta: WorkbookDelta,
) -> ValidationReport:
    checks: dict[str, bool] = {}
    detail: dict[str, str] = {}

    # 1. exists: there is committed state to validate.
    checks["exists"] = committed_bytes is not None and len(committed_bytes) > 0
    if not checks["exists"]:
        detail["exists"] = "committed bytes empty or missing"

    # 2. readable: the committed package opens as a zip with entries.
    try:
        names = read_parts(committed_bytes).keys()
        checks["readable"] = len(list(names)) > 0
    except Exception as exc:  # noqa: BLE001 -- mechanical readability probe
        checks["readable"] = False
        detail["readable"] = f"{type(exc).__name__}: {exc}"

    # 3. persisted: committed bytes are exactly what Python produced.
    checks["persisted"] = sha256(committed_bytes) == sha256(post_bytes)
    if not checks["persisted"]:
        detail["persisted"] = "committed hash != python-produced post hash"

    # 4. serialization valid: zip integrity + required package parts parse.
    try:
        with zipfile.ZipFile(io.BytesIO(committed_bytes)) as archive:
            bad = archive.testzip()
            names = archive.namelist()
            has_content_types = "[Content_Types].xml" in names
            _safe_fromstring(archive.read("[Content_Types].xml"),
                             "[Content_Types].xml")
        checks["serialization_valid"] = bad is None and has_content_types
        if bad is not None:
            detail["serialization_valid"] = f"corrupt member: {bad}"
        elif not has_content_types:
            detail["serialization_valid"] = "missing [Content_Types].xml"
    except Exception as exc:  # noqa: BLE001 -- mechanical serialization probe
        checks["serialization_valid"] = False
        detail["serialization_valid"] = f"{type(exc).__name__}: {exc}"

    # 5. relationships preserved: every .rels target resolves inside the package.
    try:
        with zipfile.ZipFile(io.BytesIO(committed_bytes)) as archive:
            names = set(archive.namelist())
            missing: list[str] = []
            for name in names:
                if not name.endswith(".rels"):
                    continue
                root = _safe_fromstring(archive.read(name), name)
                for el in root.iter():
                    target = el.attrib.get("Target")
                    mode = el.attrib.get("TargetMode")
                    if target is None or mode == "External":
                        continue
                    resolved = _resolve_target(name, target)
                    if resolved not in names:
                        missing.append(f"{name} -> {target}")
        checks["relationships_preserved"] = not missing
        if missing:
            detail["relationships_preserved"] = "; ".join(sorted(set(missing))[:5])
    except Exception as exc:  # noqa: BLE001 -- mechanical rels probe
        checks["relationships_preserved"] = False
        detail["relationships_preserved"] = f"{type(exc).__name__}: {exc}"

    # 6. captured == committed: replaying the delta onto the pre-state
    # reproduces the committed package part-for-part (opaque byte-identical;
    # normalized parts compared by stored post hash).
    try:
        replayed = replay_delta(pre_bytes, delta)
        replayed_parts = read_parts(replayed)
        committed_parts = read_parts(committed_bytes)
        mismatch = [
            name
            for name in set(replayed_parts) | set(committed_parts)
            if replayed_parts.get(name) != committed_parts.get(name)
        ]
        checks["captured_equals_committed"] = not mismatch
        if mismatch:
            detail["captured_equals_committed"] = f"{len(mismatch)} part(s) differ"
    except Exception as exc:  # noqa: BLE001 -- mechanical replay probe
        checks["captured_equals_committed"] = False
        detail["captured_equals_committed"] = f"{type(exc).__name__}: {exc}"

    return ValidationReport(
        passed=all(checks.values()),
        checks=checks,
        detail=detail,
    )


def _resolve_target(rels_name: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    base = rels_name.rsplit("/", 1)[0] if "/" in rels_name else ""
    # _rels parts live beside their owner: xl/worksheets/_rels/s.xrels ->
    # xl/worksheets/, and the package root _rels/.rels -> "".
    if base == "_rels":
        base = ""
    elif base.endswith("/_rels"):
        base = base[: -len("/_rels")]
    parts: list[str] = []
    for seg in (base + "/" + target).split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts)


@dataclass
class TelemetryPlaceholder:
    """Kept out of validate.py; see telemetry.py for the real record."""

    notes: dict = field(default_factory=dict)
