from typing import Any, ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.annotation.plugin.command import export as ontobdc_export

from infobim.annotation.adapter.csv_repository import AnnotationCsvRepository
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
        id="annotation_export",
        logical_component="annotation",
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
            {
                "accepts": ["--export"],
                "valued": True,
                "parameter": "export_format",
                "description": "Format of the export. The only one is: excel.",
                "type": "str",
                "usage": (
                    "infobim annotation --export excel --type <type> [--output <file>] "
                    "[--language <tag>] [--global-id <project-global-id>]"
                ),
            },
            {
                "accepts": ["--type"],
                "valued": True,
                "parameter": "annotation_type",
                "description": "Annotation type whose annotations are exported.",
                "type": "str",
            },
            {
                "accepts": ["--output"],
                "valued": True,
                "parameter": "export_output_path",
                "description": "Where to write the file.",
                "type": "Path",
            },
            {
                "accepts": ["--language"],
                "valued": True,
                "parameter": "export_language",
                "description": "Language of the words in the file (en, pt-br, es-es).",
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "annotation"
    TARGET_COMPONENT: ClassVar[str] = "annotation"
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
