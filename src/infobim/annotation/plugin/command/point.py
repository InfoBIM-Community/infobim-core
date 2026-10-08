from pathlib import Path
from typing import Any, ClassVar, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.annotation.plugin.command import point as ontobdc_point

from infobim.annotation.adapter.csv_repository import AnnotationCsvRepository
from infobim.project.adapter.contract import ProjectGuard


class InfoBimAnnotationCreationFromPointCommand(CliCommandPort):
    """
    Create an annotation at points picked on a DXF drawing of a project.

    The command is OntoBDC's own annotation creation from point. What
    InfoBIM adds is what OntoBDC does not know: the 2D viewer that opens the
    drawing, captures the points and asks for the details (the capabilities
    of ``DxfAnnotationCapabilities``), and the CSV repository that keeps the
    annotations of a project (``AnnotationCsvRepository``). Both are handed
    to the command through the context, and taken back when it ends.

    Like every project command, it refuses a drawing whose container is not
    an InfoBIM project.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotation_creation_from_point",
        logical_component="annotation",
        description=(
            "Create an annotation of a given type at points picked on a DXF "
            "drawing of an InfoBIM project."
        ),
        arguments=ontobdc_point.AnnotationCreationFromPointCommand.METADATA.arguments,
    )

    COMPONENT: ClassVar[str] = "annotation"
    FILE_KEY: ClassVar[str] = "file_open_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation creation from point at the CLI routing stage.
        """
        return ontobdc_point.AnnotationCreationFromPointCommand.accepts(args)

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._target: CliCommandPort = ontobdc_point.AnnotationCreationFromPointCommand(
            request
        )

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if not self._target.check():
            return False

        drawing: Path = Path(
            RequiredParameter.of(self._request.context, self.FILE_KEY)
        ).expanduser().resolve()
        ProjectGuard.guard(
            ContainerDocumentIri.container_of(drawing),
            self._request.context.root_path,
        )

        return True

    def run(self) -> CommandResponse:
        """
        Hand OntoBDC the viewer and the repository, and run its command.
        """
        # Imported here: the 2D viewer needs Qt, which not every place that
        # lists the commands of this module (a browser, say) has.
        from infobim._2d.adapter.annotation_capabilities import (
            DxfAnnotationCapabilities,
        )

        context: Any = self._request.context
        DxfAnnotationCapabilities.apply(context)
        context.set_parameter_value("entity_repository", AnnotationCsvRepository())
        try:
            return self._target.run()
        finally:
            key: str
            for key in [
                *DxfAnnotationCapabilities.CAPABILITIES_BY_KEY,
                "entity_repository",
            ]:
                context.delete_parameter(key)
