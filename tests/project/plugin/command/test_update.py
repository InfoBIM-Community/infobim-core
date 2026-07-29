from infobim.cli.domain.context import InfoBIMCliContext
from infobim.project.plugin.command.update import ProjectUpdateCommand
from ontobdc.cli.domain.request.command import CliCommandRequest


def make_command(tmp_path, monkeypatch) -> ProjectUpdateCommand:
    storage_file = tmp_path / "storage.ttl"
    storage_file.write_text("", encoding="utf-8")
    project_path = tmp_path / "project"
    project_path.mkdir()
    context = InfoBIMCliContext(root_path=str(tmp_path))
    request = CliCommandRequest(
        logical_component="project",
        component_action="update",
        command_args=["--project", "project-123", "--update"],
        context=context,
    )
    command = ProjectUpdateCommand(request)
    monkeypatch.setattr(
        "infobim.project.plugin.command.update.get_storage_file",
        lambda root_path: str(storage_file),
    )
    monkeypatch.setattr(
        ProjectUpdateCommand,
        "_list_projects",
        lambda self, path: [
            {
                "project_id": "project-123",
                "name": "Projeto teste",
                "path": str(project_path),
            }
        ],
    )
    return command


def test_accepts_project_update_aliases() -> None:
    assert ProjectUpdateCommand.accepts(
        ["project", "--project", "project-123", "--update"]
    )
    assert ProjectUpdateCommand.accepts(
        ["project", "--project-id", "project-123", "--update"]
    )


def test_updates_project_with_existing_capability(
    tmp_path,
    monkeypatch,
) -> None:
    command = make_command(tmp_path, monkeypatch)
    calls = []

    def execute(_self, context):
        calls.append(context.get_parameter_value("container_path"))
        return {"crate_file": str(tmp_path / "ro-crate-metadata.json")}

    monkeypatch.setattr(
        "infobim.project.plugin.command.update.UpdatedCapability.execute",
        execute,
    )

    assert command.check()
    response = command.run()

    assert calls == [str(tmp_path / "project")]
    assert response.content["project_id"] == "project-123"
    assert response.content["path"] == str(tmp_path / "project")
    assert response.content["crate_file"].endswith(
        "ro-crate-metadata.json"
    )
