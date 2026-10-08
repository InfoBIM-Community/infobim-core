import json
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, Mapping, Optional


@dataclass(frozen=True)
class ShortcutSpec:
    """
    What a shortcut file points to, and where it starts from.
    """

    target: str
    arguments: str
    working_directory: str

    def matches(self, expected: "ShortcutSpec") -> bool:
        return (
            self._same_path(self.target, expected.target)
            and self.arguments.strip() == expected.arguments.strip()
            and self._same_path(self.working_directory, expected.working_directory)
        )

    @staticmethod
    def _same_path(first: str, second: str) -> bool:
        if not first.strip() or not second.strip():
            return False

        return os.path.normcase(os.path.normpath(first)) == os.path.normcase(
            os.path.normpath(second)
        )


class ShellLinkPort(ABC):
    """
    Reads and writes the shortcut files of the platform's shell.
    """

    @abstractmethod
    def read(self, shortcut_file: Path) -> Optional[ShortcutSpec]:
        """
        Return what the shortcut file holds, or ``None`` when it is not a
        readable shortcut.
        """
        ...

    @abstractmethod
    def write(self, shortcut_file: Path, spec: ShortcutSpec) -> None:
        ...


class PowerShellShellLink(ShellLinkPort):
    """
    Windows shortcuts, through the shell object Windows itself offers for
    them, so the file written is the one Explorer would write.
    """

    READ_SCRIPT: ClassVar[str] = (
        "$link = (New-Object -ComObject WScript.Shell)"
        ".CreateShortcut($env:INFOBIM_SHORTCUT_FILE); "
        "ConvertTo-Json -Compress -InputObject @{"
        "TargetPath = $link.TargetPath; "
        "Arguments = $link.Arguments; "
        "WorkingDirectory = $link.WorkingDirectory}"
    )
    WRITE_SCRIPT: ClassVar[str] = (
        "$link = (New-Object -ComObject WScript.Shell)"
        ".CreateShortcut($env:INFOBIM_SHORTCUT_FILE); "
        "$link.TargetPath = $env:INFOBIM_SHORTCUT_TARGET; "
        "$link.Arguments = $env:INFOBIM_SHORTCUT_ARGUMENTS; "
        "$link.WorkingDirectory = $env:INFOBIM_SHORTCUT_WORKING_DIRECTORY; "
        "$link.Save()"
    )

    def read(self, shortcut_file: Path) -> Optional[ShortcutSpec]:
        if not shortcut_file.is_file():
            return None

        try:
            output: str = self._run(
                self.READ_SCRIPT,
                {"INFOBIM_SHORTCUT_FILE": str(shortcut_file)},
            )
            data: Any = json.loads(output)
        except (subprocess.CalledProcessError, OSError, ValueError):
            return None

        if not isinstance(data, dict):
            return None

        return ShortcutSpec(
            target=str(data.get("TargetPath") or ""),
            arguments=str(data.get("Arguments") or ""),
            working_directory=str(data.get("WorkingDirectory") or ""),
        )

    def write(self, shortcut_file: Path, spec: ShortcutSpec) -> None:
        self._run(
            self.WRITE_SCRIPT,
            {
                "INFOBIM_SHORTCUT_FILE": str(shortcut_file),
                "INFOBIM_SHORTCUT_TARGET": spec.target,
                "INFOBIM_SHORTCUT_ARGUMENTS": spec.arguments,
                "INFOBIM_SHORTCUT_WORKING_DIRECTORY": spec.working_directory,
            },
        )

    @staticmethod
    def _run(script: str, variables: Mapping[str, str]) -> str:
        completed: "subprocess.CompletedProcess[str]" = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            env={**os.environ, **variables},
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout


class ShellLinkFactory:
    """
    The shell link the running platform offers, if it offers one.
    """

    @staticmethod
    def make() -> Optional[ShellLinkPort]:
        if sys.platform == "win32":
            return PowerShellShellLink()

        return None


class InfoBIMExecutable:
    """
    The ``infobim`` command of the environment that is running.
    """

    @staticmethod
    def resolve() -> Path:
        file_name: str = "infobim.exe" if sys.platform == "win32" else "infobim"
        interpreter_directory: Path = Path(sys.executable).parent
        for candidate in (
            interpreter_directory / file_name,
            interpreter_directory / "Scripts" / file_name,
        ):
            if candidate.is_file():
                return candidate.resolve()

        found: Optional[str] = shutil.which("infobim")
        if found is None:
            raise FileNotFoundError(
                "The infobim executable was not found next to the running "
                "interpreter or on PATH."
            )

        return Path(found).resolve()


class ServeShortcut:
    """
    The shortcut that starts ``infobim serve`` from an initialized project.

    It lives in the project root, runs the InfoBIM executable of the
    environment that created it, and starts from the project folder. Where the
    platform has no shell link, there is no shortcut to keep, and none is
    claimed.
    """

    FILE_NAME: ClassVar[str] = "InfoBIM-Serve.lnk"
    ARGUMENTS: ClassVar[str] = "serve"

    def __init__(
        self,
        root_path: Path,
        shell_link: Optional[ShellLinkPort] = None,
        executable: Optional[Path] = None,
    ) -> None:
        self._root_path: Path = root_path.expanduser().resolve()
        self._shell_link: Optional[ShellLinkPort] = (
            shell_link if shell_link is not None else ShellLinkFactory.make()
        )
        self._executable: Optional[Path] = executable

    @property
    def file(self) -> Path:
        return self._root_path / self.FILE_NAME

    @property
    def supported(self) -> bool:
        return self._shell_link is not None

    def expected(self) -> ShortcutSpec:
        executable: Path = (
            self._executable
            if self._executable is not None
            else InfoBIMExecutable.resolve()
        )
        return ShortcutSpec(
            target=str(executable),
            arguments=self.ARGUMENTS,
            working_directory=str(self._root_path),
        )

    def is_ready(self) -> bool:
        if self._shell_link is None:
            return True

        found: Optional[ShortcutSpec] = self._shell_link.read(self.file)
        return found is not None and found.matches(self.expected())

    def ensure(self) -> bool:
        """
        Make the shortcut the expected one. Returns whether it was written.
        """
        if self._shell_link is None:
            raise RuntimeError(
                f"{self.FILE_NAME} is a Windows shortcut; this platform "
                f"({sys.platform}) has none to create."
            )

        if self.is_ready():
            return False

        self._shell_link.write(self.file, self.expected())
        return True

    def describe(self) -> Dict[str, Any]:
        description: Dict[str, Any] = {
            "file": str(self.file),
            "platform": sys.platform,
            "supported": self.supported,
            "present": self.file.is_file(),
        }
        if not self.supported:
            description["note"] = (
                f"{self.FILE_NAME} is a Windows shortcut; nothing was "
                f"created on {sys.platform}."
            )

        return description
