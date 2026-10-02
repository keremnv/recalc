"""Single-sourced derived-artifact identity. No validation, no I/O beyond hashing.

Everything that names an artifact (magic, versions, key derivation, paths)
lives here so the fast integrity gate (cache.py) and the full semantic layer
(artifact.py) cannot drift apart. Changing any version constant intentionally
orphans old artifacts; that is the invalidation mechanism.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .. import __version__ as RUNTIME_VERSION

MAGIC = b"LCRE3JZ1"
FORMAT = "JSONZ_MEMORY_V1"
CONTRACT = "PHASE1_NARROW_V5"
DECODER = "a6e95f1503ec6090d6176065471372924bf447f907a2a428faceee12a2f72473"
MAX_HEADER = 16 * 1024
MAX_COMPRESSED = 256 * 1024 * 1024
MAX_SHEETS = 512
HEXDIGEST = re.compile(r"^[0-9a-f]{64}$")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identity(source_sha: str) -> dict[str, str]:
    if not HEXDIGEST.fullmatch(source_sha):
        raise ValueError("invalid source hash")
    return {"source_sha256": source_sha, "decoder_sha256": DECODER,
            "contract_version": CONTRACT, "format_version": FORMAT}


def artifact_key(source_sha: str) -> str:
    return sha_bytes(("|".join(identity(source_sha).values()) +
                      "|runtime=" + RUNTIME_VERSION).encode())


def paths(cache_root: Path, source_sha: str) -> tuple[Path, Path]:
    artifact = cache_root / "read-engine" / f"{artifact_key(source_sha)}.r3jz"
    return artifact, Path(str(artifact) + ".json")
