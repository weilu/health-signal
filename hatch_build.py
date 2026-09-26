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
        root = pathlib.Path(self.root)
        if (root / "src" / "health_signal" / "_ui" / "index.html").exists():
            return  # already built (e.g. CI built it before packaging) -- don't rebuild
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError(
                "Building health-signal from source needs Node/npm to compile the frontend. "
                "Install Node, or install the prebuilt wheel (which bundles the compiled UI)."
            )
        subprocess.run([npm, "--prefix", "frontend", "install"], cwd=root, check=True)
        subprocess.run([npm, "--prefix", "frontend", "run", "build"], cwd=root, check=True)
