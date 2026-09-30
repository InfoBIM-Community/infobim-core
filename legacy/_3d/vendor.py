"""Rebuild the bundled viewer using only the sources shipped by InfoBIM."""

from shutil import which
from typing import ClassVar, Optional
from pathlib import Path
import subprocess


class ViewerAsset:
    NAME: ClassVar[str] = "ifcx-viewer-offline.html"

    @classmethod
    def path(cls) -> Path:
        return Path(__file__).resolve().parent / "asset" / cls.NAME

    @classmethod
    def build(cls) -> Path:
        npm: Optional[str] = which("npm")
        if npm is None:
            raise RuntimeError("Building the viewer requires Node.js and npm.")
        asset_directory: Path = cls.path().parent
        if not (asset_directory / "node_modules" / "esbuild").is_dir():
            raise RuntimeError(
                "Install viewer build dependencies with `npm ci` in "
                "src/infobim/_3d/asset before rebuilding."
            )
        subprocess.run([npm, "run", "build"], cwd=asset_directory, check=True)
        if not cls.path().is_file():
            raise RuntimeError("The viewer build produced no standalone HTML.")
        return cls.path()


if __name__ == "__main__":
    print(ViewerAsset.build())
