from typing import Any, Dict

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimProjectBaseCommand:

    def test_no_flags_lists_available_project_commands(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        cli_runner.run("init")
        result: CliInvocationResult = cli_runner.run("project")

        assert result.exit_code == 0
        assert result.stderr.strip() == "" or "Traceback" not in result.stderr

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Project Commands"
        assert payload["severity"] is None

        commands_tree: str = payload["content"]["Commands"]
        for expected in ("--create", "--list", "--health", "--inspect", "--refresh"):
            assert expected in commands_tree

    def test_help_flag_returns_project_command_reference(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        cli_runner.run("init")
        result: CliInvocationResult = cli_runner.run("project", "--help")

        assert result.exit_code == 0

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Project Commands"

    def test_short_help_flag_returns_project_command_reference(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        cli_runner.run("init")
        result: CliInvocationResult = cli_runner.run("project", "-h")

        assert result.exit_code == 0

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Project Commands"
