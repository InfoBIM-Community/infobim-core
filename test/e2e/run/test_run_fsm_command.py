"""Installed CLI routing for `infobim run --fsm <yaml>`."""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimRunFsmCommand:
    """
    ``run --fsm`` is the OntoBDC machine runner, exposed by InfoBIM with the
    project selector (``--global-id``) and the entity repository injected.

    The ``container_refresh`` machine is used as a safe, real FSM: it only
    updates the container's own Data Package and RO-Crate metadata, leaving
    user files untouched.
    """

    REFRESH_FSM: str = (
        "ontobdc/container/plugin/machine/container_refresh/"
        "standard_container_refresh.yaml"
    )

    def test_run_fsm_runs_a_real_machine_against_the_project(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "run",
            "--global-id",
            workspace.selector("id"),
            "--fsm",
            self.REFRESH_FSM,
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "OntoBDC Run"
        assert (
            "ContainerRefreshStateTransitionHandler"
            in result.json["description"]
        )

    def test_run_fsm_resolves_project_from_current_directory(
        self,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = workspace.runner().run(
            "run", "--fsm", self.REFRESH_FSM
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "OntoBDC Run"

    def test_run_fsm_accepts_global_id_before_fsm_flag(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "run",
            "--global-id",
            workspace.selector("id"),
            "--fsm",
            self.REFRESH_FSM,
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "OntoBDC Run"

    def test_run_fsm_rejects_nonexistent_statechart(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(
            "run",
            "--global-id",
            workspace.selector("id"),
            "--fsm",
            "/nonexistent/machine.yaml",
        )

        assert result.exit_code != 0
        assert result.json["title"] == "Run Exception"
        assert "not a statechart file" in result.json["content"]["error"]
        assert workspace.snapshot() == before

    def test_run_fsm_requires_a_project(
        self,
        cli_runner: InfobimCliProcessRunner,
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "run",
            "--global-id",
            "urn:uuid:00000000-0000-0000-0000-000000000000",
            "--fsm",
            self.REFRESH_FSM,
        )

        assert result.exit_code != 0
        assert result.json["title"] == "Run Exception"

    @pytest.mark.parametrize(
        "args",
        [
            ("--fsm",),
            ("--fsm", REFRESH_FSM, "value"),
            ("--fsm", REFRESH_FSM, "--capability", "x"),
            ("--fsm", REFRESH_FSM, "--fsm", REFRESH_FSM),
            ("--fsm", REFRESH_FSM, "----bad", "value"),
            ("--global-id",),
            ("--fsm", REFRESH_FSM, "--global-id"),
            ("--fsm", REFRESH_FSM, "--empty", ""),
            ("--fsm", REFRESH_FSM, "--empty", "   "),
        ],
    )
    def test_invalid_fsm_route_does_not_run_a_machine(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("run", *args)

        assert result.exit_code != 0, result.stdout
        assert "OntoBDC Run" not in result.stdout
        assert workspace.snapshot() == before
