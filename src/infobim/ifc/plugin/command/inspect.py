from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.ifc.adapter.element import IfcElementEntity
from infobim.project.adapter.contract import ProjectGuard


class IfcInspectCommand(CliCommandPort):
    """
    Inspect one IFC element of a project, by its GlobalId.

    The models the project's RO-Crate declares are searched for the element,
    and the answer has the shape of the listing of the entities of a
    container, with the one model that holds the element and only that element
    in it. Reading IFC needs ``ifcopenshell``.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_inspect",
        logical_component="ifc",
        description="Inspect an IFC element of an InfoBIM project by its GlobalId.",
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
                "accepts": ["--guid"],
                "valued": True,
                "parameter": "ifc_element_guid",
                "description": "The GlobalId of the IFC element to inspect.",
                "type": "str",
            },
            {
                "accepts": ["--ifc-model-path"],
                "valued": True,
                "parameter": "ifc_model_path",
                "description": (
                    "The IFC model that holds the element, by its path or "
                    "relative to the project. When omitted, every IFC model "
                    "the project declares is searched."
                ),
                "type": "Path",
            },
            {
                "accepts": ["--inspect"],
                "description": "Read the element: its class, its attributes and the model that holds it.",
                "usage": "infobim ifc --guid <element-global-id> --inspect [--global-id <project-global-id>] [--ifc-model-path <model.ifc>]",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    INSPECT_FLAG: ClassVar[str] = "--inspect"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    GUID_FLAG: ClassVar[str] = "--guid"
    PROJECT_PATH_KEY: ClassVar[str] = "container_path"
    MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    GUID_KEY: ClassVar[str] = "ifc_element_guid"
    MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the IFC element inspection at the CLI routing stage.
        """
        if not args or args[0] != IfcInspectCommand.COMPONENT:
            return False

        return IfcInspectCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if not self._matches(self._request.command_args):
            return False

        project_path: Any = self._request.context.get_parameter_value(self.PROJECT_PATH_KEY)
        if not isinstance(project_path, str) or not project_path.strip():
            return False

        ProjectGuard.guard(
            Path(project_path).expanduser().resolve(),
            self._request.context.root_path,
        )

        return True

    def run(self) -> CommandResponse:
        """
        Find the element in the models of the project and answer it.

        Raises:
            LookupError: the project's RO-Crate cannot be read, or no model holds an IfcElement with the GlobalId.
        """
        context: Any = self._request.context
        project_path: Path = Path(str(context.get_parameter_value(self.PROJECT_PATH_KEY))).expanduser().resolve()
        guid: str = str(context.get_parameter_value(self.GUID_KEY))
        requested: Any = context.get_parameter_value(self.MODEL_PATH_KEY)
        model_path: Optional[Path] = Path(requested) if isinstance(requested, str) and requested.strip() else None
        dataset: Optional[Dict[str, Any]] = IfcElementEntity.find(project_path, guid, model_path)
        if dataset is None:
            where: str = f"the model {model_path}" if model_path else "the models of the project"
            raise LookupError(f"No entity has the GlobalId {guid} in {where}.")

        element: Dict[str, Any] = dataset["entities"][0]
        ifc_class: str = next(field["values"][0] for field in element["fields"] if field["name"] == "ifc_class")
        return CommandResponse(
            title="Container Entity",
            description=f"The {ifc_class} «{element['name'] or guid}» of the model {dataset['title']}.",
            content={"datasets": [dataset]},
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --inspect, with --guid and a
        value, and optionally --global-id and --ifc-model-path, each with a value, in any order and none
        repeated.
        """
        remaining: List[str] = list(scoped_args)
        if remaining.count(IfcInspectCommand.INSPECT_FLAG) != 1:
            return False
        remaining.remove(IfcInspectCommand.INSPECT_FLAG)

        if len(remaining) % 2 != 0:
            return False
        flags: List[str] = remaining[0::2]
        values: List[str] = remaining[1::2]
        if len(set(flags)) != len(flags) or IfcInspectCommand.GUID_FLAG not in flags:
            return False
        if any(flag not in (IfcInspectCommand.SELECTOR_FLAG, IfcInspectCommand.GUID_FLAG, IfcInspectCommand.MODEL_PATH_FLAG) for flag in flags):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
