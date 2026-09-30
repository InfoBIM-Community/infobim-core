"""One command stream per connected terminal, scoped to the server directory."""

import os
import sys
import json
import shlex
import signal
from pathlib import Path
from secrets import token_urlsafe
from threading import Lock
from subprocess import PIPE, STDOUT, Popen
from typing import ClassVar, Dict, List, Optional, Tuple
from queue import Queue


class TerminalSession:
    EXECUTABLES: ClassVar[Tuple[str, ...]] = ("infobim", "ontobdc")

    def __init__(self, directory: Path) -> None:
        self.token: str = token_urlsafe(32)
        self.events: Queue[Tuple[str, str]] = Queue()
        self.directory: Path = directory
        self.lock: Lock = Lock()
        self.process: Optional[Popen[str]] = None
        self.closed: bool = False
        self.busy: bool = False

    def execute(self, command: str) -> None:
        try:
            normalized_command: str = self._normalize(command)
            with self.lock:
                if self.closed:
                    return
                environment: Dict[str, str] = dict(os.environ)
                environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]
                environment["PYTHONUNBUFFERED"] = "1"
                # This session's real display width is the browser panel's,
                # not whatever shutil.get_terminal_size() would guess for a
                # subprocess piped through here -- see ontobdc.cli's own
                # BORDERLESS_ENVIRONMENT_VARIABLE for why that makes the
                # framed box the wrong choice for this specific caller.
                environment["ONTOBDC_CLI_BORDERLESS"] = "1"
                self.process = Popen(
                    normalized_command, shell=True, cwd=self.directory, env=environment,
                    stdin=PIPE, stdout=PIPE, stderr=STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    start_new_session=True,
                )
                process: Popen[str] = self.process
            if process.stdin is None or process.stdout is None:
                raise RuntimeError("Command pipes were not created")
            process.stdin.close()
            for line in process.stdout:
                self.events.put(("message", json.dumps(line)))
            code: int = process.wait()
            self.events.put(("complete", str(code)))
        except (OSError, ValueError) as error:
            self.events.put(("message", json.dumps(f"{error}\n")))
            self.events.put(("complete", "1"))
        finally:
            with self.lock:
                self.process = None
                self.busy = False

    def _normalize(self, command: str) -> str:
        """
        Prepend `infobim` to a command that does not already name an
        executable, so a user of this embedded terminal can type `3d` or
        `project --health` instead of spelling out the executable every
        time.

        Nothing else is added: this session's subprocess already runs
        with cwd set to the Project directory, which is exactly what every
        command's own no-selector parameter strategy already resolves
        against.
        """
        tokens: List[str] = shlex.split(command)
        if not tokens:
            return command

        if tokens[0] not in self.EXECUTABLES:
            tokens.insert(0, "infobim")

        return shlex.join(tokens)

    def close(self) -> None:
        with self.lock:
            self.closed = True
            process: Optional[Popen[str]] = self.process
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    return
