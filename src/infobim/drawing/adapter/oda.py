"""Locate the installed ODA File Converter executable."""

import os
import sys
import shutil
from typing import Any, Dict
from pathlib import Path
import plistlib
import subprocess


class OdaExecutable:
    @classmethod
    def resolve(cls) -> Path:
        configured: str | None = os.environ.get("INFOBIM_ODA_FILE_CONVERTER")
        if configured is not None:
            if not configured.strip():
                raise ValueError("INFOBIM_ODA_FILE_CONVERTER must name an executable.")
            return cls._validate(Path(configured).expanduser())
        executable: str | None = shutil.which("ODAFileConverter")
        if executable is not None:
            return cls._validate(Path(executable))
        if sys.platform == "darwin":
            discovery: subprocess.CompletedProcess[str] = subprocess.run(
                ["osascript", "-e", 'POSIX path of (path to application id "ODAFileConverter")'],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if discovery.returncode == 0 and discovery.stdout.strip():
                bundle: Path = Path(discovery.stdout.strip())
                info: Dict[str, Any] = plistlib.loads((bundle / "Contents" / "Info.plist").read_bytes())
                name: Any = info.get("CFBundleExecutable")
                if not isinstance(name, str) or not name or Path(name).name != name:
                    raise ValueError("ODA application declares an invalid executable name.")
                return cls._validate(bundle / "Contents" / "MacOS" / name)
        raise RuntimeError(
            "DWG conversion requires ODA File Converter. Install it and expose "
            "ODAFileConverter on PATH or set INFOBIM_ODA_FILE_CONVERTER. "
            "On macOS, its installed application is discovered automatically."
        )

    @staticmethod
    def _validate(path: Path) -> Path:
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"ODA File Converter is not an executable file: {path}")
        return path.resolve()
