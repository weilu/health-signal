"""Hatchling build hook: compile the React frontend into ``src/health_signal/_ui``.

A prebuilt wheel already bundles ``_ui`` and skips this, so wheel installs stay Node-free. Building
from source (sdist, or ``pip install git+...``) runs Vite here, so a source build needs Node/npm on
PATH -- otherwise it would silently package only the placeholder.
"""

import pathlib
import shutil
import subprocess

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBuildHook(BuildHookInterface):
    PLUGIN_NAME = "frontend"

    def initialize(self, version, build_data):
        # Editable installs (uv sync / pip install -e) don't distribute _ui, so skip the build —
        # otherwise a dev sync would need Node and rebuild the frontend every time.
        if version == "editable":
            return
        # Rebuild unconditionally for distribution builds: a stale _ui must never be packaged, and a
        # prebuilt wheel skips this hook entirely (build hooks don't run on install).
        root = pathlib.Path(self.root)
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError(
                "Building health-signal from source needs Node/npm to compile the frontend. "
                "Install Node, or install the prebuilt wheel (which bundles the compiled UI)."
            )
        subprocess.run([npm, "--prefix", "frontend", "install"], cwd=root, check=True)
        subprocess.run([npm, "--prefix", "frontend", "run", "build"], cwd=root, check=True)
