from infobim.cli.domain.context import InfoBIMCliContext
from infobim.project.plugin.parameter.project import ProjectIdStrategy


def test_project_alias_is_normalized_to_project_id(tmp_path) -> None:
    context = InfoBIMCliContext(
        root_path=str(tmp_path),
        parameters={"project": "project-123"},
    )

    ProjectIdStrategy().execute(context)

    assert context.get_parameter_value("project_id") == "project-123"


def test_project_id_remains_supported(tmp_path) -> None:
    context = InfoBIMCliContext(
        root_path=str(tmp_path),
        parameters={"project_id": "project-456"},
    )

    ProjectIdStrategy().execute(context)

    assert context.get_parameter_value("project_id") == "project-456"


def test_project_alias_takes_precedence_when_both_are_present(tmp_path) -> None:
    context = InfoBIMCliContext(
        root_path=str(tmp_path),
        parameters={
            "project": "canonical-project",
            "project_id": "legacy-project",
        },
    )

    ProjectIdStrategy().execute(context)

    assert context.get_parameter_value("project_id") == "canonical-project"
