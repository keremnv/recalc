"""Build the Linux external observer into the platform wheel."""
from __future__ import annotations

import platform
import subprocess
import sysconfig
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        if version != "standard":
            return
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            raise RuntimeError("The external observer is currently supported only on Linux x86_64")
        root = Path(self.root)
        source = root / "src/recalc_agent/native/observer.c"
        output = root / "src/recalc_agent/native/observer"
        launcher_source = root / "src/recalc_agent/native/launcher.c"
        launcher = root / "src/recalc_agent/native/launcher"
        subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(source), "-o", str(output)], check=True)
        subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(launcher_source), "-o", str(launcher)], check=True)
        output.chmod(0o755)
        launcher.chmod(0o755)
        platform_tag = sysconfig.get_platform().replace("-", "_").replace(".", "_")
        build_data["tag"] = f"py3-none-{platform_tag}"
        build_data["pure_python"] = False
        # The compiled binaries are git-ignored build outputs, so they are
        # absent from sdists; declare them as explicit artifacts so the wheel
        # built from an sdist still ships the freshly compiled files.
        build_data["artifacts"] = ["src/recalc_agent/native/observer",
                                   "src/recalc_agent/native/launcher"]
        build_data["shared_scripts"] = {str(launcher): "recalc-agent"}
