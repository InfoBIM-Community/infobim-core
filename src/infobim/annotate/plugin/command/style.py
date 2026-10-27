from typing import Any, ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.annotate.plugin.command import style as ontobdc_style

from infobim.annotate.adapter.csv_repository import AnnotationCsvRepository
from infobim.project.adapter.proxy import ContainerCommandProxy


class InfoBimAnnotationStyleGeometryCommand(ContainerCommandProxy):
    """
    Change how a geometry of an annotation of an InfoBIM project is drawn.

    The command is OntoBDC's own annotation style of a geometry. What InfoBIM adds is
    the project selector (``--global-id``, or the current directory), the
    check that the container is a project, and the CSV repository that keeps
    the annotations of a project, handed to the command through the context
    and taken back when it ends.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate_style_geometry",
        logical_component="annotate",
        description="Change how a geometry of an annotation of an InfoBIM project is drawn.",
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
            *[
                argument
                for argument in ontobdc_style.AnnotationStyleGeometryCommand.METADATA.arguments
                if argument["accepts"] != ["--container"]
            ],
        ],
    )

    COMPONENT: ClassVar[str] = "annotate"
    TARGET_COMPONENT: ClassVar[str] = "annotate"
    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_style.AnnotationStyleGeometryCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation style of a geometry at the CLI routing stage.
        """
        return InfoBimAnnotationStyleGeometryCommand.accepts_as_target(
            InfoBimAnnotationStyleGeometryCommand.TARGET, args
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
