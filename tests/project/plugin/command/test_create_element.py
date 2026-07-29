import json

import pytest

from infobim.cli.domain.context import InfoBIMCliContext
from infobim.project.plugin.command.create_element import (
    ProjectCreateElementCommand,
)
from ontobdc.cli.domain.request.command import CliCommandRequest


def test_accepts_project_entity_create_command() -> None:
    assert ProjectCreateElementCommand.accepts(
        [
            "project",
            "--project",
            "project-123",
            "--entity",
            "WorkStream",
            "--create",
            "Cabeamento lógico",
        ]
    )


def test_command_generates_work_stream_workbook(
    tmp_path,
    monkeypatch,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("frictionless")
    rdflib = pytest.importorskip("rdflib")
    from rdflib.namespace import OWL, RDF
    container_path = tmp_path / "project"
    monkeypatch.setattr(
        ProjectCreateElementCommand,
        "_resolve_project_path",
        lambda self, project_id: container_path,
    )
    context = InfoBIMCliContext(
        root_path=str(tmp_path),
        parameters={"project_id": "project-123"},
    )
    request = CliCommandRequest(
        logical_component="project",
        component_action="create_element",
        command_args=[
            "--project",
            "project-123",
            "--entity",
            "WorkStream",
            "--create",
            "Cabeamento lógico",
        ],
        context=context,
    )
    command = ProjectCreateElementCommand(request)

    assert command.check()
    response = command.run()

    assert response.content["entity"] == "WorkStream"
    assert response.content["element_name"] == "Cabeamento lógico"
    workbook_path = container_path / "payload" / "document" / "workstreams.xlsx"
    workbook = openpyxl.load_workbook(workbook_path)
    worksheet = workbook["WorkStream"]
    assert [cell.value for cell in worksheet[1]] == [
        "GlobalId",
        "Name",
        "Description",
        "What",
        "Why",
        "Who",
        "Where",
        "When",
        "How",
        "HowMuch",
    ]
    assert worksheet["B2"].value == "Cabeamento lógico"
    assert worksheet["C2"].value is None
    linkset_path = container_path / ".__ontobdc__" / "linkset" / "WorkStream.ttl"
    assert response.content["linkset_path"] == str(linkset_path)
    assert response.content["link_count"] == 10

    graph = rdflib.Graph()
    graph.parse(linkset_path, format="turtle")
    LS = rdflib.Namespace(
        "https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#"
    )
    assert (
        None,
        OWL.imports,
        rdflib.URIRef(
            "https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset"
        ),
    ) in graph
    assert len(set(graph.subjects(RDF.type, LS.DirectedBinaryLink))) == 10
    assert (
        rdflib.URIRef(
            "urn:infobim:icdd:workstream:identifier:workbook:description"
        ),
        LS.identifier,
        rdflib.Literal("Description"),
    ) in graph


def test_command_preserves_existing_work_stream_rows(
    tmp_path,
    monkeypatch,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("frictionless")
    container_path = tmp_path / "project"
    monkeypatch.setattr(
        ProjectCreateElementCommand,
        "_resolve_project_path",
        lambda self, project_id: container_path,
    )

    def execute(name: str):
        context = InfoBIMCliContext(
            root_path=str(tmp_path),
            parameters={"project_id": "project-123"},
        )
        request = CliCommandRequest(
            logical_component="project",
            component_action="create_element",
            command_args=[
                "--project",
                "project-123",
                "--entity",
                "WorkStream",
                "--create",
                name,
            ],
            context=context,
        )
        command = ProjectCreateElementCommand(request)
        assert command.check()
        return command.run()

    execute("Cabeamento lógico")
    workbook_path = container_path / "payload" / "document" / "workstreams.xlsx"
    workbook = openpyxl.load_workbook(workbook_path)
    worksheet = workbook["WorkStream"]
    worksheet["D2"] = "Executar a infraestrutura de dados."
    workbook.save(workbook_path)

    response = execute("Passagem de fibras")

    workbook = openpyxl.load_workbook(workbook_path)
    worksheet = workbook["WorkStream"]
    assert worksheet.max_row == 3
    assert worksheet["B2"].value == "Cabeamento lógico"
    assert worksheet["D2"].value == "Executar a infraestrutura de dados."
    assert worksheet["B3"].value == "Passagem de fibras"
    assert response.content["work_stream_count"] == 2

    datapackage = json.loads(
        (container_path / ".__ontobdc__" / "datapackage.json").read_text(
            encoding="utf-8"
        )
    )
    assert datapackage["resources"][0]["name"] == "work_stream"
