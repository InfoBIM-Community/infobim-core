"""Installed CLI routing for `infobim annotate --title <value>` (create)."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


OBDC = Namespace("http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl#")
ANNOTATION_TYPE = URIRef(
    "http://datacenter.app.br/ontology/domain/annotation/taxonomy/type.ttl#Annotation"
)


class TestInfobimAnnotationCreateCommand:

    def test_create_adds_an_annotation_to_the_project(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--title",
            "Review drawing",
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Annotation Created"
        assert result.json["content"]["title"] == "Review drawing"
        assert result.json["content"]["annotation_type"] == "note"

    def test_create_accepts_optional_type_text_and_author(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--type",
            "issue",
            "--title",
            "Found a problem",
            "--text",
            "Body text",
            "--author",
            "Elias",
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Annotation Created"
        assert result.json["content"]["annotation_type"] == "issue"

    def test_create_persists_annotation_visible_to_list(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        created: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--title",
            "Review drawing",
        )
        assert created.exit_code == 0

        listed: CliInvocationResult = cli_runner.run(
            "annotate", "--global-id", workspace.selector("id"), "--list"
        )
        assert listed.exit_code == 0
        groups: List[Dict[str, Any]] = listed.json["content"]["groups"]
        annotations: List[Dict[str, Any]] = [
            annotation
            for group in groups
            for annotation in group["annotations"]
        ]
        assert len(annotations) == 1
        assert annotations[0]["global_id"] == created.json["content"]["global_id"]

    def test_create_registers_a_data_entity_in_the_dataset_metadata(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--title",
            "Review drawing",
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        dataset: Path = Path(result.json["content"]["dataset_path"])
        graph: Graph = Graph().parse(
            dataset / ".__ontobdc__" / "dataset.ttl", format="turtle"
        )
        entities: List[Any] = list(graph.objects(None, OBDC.hasDataEntity))
        assert len(entities) == 1, entities
        assert (entities[0], RDF.type, OBDC.DataEntity) in graph
        assert (entities[0], RDF.type, ANNOTATION_TYPE) in graph

    @pytest.mark.parametrize(
        "args",
        [
            ("--type", "note"),
            ("--title",),
            ("--title", "Title", "--unknown", "value"),
            ("--title", "Title", "--title", "Other"),
        ],
    )
    def test_invalid_create_route_does_not_persist_annotations(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("annotate", *args)

        assert result.exit_code != 0, result.stdout
        assert "Annotation Created" not in result.stdout
        assert workspace.snapshot() == before
