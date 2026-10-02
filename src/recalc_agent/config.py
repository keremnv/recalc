"""One TOML configuration surface; invalid optional settings fail closed."""
from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Config:
    enabled: bool = True
    reads: bool = True
    # Deprecated aliases of `reads` (one migration window; removal post-v1).
    # They AND with `reads` so old configs keep their meaning; each use warns.
    substrate: bool = True
    candidate_a: bool = True
    capture: bool = True
    verbosity: str = "normal"
    cache_dir: str = ""

    @property
    def reads_effective(self) -> bool:
        return self.enabled and self.reads and self.substrate and self.candidate_a

    @property
    def assurance(self) -> bool:
        return self.enabled and self.capture

    def public(self) -> dict:
        return {"enabled": self.enabled,
                "read_acceleration_enabled": self.reads_effective,
                "effect_capture_enabled": self.assurance,
                "verbosity": self.verbosity, "cache_dir": self.cache_dir}


def defaults() -> Config:
    base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return Config(cache_dir=str(base / "recalc-agent"))


def load(path: str | None = None, disabled: bool = False) -> tuple[Config, list[dict]]:
    config = defaults()
    issues = []
    selected = path or os.environ.get("RECALC_CONFIG")
    if selected:
        try:
            config_path = Path(selected).expanduser().resolve()
            data = tomllib.loads(config_path.read_text(encoding="utf-8"))
            if set(data) != {"runtime"} or not isinstance(data["runtime"], dict):
                raise ValueError("expected only a [runtime] table")
            settings = data["runtime"]
            if set(settings) - set(asdict(config)):
                raise ValueError("unknown runtime setting")
            for key, value in settings.items():
                if key in {"enabled", "reads", "substrate", "candidate_a", "capture"} and type(value) is not bool:
                    raise ValueError(f"{key} must be true or false")
                if key == "verbosity" and value not in {"quiet", "normal", "verbose"}:
                    raise ValueError("verbosity must be quiet, normal or verbose")
                if key == "cache_dir":
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError("cache_dir must be a nonempty path")
                    target = Path(value).expanduser()
                    settings[key] = str((config_path.parent / target).resolve())
            config = replace(config, **settings)
            retired = sorted(set(settings) & {"substrate", "candidate_a"})
            if retired:
                issues.append({"check": "configuration", "status": "WARNING",
                               "message": f"Config keys {', '.join(retired)} are deprecated; use 'reads' instead. They still apply for one migration window.",
                               "detail": "deprecated alias"})
        except (OSError, ValueError, TypeError) as exc:
            config = replace(config, enabled=False)
            issues.append({"check": "configuration", "status": "WARNING",
                           "message": f"Configuration could not be used ({type(exc).__name__}). Ordinary Python continues with runtime disabled. Fix {selected} or omit --config to use defaults.",
                           "detail": str(exc)})
    if disabled:
        config = replace(config, enabled=False)
    return config, issues
