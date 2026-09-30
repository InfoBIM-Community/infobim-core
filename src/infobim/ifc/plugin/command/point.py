from typing import Any, ClassVar, Dict, List
from pathlib import Path

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter

from infobim.ifc.adapter.model import IfcProjectModelFile
from infobim.project.adapter.contract import ProjectGuard
from infobim.ifc.plugin.machine.ifc_model_create.machine import (
    IfcModelCreateStateTransitionHandler,
)
from infobim._2d.plugin.machine.element_creation_from_point.machine import (
    ElementCreationFromPointStateTransitionHandler,
)


class IfcElementCreationFromPointCommand(CliCommandPort):
    """
    Create IFC elements of the kind a term names, at points picked on a drawing.

    Selection and binding follow the other project commands: the parameter
    stage binds the project (``--global-id``, or the current directory), the
    term and the drawing; the command checks the project and runs the
    element creation from point machine, which owns everything from the
    term's meaning to the IFC elements.

    The elements go into the model ``--ifc-model-path`` names. Without it,
    they go into the project's own model, named after the slug of its
    IfcProject GlobalId; when that file does not exist yet, the IFC model
    creation machine writes it and declares it in the project first.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_element_creation_from_point",
        logical_component="ifc",
        description=(
            "Create IFC elements of the kind a term names at points picked on "
            "a DXF or DWG drawing."
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
            },
            {
                "accepts": ["--term"],
                "valued": True,
                "parameter": "text",
                "description": "Name of the element kind, in natural language.",
            },
            {
                "accepts": ["--point"],
                "valued": True,
                "parameter": "file_open_path",
                "description": (
                    "DXF or DWG drawing on which the element points are picked."
                ),
                "usage": (
                    'infobim ifc [--global-id <project-global-id>] --term "<term>" '
                    "--point <drawing.dxf|drawing.dwg> [--ifc-model-path <model.ifc>]"
                ),
            },
            {
                "accepts": ["--ifc-model-path"],
                "valued": True,
                "parameter": "ifc_model_path",
                "description": (
                    "IFC model of the project to create the elements in. When "
                    "omitted, the project's own model, named after its "
                    "IfcProject GlobalId, created if it does not exist yet."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    VALUED_FLAGS: ClassVar[List[str]] = ["--term", "--point"]

    GLOBAL_ID_KEY: ClassVar[str] = "global_id"
    TERM_KEY: ClassVar[str] = "text"
    DRAWING_KEY: ClassVar[str] = "file_open_path"
    PROJECT_PATH_KEY: ClassVar[str] = "container_path"
    MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the element creation from point at the CLI routing stage.
        """
        if not args or args[0] != IfcElementCreationFromPointCommand.COMPONENT:
            return False

        return IfcElementCreationFromPointCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if not self._matches(self._request.command_args):
            return False

        project_path: Any = self._request.context.get_parameter_value(
            self.PROJECT_PATH_KEY
        )
        if not isinstance(project_path, str) or not project_path.strip():
            return False

        ProjectGuard.guard(
            Path(project_path).expanduser().resolve(),
            self._request.context.root_path,
        )

        return True

    def run(self) -> CommandResponse:
        """
        Run the element creation from point machine on the prepared context.
        """
        context: Any = self._request.context
        self._bind_model_path(context)
        term: str = RequiredParameter.of(context, self.TERM_KEY)
        drawing: str = RequiredParameter.of(context, self.DRAWING_KEY)
        result: Dict[str, Any] = ElementCreationFromPointStateTransitionHandler(
            context
        ).execute()
        created_count: int = result["created_count"]
        return CommandResponse(
            title="IFC Elements Created",
            description=f"Created {created_count} IFC elements.",
            content={
                "global_id": context.get_parameter_value(self.GLOBAL_ID_KEY),
                "term": term,
                "drawing": drawing,
                "ifc_model_path": result["ifc_model_path"],
                "created_count": created_count,
                "ifc_elements": result["ifc_elements"],
            },
        )

    def _bind_model_path(self, context: Any) -> None:
        """
        Bind the model the elements go into, creating the project's own one
        when no model was named and it does not exist yet.
        """
        if self.MODEL_PATH_FLAG in self._request.command_args:
            supplied: str = RequiredParameter.of(context, self.MODEL_PATH_KEY)
            context.set_parameter_value(
                self.MODEL_PATH_KEY, str(Path(supplied).expanduser().resolve())
            )
            return

        project_path: Path = Path(
            RequiredParameter.of(context, self.PROJECT_PATH_KEY)
        ).expanduser().resolve()
        model_path: Path = IfcProjectModelFile.path_of(project_path)
        context.set_parameter_value(self.MODEL_PATH_KEY, str(model_path))
        if not model_path.exists():
            IfcModelCreateStateTransitionHandler(context).execute()

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --term and --point, each with a
        value, and optionally --global-id and --ifc-model-path with a value,
        in any order.
        """
        flags: List[str] = IfcElementCreationFromPointCommand.VALUED_FLAGS + [
            IfcElementCreationFromPointCommand.SELECTOR_FLAG,
            IfcElementCreationFromPointCommand.MODEL_PATH_FLAG,
        ]
        if len(scoped_args) % 2 != 0:
            return False

        seen: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        if len(set(seen)) != len(seen) or any(flag not in flags for flag in seen):
            return False
        if any(not value.strip() or value.startswith("--") for value in values):
            return False

        return all(
            flag in seen for flag in IfcElementCreationFromPointCommand.VALUED_FLAGS
        )
