from typing import Any, ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.annotation.plugin.command import list as ontobdc_list

from infobim.annotation.adapter.csv_repository import AnnotationCsvRepository
from infobim.project.adapter.proxy import ContainerCommandProxy


class InfoBimAnnotationListCommand(ContainerCommandProxy):
    """
    List the annotations of an InfoBIM project, grouped by annotation type.

    The command is OntoBDC's own annotation list. What InfoBIM adds is the
    project selector (``--global-id``, or the current directory), the check
    that the container is a project, and the CSV repository that keeps the
    annotations of a project, handed to the command through the context.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotation_list",
        logical_component="annotation",
        description=(
            "List the annotations of an InfoBIM project, grouped by the "
            "annotation types the ontology declares."
        ),
        arguments=[
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select the project by the GlobalId carried by its "
                    "IfcProject. When omitted, resolve the project from the "
                    "current working directory."
                ),
                "type": "str",
            },
            {
                "accepts": ["--list"],
                "description": (
                    "List the annotations of the project, grouped by type."
                ),
                "usage": "infobim annotation --list [--global-id <project-global-id>]",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "annotation"
    TARGET_COMPONENT: ClassVar[str] = "annotation"
    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_list.AnnotationListCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation list at the CLI routing stage.
        """
        return InfoBimAnnotationListCommand.accepts_as_target(
            InfoBimAnnotationListCommand.TARGET, args
        )

    def run(self) -> CommandResponse:
        """
        Hand OntoBDC the repository of the annotations, and run its command.
        """
        context: Any = self._request.context
        context.set_parameter_value("entity_repository", AnnotationCsvRepository())
        try:
            return self._target.run()
        finally:
            context.delete_parameter("entity_repository")
