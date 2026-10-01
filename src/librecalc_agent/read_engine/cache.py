"""Lightweight artifact integrity gate and serialized cache publication."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import struct
import time
import fcntl
from pathlib import Path

from ._identity import (HEXDIGEST, MAGIC, MAX_COMPRESSED, MAX_HEADER,
                        MAX_SHEETS, RUNTIME_VERSION, artifact_key, identity,
                        paths, sha_file)

__all__ = ["artifact_key", "ensure", "identity", "paths", "sha_file",
           "validate"]


def tick() -> int:
    return time.perf_counter_ns()


def validate(artifact: Path, sidecar: Path, source_sha: str) -> tuple[bool, str, dict]:
    """Validate publication and whole-artifact integrity, never semantic cells."""
    phases = {"sidecar_header_ns": 0, "artifact_read_ns": 0, "artifact_hash_ns": 0,
              "parent_semantic_decompress_ns": 0, "parent_semantic_json_ns": 0,
              "parent_schema_validation_ns": 0, "parent_memorybook_construction_ns": 0,
              "parent_memorybook_constructed": False}
    try:
        t = tick()
        if sidecar.is_symlink() or artifact.is_symlink() or sidecar.stat().st_size > MAX_HEADER:
            return False, "artifact_path_or_sidecar_size", phases
        meta = json.loads(sidecar.read_bytes())
        expected = identity(source_sha)
        if (not isinstance(meta, dict) or any(meta.get(k) != v for k, v in expected.items())
                or meta.get("runtime_version") != RUNTIME_VERSION):
            return False, "manifest_identity", phases
        if (meta.get("artifact_key") != artifact_key(source_sha)
                or not isinstance(meta.get("artifact_sha256"), str)
                or not HEXDIGEST.fullmatch(meta["artifact_sha256"])):
            return False, "manifest_fields", phases
        if not artifact.is_file():
            return False, "artifact_missing_or_size", phases
        size = artifact.stat().st_size
        if (size != meta.get("artifact_bytes") or size > MAX_COMPRESSED + MAX_HEADER + 52
                or size < 52):
            return False, "artifact_missing_or_size", phases
        phases["sidecar_header_ns"] += tick() - t

        t = tick()
        blob = artifact.read_bytes()
        phases["artifact_read_ns"] = tick() - t
        if len(blob) != size:
            return False, "artifact_changed_during_read", phases

        t = tick()
        if hashlib.sha256(blob).hexdigest() != meta["artifact_sha256"]:
            return False, "artifact_hash", phases
        if blob[:8] != MAGIC or hashlib.sha256(blob[:-32]).digest() != blob[-32:]:
            return False, "artifact_envelope", phases
        phases["artifact_hash_ns"] = tick() - t

        t = tick()
        hlen = struct.unpack(">I", blob[8:12])[0]
        if hlen > MAX_HEADER or 12 + hlen + 8 + 32 > len(blob):
            return False, "header_length", phases
        header = json.loads(blob[12:12 + hlen])
        if (not isinstance(header, dict)
                or set(header) != set(expected) | {"sheet_count", "payload_sha256"}
                or any(header[k] != v for k, v in expected.items())
                or type(header["sheet_count"]) is not int
                or not 0 <= header["sheet_count"] <= MAX_SHEETS
                or not isinstance(header["payload_sha256"], str)
                or not HEXDIGEST.fullmatch(header["payload_sha256"])):
            return False, "header_identity_or_fields", phases
        offset = 12 + hlen
        clen = struct.unpack(">Q", blob[offset:offset + 8])[0]
        if clen > MAX_COMPRESSED or offset + 8 + clen + 32 != len(blob):
            return False, "compressed_length", phases
        phases["sidecar_header_ns"] += tick() - t
        return True, "valid_integrity_candidate", phases
    except (OSError, ValueError, TypeError, KeyError, OverflowError, struct.error) as exc:
        return False, f"invalid:{type(exc).__name__}", phases


def ensure(source: Path, cache_root: Path, source_sha: str) -> tuple[Path, str, dict]:
    artifact, sidecar = paths(cache_root, source_sha)
    directory = artifact.parent
    if cache_root.is_symlink() or directory.is_symlink():
        raise ValueError("symlinked read-engine cache root")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    t = tick()
    good, reason, phases = validate(artifact, sidecar, source_sha)
    profile = {**phases, "artifact_discovery_validation_ns": tick() - t,
               "builder_import_ns": 0, "builder_stack_imported": False}
    if good:
        profile["artifact_bytes"] = artifact.stat().st_size
        return artifact, "REUSED", profile
    lock = directory / f"{artifact_key(source_sha)}.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        good, reason, _ = validate(artifact, sidecar, source_sha)
        if good:
            profile["artifact_bytes"] = artifact.stat().st_size
            return artifact, "REUSED", profile
        profile["rebuild_reason"] = reason
        t = tick()
        builder = importlib.import_module("librecalc_agent.read_engine.artifact")
        profile["builder_import_ns"] = tick() - t
        profile["builder_stack_imported"] = True
        built_artifact, status, build_phases = builder.ensure(source, cache_root, source_sha)
        profile.update(build_phases)
        return built_artifact, status, profile
    finally:
        os.close(fd)
