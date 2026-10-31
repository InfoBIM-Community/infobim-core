from typing import Any, ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.annotate.plugin.command import export as ontobdc_export

from infobim.annotate.adapter.csv_repository import AnnotationCsvRepository
from infobim.project.adapter.proxy import ContainerCommandProxy


class InfoBimAnnotationExportCommand(ContainerCommandProxy):
    """
    Export the annotations of one type of an InfoBIM project to an Excel
    workbook.

    The command is OntoBDC's own annotation export. What InfoBIM adds is the
    project selector (``--global-id``, or the current directory), the check
    that the container is a project, and the CSV repository that keeps the
    annotations of a project, handed to the command through the context.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate_export",
        logical_component="annotate",
        description="Export the annotations of one type of an InfoBIM project, as an Excel workbook.",
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
            # The arguments of OntoBDC's own export (the format, the type, which of them, where to write, the language),
            # which is what reads them; the container is the project, which is selected above.
            *[
                argument
                for argument in ontobdc_export.AnnotationExportCommand.METADATA.arguments
                if argument["accepts"] != ["--container"]
            ],
        ],
    )

    COMPONENT: ClassVar[str] = "annotate"
    TARGET_COMPONENT: ClassVar[str] = "annotate"
    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_export.AnnotationExportCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation export at the CLI routing stage.
        """
        return InfoBimAnnotationExportCommand.accepts_as_target(
            InfoBimAnnotationExportCommand.TARGET, args
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
