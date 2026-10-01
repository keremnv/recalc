"""Internal WorkbookDelta: observed package-part effects of one mutation.

Mechanical only. A delta records which xlsx zip parts changed between the
canonical pre-state and the Python-produced post-state, stores the full
post-state bytes of changed parts, and references the pre-state hash for
unchanged parts. Unchanged parts (normalized and opaque alike) are preserved
byte-identically on replay. Cell effects are observed read-only via openpyxl
(value/formula before/after); nothing is inferred about intent or targets.
"""

from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from dataclasses import dataclass, field


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_parts(data: bytes) -> dict[str, bytes]:
    """Return {part_name: raw_bytes} for every part of an xlsx package."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


# Parts whose XML openpyxl normalizes on save (sheet data, strings, styles,
# workbook structure). Compared normalized at F2; carried byte-exact when
# unchanged.
NORMALIZED_SUFFIXES = (
    "xl/worksheets/",
    "xl/sharedStrings.xml",
    "xl/styles.xml",
    "xl/workbook.xml",
)


def is_normalized_part(name: str) -> bool:
    return name == "xl/workbook.xml" or name.startswith(
        ("xl/worksheets/", "xl/sharedStrings.xml", "xl/styles.xml")
    )


@dataclass(frozen=True)
class ChangedPart:
    name: str
    pre_hash: str | None
    post_hash: str
    post_bytes: bytes
    normalized: bool
    deleted: bool = False


@dataclass(frozen=True)
class WorkbookDelta:
    """Observed effects of one Python mutation, derived post-hoc from bytes."""

    delta_id: str
    pre_hash: str | None
    post_hash: str
    changed: tuple[ChangedPart, ...] = ()
    unchanged_parts: tuple[str, ...] = ()
    opaque_preserved: tuple[str, ...] = ()
    created: bool = False
    cell_effects: tuple[dict, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "delta_id": self.delta_id,
            "pre_hash": self.pre_hash,
            "post_hash": self.post_hash,
            "created": self.created,
            "changed": [
                {
                    "name": c.name,
                    "pre_hash": c.pre_hash,
                    "post_hash": c.post_hash,
                    "normalized": c.normalized,
                    "deleted": c.deleted,
                }
                for c in self.changed
            ],
            "unchanged_parts": list(self.unchanged_parts),
            "opaque_preserved": list(self.opaque_preserved),
            "cell_effects": list(self.cell_effects),
        }


def derive_delta(
    pre_bytes: bytes | None,
    post_bytes: bytes,
    cell_effects: list[dict] | None = None,
    delta_id: str | None = None,
) -> WorkbookDelta:
    """Derive the delta between canonical pre-state and Python-produced post-state."""
    post_hash = sha256(post_bytes)
    post_parts = read_parts(post_bytes)
    if pre_bytes is None:
        changed = tuple(
            ChangedPart(
                name=name,
                pre_hash=None,
                post_hash=sha256(raw),
                post_bytes=raw,
                normalized=is_normalized_part(name),
            )
            for name, raw in sorted(post_parts.items())
        )
        return WorkbookDelta(
            delta_id=delta_id or uuid.uuid4().hex,
            pre_hash=None,
            post_hash=post_hash,
            changed=changed,
            unchanged_parts=(),
            opaque_preserved=(),
            created=True,
            cell_effects=tuple(cell_effects or ()),
        )
    pre_hash = sha256(pre_bytes)
    pre_parts = read_parts(pre_bytes)
    changed: list[ChangedPart] = []
    unchanged: list[str] = []
    for name in sorted(set(pre_parts) | set(post_parts)):
        pre_raw = pre_parts.get(name)
        post_raw = post_parts.get(name)
        if pre_raw is not None and post_raw is not None and pre_raw == post_raw:
            unchanged.append(name)
        elif post_raw is not None:
            changed.append(
                ChangedPart(
                    name=name,
                    pre_hash=sha256(pre_raw) if pre_raw is not None else None,
                    post_hash=sha256(post_raw),
                    post_bytes=post_raw,
                    normalized=is_normalized_part(name),
                )
            )
        else:
            # Part deleted by Python: explicit deleted flag (an empty
            # post image alone is ambiguous with zero-length dir entries).
            changed.append(
                ChangedPart(
                    name=name,
                    pre_hash=sha256(pre_raw) if pre_raw is not None else None,
                    post_hash=sha256(b""),
                    post_bytes=b"",
                    normalized=is_normalized_part(name),
                    deleted=True,
                )
            )
    opaque = tuple(n for n in unchanged if not is_normalized_part(n))
    return WorkbookDelta(
        delta_id=delta_id or uuid.uuid4().hex,
        pre_hash=pre_hash,
        post_hash=post_hash,
        changed=tuple(changed),
        unchanged_parts=tuple(unchanged),
        opaque_preserved=opaque,
        created=False,
        cell_effects=tuple(cell_effects or ()),
    )


def replay_delta(pre_bytes: bytes | None, delta: WorkbookDelta) -> bytes:
    """Reconstruct post-state bytes from pre-state + delta.

    Changed parts take their stored post image; every other pre-state part
    (normalized or opaque) is carried over byte-identically.
    """
    if delta.created or pre_bytes is None:
        images = {c.name: c.post_bytes for c in delta.changed if not c.deleted}
        return _build_package(images)
    pre_parts = read_parts(pre_bytes)
    merged: dict[str, bytes] = dict(pre_parts)
    for c in delta.changed:
        if c.deleted:
            merged.pop(c.name, None)
        else:
            merged[c.name] = c.post_bytes
    return _build_package(merged)


def _build_package(parts: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(parts):
            archive.writestr(name, parts[name])
    return buf.getvalue()
