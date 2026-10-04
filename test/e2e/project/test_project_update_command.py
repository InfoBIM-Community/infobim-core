import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from rdflib import Graph
from rdflib.namespace import DCTERMS

from test.e2e.project_workspace import ProjectE2eWorkspace
from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimProjectUpdateCommand:
    """
    E2E coverage for `infobim project --update --from <source> --json`.

    The source is accepted in three shapes: a .csv file, a .json file, or
    inline key=value assignments. A source that parses is written into the
    container the command resolves from the working directory, and the fields
    it may carry are the ones the container facade declares as editable.
    """

    def _error_of(self, result: CliInvocationResult) -> str:
        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Run Exception"

        return str(payload["content"]["error"])

    def test_an_update_without_a_project_to_write_to_is_rejected(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "project", "--update", "--from", "title=Sem Container"
        )

        assert result.exit_code == 1
        assert "Missing required input: container_id" in self._error_of(result)

    # ------------------------------------------------------------------
    # Routing: the command is not reached at all
    # ------------------------------------------------------------------

    def test_update_without_a_source_flag_is_rejected(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("project", "--update")

        assert result.exit_code == 1
        assert "Invalid command arguments" in self._error_of(result)

    def test_source_flag_without_a_value_is_rejected(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("project", "--update", "--from")

        assert result.exit_code == 1
        assert "Invalid command arguments" in self._error_of(result)

    # ------------------------------------------------------------------
    # Sources that are not one of the three shapes
    # ------------------------------------------------------------------

    def test_a_bare_word_is_not_a_source(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "project", "--update", "--from", "so-texto"
        )

        assert result.exit_code == 1
        assert "Invalid command arguments" in self._error_of(result)

    def test_an_empty_source_is_rejected(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "project", "--update", "--from", ""
        )

        assert result.exit_code == 1
        assert "Invalid command arguments" in self._error_of(result)

    # ------------------------------------------------------------------
    # Sources of an accepted shape whose content does not parse
    # ------------------------------------------------------------------

    def test_a_missing_json_file_is_reported_by_path(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "project", "--update", "--from", "ausente.json"
        )

        assert result.exit_code == 1
        assert self._error_of(result) == (
            "Container update source file not found: ausente.json"
        )

    def test_a_missing_csv_file_is_reported_by_path(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "project", "--update", "--from", "ausente.csv"
        )

        assert self._error_of(result) == (
            "Container update source file not found: ausente.csv"
        )

    def test_a_json_source_that_is_not_an_object_is_rejected(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        source: Path = tmp_path / "list.json"
        source.write_text(json.dumps(["title", "description"]), encoding="utf-8")

        result: CliInvocationResult = cli_runner.run(
            "project", "--update", "--from", "list.json"
        )

        assert self._error_of(result) == (
            "Container update JSON source must contain an object."
        )

    def test_a_csv_source_with_more_than_one_row_is_rejected(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        source: Path = tmp_path / "rows.csv"
        source.write_text("title\nPrimeiro\nSegundo\n", encoding="utf-8")

        result: CliInvocationResult = cli_runner.run(
            "project", "--update", "--from", "rows.csv"
        )

        assert self._error_of(result) == (
            "Container update CSV source must contain exactly one data row."
        )

    def test_a_csv_source_with_only_a_header_is_rejected(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        source: Path = tmp_path / "header.csv"
        source.write_text("title,description\n", encoding="utf-8")

        result: CliInvocationResult = cli_runner.run(
            "project", "--update", "--from", "header.csv"
        )

        assert self._error_of(result) == (
            "Container update CSV source must contain exactly one data row."
        )

    def test_an_assignment_without_a_key_is_rejected(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "project", "--update", "--from", "=semchave"
        )

        assert self._error_of(result) == (
            "Invalid container update assignment: =semchave"
        )

    def test_a_repeated_assignment_key_is_rejected(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "project", "--update", "--from", "title=A,title=B"
        )

        assert self._error_of(result) == "Duplicate container update key: title"

    @pytest.mark.parametrize("source_kind", ["inline", "json", "csv"])
    @pytest.mark.parametrize("selector", ["cwd", "id"])
    def test_update_persists_metadata_and_synchronizes_listing(
        self, tmp_path: Path, source_kind: str, selector: str
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        title: str = "Updated Project"
        description: str = "Updated through the CLI"
        source: str
        if source_kind == "inline":
            source = f"title={title},description={description}"
        else:
            source_path: Path = tmp_path / f"update.{source_kind}"
            content: str = (
                json.dumps({"title": title, "description": description})
                if source_kind == "json"
                else f"title,description\n{title},{description}\n"
            )
            source_path.write_text(content, encoding="utf-8")
            source = str(source_path)
        arguments: List[str] = ["project"]
        if selector == "id":
            arguments.extend(["--global-id", workspace.identifier])
        arguments.extend(["--update", "--from", source])
        user_file: Path = workspace.project / "notes.txt"
        user_file.write_text("preserve me", encoding="utf-8")

        runner: InfobimCliProcessRunner = (
            InfobimCliProcessRunner(tmp_path) if selector == "id" else workspace.runner()
        )
        result: CliInvocationResult = runner.run(*arguments)

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Container Updated"
        assert result.json["severity"] is None
        graph: Graph = Graph().parse(
            workspace.project / ".__ontobdc__" / "container.ttl", format="turtle"
        )
        assert title in {str(value) for value in graph.objects(None, DCTERMS.title)}
        assert description in {str(value) for value in graph.objects(None, DCTERMS.description)}
        listing: CliInvocationResult = InfobimCliProcessRunner(tmp_path).run(
            "project", "--list"
        )
        assert listing.exit_code == 0, listing.stdout + listing.stderr
        entries: List[Dict[str, Any]] = listing.json["content"]["projects"]
        assert len(entries) == 1
        assert entries[0]["id"] == workspace.identifier
        assert entries[0]["title"] == title
        assert user_file.read_text(encoding="utf-8") == "preserve me"
