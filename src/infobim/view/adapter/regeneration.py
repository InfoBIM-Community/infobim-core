from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from infobim.view.adapter.component import InfoBIMComponentSourceAdapter
from infobim.view.adapter.machine import (
    InfoBIMSurfaceGenerationStateTransitionHandler,
)
from infobim.view.adapter.project import InfoBIMProjectPresentationRepository
from ontobdc.cli.adapter.context import CliContextAdapter
from ontobdc.shared.adapter.filesystem import (
    remove_directory_tree,
    remove_file,
)
from ontobdc.view.adapter.surface.context import SurfaceContextAdapter
from ontobdc.view.plugin.capability.transformation.data_gathered import (
    DataGatheredCapability,
)


REQUEST_FILE_NAME = "surface-regeneration.request.json"
PID_FILE_NAME = "surface-regeneration.pid"
LOG_FILE_NAME = "surface-regeneration.log"
POLL_SECONDS = 0.5
DEBOUNCE_SECONDS = 0.8


def _metadata_directory(project_path: Path) -> Path:
    return project_path / ".__ontobdc__"


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


class InfoBIMSurfaceRegenerationWorker:
    """Regenerate a Surface after browser-side workbook mutations."""

    def __init__(
        self,
        *,
        project_id: str,
        project_path: Path,
        context_root: Path,
        language: str,
    ) -> None:
        self.project_id = project_id
        self.project_path = project_path.resolve()
        self.context_root = context_root.resolve()
        self.language = language

    def request_files(self) -> list[Path]:
        return sorted(
            self.project_path.rglob(REQUEST_FILE_NAME),
            key=lambda path: str(path),
        )

    def latest_request_mtime_ns(self) -> int:
        latest = 0
        for path in self.request_files():
            try:
                latest = max(latest, path.stat().st_mtime_ns)
            except OSError:
                continue
        return latest

    def regenerate(self) -> None:
        context = CliContextAdapter([], root_dir=str(self.context_root))
        for key, value in (
            ("project_id", self.project_id),
            ("project_path", str(self.project_path)),
            ("container_id", self.project_id),
            ("container_path", str(self.project_path)),
            ("representation", "html"),
            ("view_type", "standard"),
            ("language", self.language),
        ):
            context.set_parameter_value(key, value)

        presentation = InfoBIMProjectPresentationRepository().load(
            project_id=self.project_id,
            project_path=str(self.project_path),
        )
        context.set_parameter_value(
            "surface_component_scripts",
            InfoBIMComponentSourceAdapter().scripts(
                root_path=str(self.project_path)
            ),
        )

        # Same cleanup ``ViewProjectCommand.run()`` does before its own
        # generation pass: without dropping the frozen surface HTML and the
        # DATA_GATHERED ETL artifact, every capability's check() reports
        # "already satisfied" and the handler returns having rebuilt nothing —
        # so a field edited in the browser never reaches the regenerated page.
        surface_path = SurfaceContextAdapter().surface_path(context)
        if surface_path.is_file():
            remove_file(surface_path)
        etl_directory = DataGatheredCapability.state_directory(context)
        if etl_directory.is_dir():
            remove_directory_tree(etl_directory)

        InfoBIMSurfaceGenerationStateTransitionHandler(
            context=context,
            presentation=presentation,
        ).execute()

    def run(self) -> None:
        metadata = _metadata_directory(self.project_path)
        metadata.mkdir(parents=True, exist_ok=True)
        pid_path = metadata / PID_FILE_NAME
        pid_path.write_text(str(os.getpid()), encoding="utf-8")
        handled_mtime_ns = self.latest_request_mtime_ns()
        pending_mtime_ns = handled_mtime_ns
        pending_since: Optional[float] = None
        try:
            while True:
                latest = self.latest_request_mtime_ns()
                if latest > pending_mtime_ns:
                    pending_mtime_ns = latest
                    pending_since = time.monotonic()
                if (
                    pending_since is not None
                    and time.monotonic() - pending_since >= DEBOUNCE_SECONDS
                ):
                    try:
                        self.regenerate()
                    except Exception as error:
                        print(
                            json.dumps(
                                {
                                    "event": "surface_regeneration_failed",
                                    "error": f"{type(error).__name__}: {error}",
                                },
                                ensure_ascii=False,
                            ),
                            flush=True,
                        )
                    else:
                        handled_mtime_ns = pending_mtime_ns
                        print(
                            json.dumps(
                                {
                                    "event": "surface_regenerated",
                                    "request_mtime_ns": handled_mtime_ns,
                                }
                            ),
                            flush=True,
                        )
                    pending_since = None
                time.sleep(POLL_SECONDS)
        finally:
            try:
                if pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                    pid_path.unlink(missing_ok=True)
            except OSError:
                pass


class InfoBIMSurfaceRegenerationWorkerLauncher:
    """Ensure one detached regeneration worker exists per Project."""

    def ensure_running(
        self,
        *,
        project_id: str,
        project_path: str,
        context_root: str,
        language: str,
    ) -> Optional[int]:
        project = Path(project_path).expanduser().resolve()
        metadata = _metadata_directory(project)
        metadata.mkdir(parents=True, exist_ok=True)
        pid_path = metadata / PID_FILE_NAME
        try:
            existing_pid = int(pid_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing_pid = 0
        if _pid_is_running(existing_pid):
            return existing_pid

        log_stream = (metadata / LOG_FILE_NAME).open("a", encoding="utf-8")
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "infobim.view.adapter.regeneration",
                    "--worker",
                    "--project-id",
                    project_id,
                    "--project-path",
                    str(project),
                    "--context-root",
                    str(Path(context_root).expanduser().resolve()),
                    "--language",
                    language,
                ],
                cwd=str(project),
                stdin=subprocess.DEVNULL,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            log_stream.close()
        pid_path.write_text(str(process.pid), encoding="utf-8")
        return process.pid


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--context-root", required=True)
    parser.add_argument("--language", default="en")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.worker:
        return 2
    InfoBIMSurfaceRegenerationWorker(
        project_id=args.project_id,
        project_path=Path(args.project_path),
        context_root=Path(args.context_root),
        language=args.language,
    ).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
