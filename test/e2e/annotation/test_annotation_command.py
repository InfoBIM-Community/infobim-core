"""Real annotation command through its DXF viewer, form and CSV persistence."""

import csv
from datetime import datetime
from urllib.parse import quote
import pytest
from rdflib import Graph, RDF, URIRef, RDFS, Literal
from brasidatacenter import resources
from ontobdc.annotation.domain.model.annotation import Annotation
from ontobdc.annotation.plugin.capability.transformation.annotation_type_identified import (
    AnnotationTypeIdentifiedCapability as Type,
)
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.container.adapter.entity_linkset import EntityLinkset
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.shared.domain.vocabulary import OBDC, ICDD_CONTAINER, ICDD_LINKSET
from test.e2e.annotation.support import project, run


def error_text(result):
    return result.json["content"]["error"].replace("\n", "")


COLUMNS = [
    "global_id",
    "annotation_type",
    "title",
    "text",
    "geometry",
    "source_document",
    "author",
    "created_at",
    "related_documents",
]


def records(directory):
    files = list((directory / "annotation/payload/document").glob("*.csv"))
    assert len(files) == 1, files
    with files[0].open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        assert reader.fieldnames == COLUMNS
    return files[0], rows


@pytest.mark.parametrize(
    "requested,identifier",
    [
        ("issue", "issue"),
        ("alerta", "issue"),
        ("dúvida", "question"),
        (str(Type.ONTOLOGY_IRI) + "#Issue", "issue"),
    ],
)
def test_command_creates_complete_annotation_csv_dataset_links_and_etl(
    tmp_path, requested, identifier
):
    directory, drawing = project(tmp_path)
    before_context = tmp_path / ".__ontobdc__/context.ttl"
    before = before_context.read_bytes() if before_context.exists() else None
    result = run(directory, "annotation", "--type", requested, "--point", str(drawing))
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = result.json
    assert payload["title"] == "Annotation Created"
    path, rows = records(directory)
    assert len(rows) == 1
    row = rows[0]
    assert row["global_id"] == payload["content"]["global_id"]
    assert row["annotation_type"] == identifier
    assert row["title"] == "Review drawing"
    assert row["text"] == 'Body, "quoted"\nsecond line' and row["author"] == "Elias"
    assert row["geometry"] == "LINESTRING(1.5 2, 3 4)"
    datetime.fromisoformat(row["created_at"])
    expected = (
        "urn:ontobdc:storage/container/"
        + quote(ContainerDocumentIri.container_id(directory), safe="")
        + "/payload/document/planta.dxf"
    )
    assert row["source_document"] == expected == payload["content"]["source_document"]
    dataset = directory / "annotation"
    graph = Graph().parse(StorageBootstrap.get_dataset_storage_file_path(dataset))
    assert list(graph.subjects(RDF.type, OBDC.EntityDataset))
    assert list(graph.subjects(RDF.type, URIRef(Annotation.ENTITY_IRI)))
    linkset = EntityLinkset(dataset, path)
    graph = Graph().parse(linkset.path)
    assert (
        linkset.data_source_document,
        RDF.type,
        ICDD_CONTAINER.InternalDocument,
    ) in graph
    links = list(graph.subjects(RDF.type, ICDD_LINKSET.DirectedBinaryLink))
    assert len(links) == 1
    target = graph.value(links[0], ICDD_LINKSET.hasToLinkElement)
    assert graph.value(target, ICDD_LINKSET.hasDocument) == URIRef(expected)
    etl = directory / ".__ontobdc__/etl/annotation/creation/point"
    events = list(etl.glob("*.json"))
    assert len(events) == 7
    assert len(list(etl.iterdir())) == 8
    assert (etl / "__annotation_type_identified__.jsonld").is_file()
    import json

    assert {json.loads(path.read_text())["state"] for path in events} == {
        "__" + state + "__"
        for state in [
            "annotation_type_identified",
            "file_metadata_extracted",
            "drawable_documents_loaded",
            "drawable_file_viewer_opened",
            "points_captured",
            "annotation_details_filled",
            "annotations_created",
        ]
    }
    assert (before_context.read_bytes() if before_context.exists() else None) == before


def test_second_command_appends_to_same_csv(tmp_path):
    directory, drawing = project(tmp_path)
    first = run(directory, "annotation", "--point", str(drawing), "--type", "note")
    assert first.exit_code == 0, first.stdout + first.stderr
    path, rows = records(directory)
    second = run(directory, "annotation", "--type", "question", "--point", str(drawing))
    assert second.exit_code == 0, second.stdout + second.stderr
    second_path, rows = records(directory)
    assert path == second_path and len(rows) == 2
    assert [row["annotation_type"] for row in rows] == ["note", "question"]
    assert rows[0]["global_id"] != rows[1]["global_id"]


def test_cancelled_form_fails_without_persisting_annotation(tmp_path):
    directory, drawing = project(tmp_path)
    result = run(
        directory,
        "annotation",
        "--type",
        "note",
        "--point",
        str(drawing),
        mode="cancel",
    )
    assert result.exit_code != 0 and "RuntimeError" in result.json["description"]
    assert not (directory / "annotation").exists()
    assert not list(tmp_path.rglob("__annotations_created__.json"))
    assert not list(tmp_path.rglob("__annotation_details_filled__.json"))


@pytest.mark.parametrize("kind", ["unknown", "dwg"])
def test_unhandled_type_or_dwg_is_clear_and_does_not_persist(tmp_path, kind):
    directory, drawing = project(tmp_path)
    if kind == "dwg":
        drawing = directory / "drawing.dwg"
        drawing.write_bytes(b"AC1032")
    result = run(
        directory,
        "annotation",
        "--type",
        "no-such-type" if kind == "unknown" else "note",
        "--point",
        str(drawing),
    )
    assert result.exit_code != 0 and "LookupError" in result.json["description"]
    assert ("No annotation type" if kind == "unknown" else "MIME type") in error_text(
        result
    )
    assert not (directory / "annotation").exists()


@pytest.mark.parametrize("kind", ["outside", "missing", "plain-container"])
def test_project_guard_refuses_invalid_locations(tmp_path, kind):
    directory, drawing = project(tmp_path)
    if kind == "outside":
        drawing = tmp_path / "outside.dxf"
        drawing.touch()
    if kind == "missing":
        drawing = tmp_path / "missing" / "drawing.dxf"
    if kind == "plain-container":
        directory = tmp_path / "plain"
        directory.mkdir()
        from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
            main,
        )

        assert main(container_path=str(directory), root_path=str(tmp_path)) == 0
        drawing = directory / "plain.dxf"
        drawing.touch()
    result = run(directory, "annotation", "--type", "note", "--point", str(drawing))
    assert result.exit_code != 0
    assert (
        "not an InfoBIM project"
        if kind == "plain-container"
        else "not inside any container"
    ) in error_text(result)
    assert not (directory / "annotation").exists()


def test_ambiguous_external_catalog_reports_both_types(tmp_path):
    directory, drawing = project(tmp_path)
    graph = Graph().parse(str(resources.ontology_path_for_iri(Type.ONTOLOGY_IRI)))
    types = sorted(graph.subjects(RDFS.subClassOf, Type.ANNOTATION_CLASS), key=str)
    for subject in types[:2]:
        graph.add((subject, RDFS.label, Literal("ambiguous-test")))
    catalog = tmp_path / "external-catalog"
    relative = Type.ONTOLOGY_IRI.removeprefix(resources.ONTOLOGY_BASE_IRI)
    file = catalog / relative
    file.parent.mkdir(parents=True)
    graph.serialize(file, format="turtle")
    result = run(
        directory,
        "annotation",
        "--type",
        "ambiguous-test",
        "--point",
        str(drawing),
        catalog=catalog,
    )
    assert result.exit_code != 0
    assert "more than one annotation type" in error_text(result)
    for subject in types[:2]:
        assert str(subject) in error_text(result)
    assert not (directory / "annotation").exists()


def test_resaving_command_created_global_id_replaces_csv_row(tmp_path):
    """The CLI allocates IDs; reuse through the public model persistence API."""
    import os
    import subprocess
    import sys

    directory, drawing = project(tmp_path)
    result = run(directory, "annotation", "--type", "note", "--point", str(drawing))
    assert result.exit_code == 0, result.stdout + result.stderr
    source, original = records(directory)
    script = """
import sys
from ontobdc.cli.adapter.context import IsolatedCliContextAdapter
from ontobdc.annotation.domain.model.annotation import Annotation
from infobim.annotation.adapter.csv_repository import AnnotationCsvRepository
context = IsolatedCliContextAdapter([],root_dir=sys.argv[1])
context.set_parameter_value("entity_repository",AnnotationCsvRepository())
model = Annotation(global_id=sys.argv[3],annotation_type="note",title="Updated",points=[dict(x=1.5,y=2),dict(x=3,y=4)],source_document=sys.argv[4])
model.save(context,sys.argv[2])
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(tmp_path),
            str(directory),
            original[0]["global_id"],
            original[0]["source_document"],
        ],
        cwd=directory,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    same_source, updated = records(directory)
    assert same_source == source and len(updated) == 1
    assert updated[0]["global_id"] == original[0]["global_id"]
    assert updated[0]["title"] == "Updated" and updated[0]["text"] == ""
    assert updated[0]["source_document"] == original[0]["source_document"]


def test_blank_title_disables_ok_in_real_command_form(tmp_path):
    directory, drawing = project(tmp_path)
    result = run(
        directory,
        "annotation",
        "--type",
        "note",
        "--point",
        str(drawing),
        mode="blank-title",
    )
    assert "ANNOTATION_TEST_BLANK_TITLE_ENABLED=False" in result.stderr
    assert result.exit_code != 0
    assert "cancelled" in error_text(result)
    assert not (directory / "annotation").exists()
    assert not list(tmp_path.rglob("__annotations_created__.json"))
