from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort


class ProjectIdStrategy(ParameterPort, CliContextStrategyPort):
    """Normalize project command aliases to the canonical project identifier."""

    METADATA = ParameterMetadata(
        id="org.infobim.domain.project.parameter.project",
        version="0.2.0",
        name="project",
        description="Resolve --project and --project-id to the project identifier.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        raw_project: object = context.get_parameter_value("project")
        if raw_project is None:
            raw_project = context.get_parameter_value("project_id")

        project_id: str = str(raw_project or "").strip()
        if project_id:
            context.set_parameter_value("project_id", project_id)

        return context
