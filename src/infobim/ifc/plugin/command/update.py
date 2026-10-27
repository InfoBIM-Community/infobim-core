from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.command import entity_update as ontobdc_entity_update

from infobim.ifc.adapter.element import IfcElementEntity
from infobim.project.adapter.contract import ProjectGuard


class IfcUpdateCommand(CliCommandPort):
    """
    Change the fields of one IFC element of a project, by its GlobalId.

    The values come from ``--update`` as they do for an entity of a
    container, and the fields that can be changed are the ones the facade of
    IfcElement declares editable. The IFC model that holds the element is
    written back to its file.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_update",
        logical_component="ifc",
        description="Change the fields of an IFC element of an InfoBIM project by its GlobalId.",
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
                "description": "The GlobalId of the IFC element to change.",
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
                "accepts": ["--update"],
                "valued": True,
                "parameter": "ifc_update_source",
                "description": (
                    "The values to write: a path to a .json or .csv file, a "
                    "JSON object, or key=value assignments separated by commas."
                ),
                "type": "str",
                "usage": (
                    "infobim ifc --guid <element-global-id> --update <source> "
                    "[--global-id <project-global-id>] [--ifc-model-path <model.ifc>]"
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    UPDATE_FLAG: ClassVar[str] = "--update"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    GUID_FLAG: ClassVar[str] = "--guid"
    MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    PROJECT_PATH_KEY: ClassVar[str] = "container_path"
    GUID_KEY: ClassVar[str] = "ifc_element_guid"
    MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    SOURCE_KEY: ClassVar[str] = "ifc_update_source"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the IFC element update at the CLI routing stage.
        """
        if not args or args[0] != IfcUpdateCommand.COMPONENT:
            return False

        return IfcUpdateCommand._matches(args[1:])

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
        Change the element in the model and write the model back.

        Raises:
            LookupError: no model holds an IfcElement with the GlobalId.
            ValueError: a field cannot be changed, or takes a structure.
        """
        context: Any = self._request.context
        project_path: Path = Path(str(context.get_parameter_value(self.PROJECT_PATH_KEY))).expanduser().resolve()
        guid: str = str(context.get_parameter_value(self.GUID_KEY))
        requested: Any = context.get_parameter_value(self.MODEL_PATH_KEY)
        model_path: Optional[Path] = Path(requested) if isinstance(requested, str) and requested.strip() else None
        changes: Dict[str, Any] = ontobdc_entity_update.ContainerEntityUpdateCommand.parse(
            str(context.get_parameter_value(self.SOURCE_KEY))
        )

        changed: Optional[List[str]] = IfcElementEntity.update(project_path, guid, changes, model_path)
        if changed is None:
            where: str = f"the model {model_path}" if model_path else "the models of the project"
            raise LookupError(f"No entity has the GlobalId {guid} in {where}.")

        return CommandResponse(
            title="Entity Updated",
            description=f"Changed {', '.join(changed) or 'nothing'} of the IFC element {guid}.",
            content={"global_id": guid, "changed": changed},
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid and --update, and
        optionally --global-id and --ifc-model-path, each with a value, in
        any order and none repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        required: List[str] = [IfcUpdateCommand.GUID_FLAG, IfcUpdateCommand.UPDATE_FLAG]
        allowed: List[str] = required + [IfcUpdateCommand.SELECTOR_FLAG, IfcUpdateCommand.MODEL_PATH_FLAG]
        if len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
            return False
        if any(flag not in flags for flag in required):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
