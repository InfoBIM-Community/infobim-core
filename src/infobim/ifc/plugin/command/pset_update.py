from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.command import entity_update as ontobdc_entity_update

from infobim.ifc.adapter.element import IfcElementEntity
from infobim.ifc.adapter.element_property_set_update import IfcElementPropertySetUpdate
from infobim.project.adapter.contract import ProjectGuard


class IfcPsetUpdateCommand(CliCommandPort):
    """
    Change the properties of ONE property set, or ONE quantity set, of an IFC element of a project, by its GlobalId.

    The set is named by ``--pset`` and the properties to change come in ``--update`` (a JSON object, or
    ``name=value`` pairs, of the property and its new text; an empty text removes the property). One set is changed by
    each call: an application that changes several runs the command once for each. The model is written back only when
    something changed. Reading and writing IFC needs ``ifcopenshell``.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_pset_update",
        logical_component="ifc",
        description="Change the properties of one property set or quantity set of an IFC element of an InfoBIM project.",
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
                "description": "The GlobalId of the IFC element whose property set is changed.",
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
                "accepts": ["--pset"],
                "valued": True,
                "parameter": "ifc_pset_name",
                "description": "The name of the property set or quantity set to change, such as Pset_WallCommon.",
                "type": "str",
            },
            {
                "accepts": ["--update"],
                "valued": True,
                "parameter": "ifc_pset_update_source",
                "description": "The properties to change: a JSON object, or name=value pairs, of the property and its new text.",
                "type": "str",
                "usage": (
                    "infobim ifc --guid <element-global-id> --pset <set name> --update '<properties as JSON>' "
                    "[--global-id <project-global-id>] [--ifc-model-path <model.ifc>]"
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    GUID_FLAG: ClassVar[str] = "--guid"
    MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    SET_FLAG: ClassVar[str] = "--pset"
    UPDATE_FLAG: ClassVar[str] = "--update"
    PROJECT_PATH_KEY: ClassVar[str] = "container_path"
    GUID_KEY: ClassVar[str] = "ifc_element_guid"
    MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    SET_KEY: ClassVar[str] = "ifc_pset_name"
    SOURCE_KEY: ClassVar[str] = "ifc_pset_update_source"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the change of a property set of an IFC element at the CLI routing stage.
        """
        if not args or args[0] != IfcPsetUpdateCommand.COMPONENT:
            return False

        return IfcPsetUpdateCommand._matches(args[1:])

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
        Change the properties of the set in the model and write the model back, when something changed.

        Raises:
            LookupError: no model holds an IfcElement with the GlobalId.
            ValueError: a property cannot be changed, or its text is not a value of its datatype.
        """
        context: Any = self._request.context
        project_path: Path = Path(str(context.get_parameter_value(self.PROJECT_PATH_KEY))).expanduser().resolve()
        guid: str = str(context.get_parameter_value(self.GUID_KEY))
        set_name: str = str(context.get_parameter_value(self.SET_KEY))
        requested: Any = context.get_parameter_value(self.MODEL_PATH_KEY)
        model_path: Optional[Path] = Path(requested) if isinstance(requested, str) and requested.strip() else None
        parsed: Dict[str, Any] = ontobdc_entity_update.ContainerEntityUpdateCommand.parse(
            str(context.get_parameter_value(self.SOURCE_KEY))
        )
        changes: Dict[str, str] = {}
        for name, value in parsed.items():
            if isinstance(value, (dict, list)):
                raise ValueError(f"The property {name} takes a text, not a structure.")
            changes[name] = "" if value is None else str(value)

        located: Optional[Tuple[Path, Any, Any]] = IfcElementEntity.locate(project_path, guid, model_path)
        if located is None:
            where: str = f"the model {model_path}" if model_path else "the models of the project"
            raise LookupError(f"No entity has the GlobalId {guid} in {where}.")

        path, model, element = located
        changed: List[str] = IfcElementPropertySetUpdate.apply(element, set_name, changes)
        if changed:
            model.write(str(path))

        return CommandResponse(
            title="Property Set Updated",
            description=f"Changed {', '.join(changed) or 'nothing'} of {set_name} of the IFC element {guid}.",
            content={
                "global_id": guid,
                "model": path.relative_to(project_path).as_posix(),
                "property_set": set_name,
                "changed": changed,
            },
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid, --pset and --update, each with a value, and optionally
        --global-id and --ifc-model-path, each with a value, in any order and none repeated.
        """
        remaining: List[str] = list(scoped_args)
        if len(remaining) % 2 != 0:
            return False
        flags: List[str] = remaining[0::2]
        values: List[str] = remaining[1::2]
        required: List[str] = [IfcPsetUpdateCommand.GUID_FLAG, IfcPsetUpdateCommand.SET_FLAG, IfcPsetUpdateCommand.UPDATE_FLAG]
        allowed: List[str] = required + [IfcPsetUpdateCommand.SELECTOR_FLAG, IfcPsetUpdateCommand.MODEL_PATH_FLAG]
        if len(set(flags)) != len(flags) or any(flag not in flags for flag in required):
            return False
        if any(flag not in allowed for flag in flags):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
