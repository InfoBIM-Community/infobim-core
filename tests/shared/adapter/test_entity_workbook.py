import json

import pytest

from infobim.shared.adapter.entity_workbook import (
    EntityWorkbookAdapter,
    EntityWorkbookField,
)


def test_generates_entity_workbook_and_datapackage(tmp_path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("frictionless")
    adapter = EntityWorkbookAdapter()

    artifact = adapter.generate(
        output_dir=tmp_path / "payload" / "document",
        workbook_name="tasks.xlsx",
        worksheet_name="IfcTask",
        fields=[
            EntityWorkbookField("GlobalId"),
            EntityWorkbookField("Name"),
            EntityWorkbookField("IsMilestone", "boolean"),
            EntityWorkbookField("TaskTime"),
        ],
        records=[
            {
                "GlobalId": "task-1",
                "Name": "Cabeamento lógico",
                "IsMilestone": False,
                "TaskTime": {"ScheduleDuration": "5 dias"},
            }
        ],
        datapackage_path=tmp_path / ".__ontobdc__" / "datapackage.json",
        package_name="schedule_ifc_task",
        resource_name="ifc_task",
        primary_key=["GlobalId"],
    )

    workbook = openpyxl.load_workbook(artifact.workbook_path)
    worksheet = workbook["IfcTask"]

    assert [cell.value for cell in worksheet[1]] == [
        "GlobalId",
        "Name",
        "IsMilestone",
        "TaskTime",
    ]
    assert worksheet["A2"].value == "task-1"
    assert worksheet["B2"].value == "Cabeamento lógico"
    assert worksheet["C2"].value is False
    assert json.loads(worksheet["D2"].value) == {
        "ScheduleDuration": "5 dias"
    }
    assert artifact.generated_row_count == 1
    assert artifact.datapackage_path.is_file()
    assert artifact.validation["valid"] is True


def test_rejects_unknown_primary_key(tmp_path) -> None:
    adapter = EntityWorkbookAdapter()

    with pytest.raises(ValueError, match="Unknown primary key fields"):
        adapter.generate(
            output_dir=tmp_path,
            workbook_name="entity.xlsx",
            worksheet_name="Entity",
            fields=[EntityWorkbookField("Name")],
            records=[],
            datapackage_path=tmp_path / "datapackage.json",
            package_name="entity",
            resource_name="entity",
            primary_key=["Missing"],
        )


def test_preserves_other_datapackage_resources(tmp_path) -> None:
    pytest.importorskip("openpyxl")
    pytest.importorskip("frictionless")
    datapackage_path = tmp_path / ".__ontobdc__" / "datapackage.json"
    datapackage_path.parent.mkdir(parents=True)
    datapackage_path.write_text(
        json.dumps(
            {
                "name": "existing_project",
                "resources": [
                    {
                        "name": "existing_resource",
                        "path": "../payload/document/existing.csv",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    EntityWorkbookAdapter().generate(
        output_dir=tmp_path / "payload" / "document",
        workbook_name="entity.xlsx",
        worksheet_name="Entity",
        fields=[EntityWorkbookField("GlobalId")],
        records=[{"GlobalId": "entity-1"}],
        datapackage_path=datapackage_path,
        package_name="replacement_name",
        resource_name="entity",
        primary_key=["GlobalId"],
    )

    descriptor = json.loads(datapackage_path.read_text(encoding="utf-8"))
    assert descriptor["name"] == "existing_project"
    assert [
        resource["name"]
        for resource in descriptor["resources"]
    ] == ["existing_resource", "entity"]
