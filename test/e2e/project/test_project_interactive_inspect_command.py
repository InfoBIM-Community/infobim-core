import json
import os
from pathlib import Path
from typing import List

import ezdxf
import pytest

from test.e2e.project_workspace import ProjectE2eWorkspace
from test.e2e.cli_process_runner import (
    CliInvocationResult,
    InfobimCliProcessRunner,
    InfobimTerminalProcessRunner,
)


class TestInfobimProjectInteractiveInspectCommand:

    TITLE: str = "InfoBIM Project"
    QUIT_KEY: str = "q"
    EXPAND_ALL_KEY: str = "e"
    CURSOR_DOWN_KEY: str = "\x1b[B"
    OPEN_KEY: str = "o"
    PYSIDE6_CAPABILITY_ID: str = (
        "org.infobim._2d.plugin.capability.loader.pyside6"
    )
    OPEN_FILE_EVENT_NAME: str = "__file_opening_strategy_found__.json"

    @pytest.mark.parametrize("interactive_flag", ["--interactive", "-i"])
    def test_interactive_inspect_opens_project_tree_and_quits(
        self, tmp_path: Path, interactive_flag: str
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        terminal_runner: InfobimTerminalProcessRunner = InfobimTerminalProcessRunner(
            tmp_path
        )

        result: CliInvocationResult = terminal_runner.run(
            "project",
            "--global-id",
            workspace.selector("id"),
            "--inspect",
            interactive_flag,
            ready_marker=self.TITLE,
            keys=self.QUIT_KEY,
        )

        assert result.exit_code == 0, result.stdout
        assert self.TITLE in result.stdout

    @pytest.mark.parametrize(
        "flags",
        [["--interactive", "--inspect"], ["-i", "--inspect"]],
    )
    def test_interactive_inspect_accepts_flags_in_any_order(
        self, tmp_path: Path, flags: List[str]
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        terminal_runner: InfobimTerminalProcessRunner = InfobimTerminalProcessRunner(
            tmp_path
        )

        result: CliInvocationResult = terminal_runner.run(
            "project",
            *flags,
            "--global-id",
            workspace.selector("id"),
            ready_marker=self.TITLE,
            keys=self.QUIT_KEY,
        )

        assert result.exit_code == 0, result.stdout
        assert self.TITLE in result.stdout

    @pytest.mark.parametrize("interactive_flag", ["--interactive", "-i"])
    def test_interactive_inspect_requires_a_project(
        self, cli_runner: InfobimCliProcessRunner, interactive_flag: str
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "project",
            "--global-id",
            "urn:uuid:00000000-0000-0000-0000-000000000000",
            "--inspect",
            interactive_flag,
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"

    def test_interactive_inspect_opens_real_dxf_through_mime_capability(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        dxf_path: Path = workspace.project / "e2e-open-file.dxf"
        document = ezdxf.new("R2010")
        document.modelspace().add_line((0, 0), (1000, 0))
        document.saveas(dxf_path)

        refresh: CliInvocationResult = InfobimCliProcessRunner(tmp_path).run(
            "project",
            "--global-id",
            workspace.selector("id"),
            "--refresh",
        )
        assert refresh.exit_code == 0, refresh.stdout + refresh.stderr
        assert dxf_path.name in workspace.manifest_files()

        qt_bootstrap: Path = tmp_path / "qt-e2e-bootstrap"
        qt_bootstrap.mkdir()
        (qt_bootstrap / "sitecustomize.py").write_text(
            "\n".join(
                [
                    "from PySide6 import QtCore, QtWidgets",
                    "",
                    "_original_exec = QtWidgets.QDialog.exec",
                    "",
                    "def _exec(dialog):",
                    "    QtCore.QTimer.singleShot(0, dialog.accept)",
                    "    return _original_exec(dialog)",
                    "",
                    "QtWidgets.QDialog.exec = _exec",
                    "if hasattr(QtWidgets.QDialog, 'exec_'):",
                    "    QtWidgets.QDialog.exec_ = _exec",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        existing_pythonpath: str = os.environ.get("PYTHONPATH", "")
        pythonpath: str = str(qt_bootstrap)
        if existing_pythonpath:
            pythonpath = f"{pythonpath}{os.pathsep}{existing_pythonpath}"
        monkeypatch.setenv("PYTHONPATH", pythonpath)
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

        terminal_runner: InfobimTerminalProcessRunner = InfobimTerminalProcessRunner(
            tmp_path
        )
        result: CliInvocationResult = terminal_runner.run(
            "project",
            "--global-id",
            workspace.selector("id"),
            "--inspect",
            "-i",
            ready_marker=self.TITLE,
            keys=(
                self.EXPAND_ALL_KEY
                + (self.CURSOR_DOWN_KEY * 64)
                + self.OPEN_KEY
                + self.QUIT_KEY
            ),
        )

        assert result.exit_code == 0, result.stdout
        assert self.TITLE in result.stdout

        event_paths: List[Path] = list(tmp_path.rglob(self.OPEN_FILE_EVENT_NAME))
        assert len(event_paths) == 1, event_paths
        event = json.loads(event_paths[0].read_text(encoding="utf-8"))
        assert event["state"] == "file_opening_strategy_found"
        assert event["strategies"] == [self.PYSIDE6_CAPABILITY_ID]
        assert event["results"][self.PYSIDE6_CAPABILITY_ID] == {
            "handled": True,
            "handler": "pyside6",
            "message": "Opened the DXF file in the InfoBIM 2D viewer.",
            "error": None,
        }
