"""Per-mutation telemetry, recorded internally (never shown to the model)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MutationTelemetry:
    delta_id: str
    generation_id: str
    pre_hash: str | None
    post_hash: str | None
    fidelity_f0_exact: bool
    fidelity_f1_part_exact: bool
    fidelity_f2_state_exact: bool
    opaque_parts: tuple[str, ...] = ()
    validation: dict[str, bool] = field(default_factory=dict)
    status: str = "committed"

    def to_dict(self) -> dict:
        return {
            "delta_id": self.delta_id,
            "generation_id": self.generation_id,
            "pre_hash": self.pre_hash,
            "post_hash": self.post_hash,
            "fidelity": {
                "f0_exact": self.fidelity_f0_exact,
                "f1_part_exact": self.fidelity_f1_part_exact,
                "f2_state_exact": self.fidelity_f2_state_exact,
            },
            "opaque_parts": list(self.opaque_parts),
            "validation": dict(self.validation),
            "status": self.status,
        }
