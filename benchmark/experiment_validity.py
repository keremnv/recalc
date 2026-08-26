"""Known-invalid benchmark attempts that must not enter aggregate evidence.

This registry is deliberately small and evidence-backed. Development/contaminated runs are
still valid for symmetric interface comparisons; an attempt belongs here only when the recorded
output or score does not describe the agent/task pairing it claims to describe.
"""

from __future__ import annotations

KNOWN_INVALID_ATTEMPTS: dict[tuple[str, str], str] = {
    ("glm-5.3-v4-five-high-1", "Template:01_04"): (
        "pre-fix output discovery matched task id across categories and copied "
        "Financial_Model:01_04 into Template:01_04"
    ),
}


def invalid_reason(run_name: str, task_key: str) -> str | None:
    """Return the documented invalidity reason, if this attempt is unusable evidence."""

    return KNOWN_INVALID_ATTEMPTS.get((run_name, task_key))


__all__ = ["KNOWN_INVALID_ATTEMPTS", "invalid_reason"]
