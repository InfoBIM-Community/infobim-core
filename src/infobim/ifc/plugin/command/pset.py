from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.ifc.adapter.element import IfcElementEntity
from infobim.ifc.adapter.element_property_sets import IfcElementPropertySets
from infobim.project.adapter.contract import ProjectGuard


class IfcPsetCommand(CliCommandPort):
    """
    List the property sets of one IFC element of a project, by its GlobalId.

    The models the project's RO-Crate declares are searched for the element,
    and the answer lists its property sets and quantity sets, each with its
    properties, and says the schema of the model. ``--pset`` alone lists them
    all; ``--pset <name>`` lists only the set of that name. The sets are not part of ``infobim ifc --inspect``: an
    application that wants them asks for them with this command, and puts them
    with what the inspection answered. Reading IFC needs ``ifcopenshell``.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_pset",
        logical_component="ifc",
        description="List the property sets of an IFC element of an InfoBIM project by its GlobalId.",
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
                "description": "The GlobalId of the IFC element whose property sets are listed.",
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
                "description": (
                    "List the property sets and quantity sets of the element, with their properties. With the name of "
                    "a set, list only that set."
                ),
                "usage": "infobim ifc --guid <element-global-id> --pset [<set name>] [--global-id <project-global-id>] [--ifc-model-path <model.ifc>]",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    PSET_FLAG: ClassVar[str] = "--pset"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    GUID_FLAG: ClassVar[str] = "--guid"
    PROJECT_PATH_KEY: ClassVar[str] = "container_path"
    MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    GUID_KEY: ClassVar[str] = "ifc_element_guid"
    MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the listing of the property sets of an IFC element at the CLI routing stage.
        """
        if not args or args[0] != IfcPsetCommand.COMPONENT:
            return False

        return IfcPsetCommand._matches(args[1:])

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
        Find the element in the models of the project and list its property sets.

        Raises:
            LookupError: the project's RO-Crate cannot be read, or no model holds an IfcElement with the GlobalId.
        """
        context: Any = self._request.context
        project_path: Path = Path(str(context.get_parameter_value(self.PROJECT_PATH_KEY))).expanduser().resolve()
        guid: str = str(context.get_parameter_value(self.GUID_KEY))
        requested: Any = context.get_parameter_value(self.MODEL_PATH_KEY)
        model_path: Optional[Path] = Path(requested) if isinstance(requested, str) and requested.strip() else None
        located: Optional[Tuple[Path, Any, Any]] = IfcElementEntity.locate(project_path, guid, model_path)
        if located is None:
            where: str = f"the model {model_path}" if model_path else "the models of the project"
            raise LookupError(f"No entity has the GlobalId {guid} in {where}.")

        path, model, element = located
        sets: List[Dict[str, Any]] = IfcElementPropertySets.read(element)
        wanted: Optional[str] = self._set_name(self._request.command_args)
        if wanted is not None:
            sets = [item for item in sets if item["name"] == wanted]
            if not sets:
                raise LookupError(f"The {element.is_a()} {guid} has no property set or quantity set named {wanted}.")
        return CommandResponse(
            title="IFC Element Property Sets",
            description=f"The {element.is_a()} «{element.Name or guid}» has {len(sets)} property set(s) listed.",
            content={"global_id": guid, "model": path.relative_to(project_path).as_posix(), "schema": model.schema, "property_sets": sets},
        )

    @staticmethod
    def _set_name(scoped_args: List[str]) -> Optional[str]:
        """The name of the set the line asks for: the word after --pset, none when --pset has no word."""
        flags: Dict[str, Optional[str]] = IfcPsetCommand._flags(scoped_args) or {}
        return flags.get(IfcPsetCommand.PSET_FLAG)

    @staticmethod
    def _flags(scoped_args: List[str]) -> Optional[Dict[str, Optional[str]]]:
        """
        The flags of the line with their values, none for a --pset with no value, or None when the line is not made of
        --guid with a value, --pset with or without one, and optionally --global-id and --ifc-model-path, each with a value,
        in any order and none repeated.
        """
        allowed: List[str] = [
            IfcPsetCommand.GUID_FLAG,
            IfcPsetCommand.PSET_FLAG,
            IfcPsetCommand.SELECTOR_FLAG,
            IfcPsetCommand.MODEL_PATH_FLAG,
        ]
        flags: Dict[str, Optional[str]] = {}
        index: int = 0
        while index < len(scoped_args):
            flag: str = scoped_args[index]
            value: Optional[str] = scoped_args[index + 1] if index + 1 < len(scoped_args) else None
            has_value: bool = value is not None and bool(value.strip()) and not value.startswith("--")
            if flag not in allowed or flag in flags:
                return None
            if flag != IfcPsetCommand.PSET_FLAG and not has_value:
                return None
            flags[flag] = value if has_value else None
            index += 2 if has_value else 1

        if IfcPsetCommand.GUID_FLAG not in flags or IfcPsetCommand.PSET_FLAG not in flags:
            return None

        return flags

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid with a value and --pset, with a value or none, and optionally
        --global-id and --ifc-model-path, each with a value, in any order and none repeated.
        """
        return IfcPsetCommand._flags(scoped_args) is not None
