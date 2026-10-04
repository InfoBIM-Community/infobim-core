import os
import pty
import sys
import fcntl
import struct
import termios
import json
import time
import select
from typing import Any, Dict, List, Optional, Sequence
from pathlib import Path
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CliInvocationResult:
    arguments: List[str]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def json(self) -> Dict[str, Any]:
        return json.loads(self.stdout)


class _BaseCliProcessRunner:
    _TIMEOUT_SECONDS: int = 30
    _EXECUTABLE_NAME: str = ""

    def __init__(self, isolated_project_root: Path) -> None:
        self._isolated_project_root: Path = isolated_project_root

    def run(self, *arguments: str) -> CliInvocationResult:
        full_arguments: List[str] = [str(self._executable_path()), *arguments, "--json"]
        environment: Dict[str, str] = dict(os.environ)
        environment.pop("ONTOBDC_PROJECT_ROOT", None)
        environment.pop("INFOBIM_PROJECT_ROOT", None)
        repository: Path = Path(__file__).resolve().parents[2]
        source_paths: List[str] = [str(repository / "src"), str(repository)]
        if "PYTHONPATH" in environment:
            source_paths.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(source_paths)

        completed_process: "subprocess.CompletedProcess[str]" = subprocess.run(
            full_arguments,
            cwd=self._isolated_project_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=self._TIMEOUT_SECONDS,
        )

        return CliInvocationResult(
            arguments=list(arguments),
            exit_code=completed_process.returncode,
            stdout=completed_process.stdout,
            stderr=completed_process.stderr,
        )

    def _executable_path(self) -> Path:
        executable_path: Path = Path(sys.executable).parent / self._EXECUTABLE_NAME
        if not executable_path.is_file():
            raise FileNotFoundError(
                f"No '{self._EXECUTABLE_NAME}' executable found next to the running "
                f"interpreter at '{executable_path}'. Is the package installed in this venv?"
            )
        return executable_path


class InfobimCliProcessRunner(_BaseCliProcessRunner):
    _EXECUTABLE_NAME: str = "infobim"


class OntobdcCliProcessRunner(_BaseCliProcessRunner):
    _EXECUTABLE_NAME: str = "ontobdc"


@dataclass(frozen=True)
class TerminalStep:
    """
    Keys sent to the terminal, then what to wait for before the next step.

    ``wait_for`` is text the command must print after the keys were sent;
    ``pause_seconds`` is a fixed wait, for keys whose effect prints nothing
    distinctive.
    """

    keys: str
    wait_for: Optional[str] = None
    pause_seconds: float = 0.0


class InfobimTerminalProcessRunner:
    """Drive an ``infobim`` command that takes over a pseudo-terminal."""

    _TIMEOUT_SECONDS: int = 30
    _READ_INTERVAL_SECONDS: float = 0.2
    _READ_CHUNK_SIZE: int = 65536
    _TERMINAL_ENVIRONMENT: Dict[str, str] = {
        "TERM": "xterm-256color",
        "COLUMNS": "120",
        "LINES": "40",
    }

    def __init__(self, isolated_project_root: Path) -> None:
        self._isolated_project_root: Path = isolated_project_root

    def run(
        self,
        *arguments: str,
        ready_marker: str,
        keys: str,
        steps: Sequence[TerminalStep] = (),
    ) -> CliInvocationResult:
        """
        Run the command and, once ``ready_marker`` is on screen, play the
        ``steps`` in order and finally send ``keys``.
        """
        environment: Dict[str, str] = dict(os.environ)
        environment.pop("ONTOBDC_PROJECT_ROOT", None)
        environment.pop("INFOBIM_PROJECT_ROOT", None)
        repository: Path = Path(__file__).resolve().parents[2]
        source_paths: List[str] = [str(repository / "src"), str(repository)]
        if "PYTHONPATH" in environment:
            source_paths.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(source_paths)
        environment.update(self._TERMINAL_ENVIRONMENT)

        controller_descriptor: int
        terminal_descriptor: int
        controller_descriptor, terminal_descriptor = pty.openpty()
        # A real terminal reports its size; programs that lay out or scale
        # to the terminal read it from the pseudo-terminal.
        fcntl.ioctl(
            terminal_descriptor,
            termios.TIOCSWINSZ,
            struct.pack(
                "HHHH",
                int(self._TERMINAL_ENVIRONMENT["LINES"]),
                int(self._TERMINAL_ENVIRONMENT["COLUMNS"]),
                0,
                0,
            ),
        )
        process: "subprocess.Popen[bytes]" = subprocess.Popen(
            [str(self._executable_path()), *arguments],
            cwd=self._isolated_project_root,
            env=environment,
            stdin=terminal_descriptor,
            stdout=terminal_descriptor,
            stderr=terminal_descriptor,
            close_fds=True,
        )
        os.close(terminal_descriptor)

        screen: bytes = b""
        pending: List[TerminalStep] = [*steps, TerminalStep(keys)]
        ready: bool = False
        waiting: Optional[TerminalStep] = None
        sent_at: int = 0
        resume_at: float = 0.0
        deadline: float = time.monotonic() + self._TIMEOUT_SECONDS
        try:
            while process.poll() is None and time.monotonic() < deadline:
                readable: List[int]
                readable, _, _ = select.select(
                    [controller_descriptor], [], [], self._READ_INTERVAL_SECONDS
                )
                if readable:
                    try:
                        screen += os.read(controller_descriptor, self._READ_CHUNK_SIZE)
                    except OSError:
                        break
                if not ready:
                    ready = ready_marker.encode("utf-8") in screen
                if not ready or not pending:
                    continue
                if waiting is not None:
                    if waiting.wait_for is not None and (
                        waiting.wait_for.encode("utf-8") not in screen[sent_at:]
                    ):
                        continue
                    if time.monotonic() < resume_at:
                        continue
                    waiting = None
                waiting = pending.pop(0)
                sent_at = len(screen)
                resume_at = time.monotonic() + waiting.pause_seconds
                os.write(controller_descriptor, waiting.keys.encode("utf-8"))
            screen += self._drain(controller_descriptor)
            if process.poll() is None:
                process.kill()
                process.wait()
                raise subprocess.TimeoutExpired(
                    process.args, self._TIMEOUT_SECONDS, output=screen
                )
        finally:
            os.close(controller_descriptor)

        return CliInvocationResult(
            arguments=list(arguments),
            exit_code=process.returncode,
            stdout=screen.decode("utf-8", errors="replace"),
            stderr="",
        )

    def _drain(self, controller_descriptor: int) -> bytes:
        """Read what the command printed right before it exited."""
        drained: bytes = b""
        while True:
            readable: List[int]
            readable, _, _ = select.select([controller_descriptor], [], [], 0.1)
            if not readable:
                return drained
            try:
                chunk: bytes = os.read(controller_descriptor, self._READ_CHUNK_SIZE)
            except OSError:
                return drained
            if not chunk:
                return drained
            drained += chunk

    def _executable_path(self) -> Path:
        executable_path: Path = Path(sys.executable).parent / "infobim"
        if not executable_path.is_file():
            raise FileNotFoundError(
                f"No 'infobim' executable found next to the running "
                f"interpreter at '{executable_path}'. Is the package installed in this venv?"
            )
        return executable_path
