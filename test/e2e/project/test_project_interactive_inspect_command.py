from pathlib import Path
from typing import List

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
