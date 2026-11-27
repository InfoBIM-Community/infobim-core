from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.ifc.adapter.class_description import IfcClassDescription


class IfcDescribeCommand(CliCommandPort):
    """
    Describe an IFC class: its attributes, with their types and the class that declares each one, and the property
    sets and quantity sets that apply to it, with their properties. It reads the IFC schema and the templates of the
    standard, so it needs no project and no model. Reading IFC needs ``ifcopenshell``.
    """

    DEFAULT_SCHEMA: ClassVar[str] = "IFC4"

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_describe",
        logical_component="ifc",
        description="Describe an IFC class: its attributes and the property sets that apply to it.",
        arguments=[
            {
                "accepts": ["--ifc-class"],
                "valued": True,
                "parameter": "ifc_class",
                "description": "The name of the IFC class to describe, such as IfcWall.",
                "type": "str",
            },
            {
                "accepts": ["--schema"],
                "valued": True,
                "parameter": "ifc_schema",
                "description": (
                    "The IFC schema the class is read in: IFC2X3, IFC4 or IFC4X3. "
                    f"When omitted, {DEFAULT_SCHEMA}, the one the ontologies of InfoBIM describe."
                ),
                "type": "str",
            },
            {
                "accepts": ["--describe"],
                "description": "List the attributes of the class and the property sets and quantity sets that apply to it.",
                "usage": "infobim ifc --ifc-class <class name> --describe [--schema <IFC2X3|IFC4|IFC4X3>]",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    DESCRIBE_FLAG: ClassVar[str] = "--describe"
    CLASS_FLAG: ClassVar[str] = "--ifc-class"
    SCHEMA_FLAG: ClassVar[str] = "--schema"
    CLASS_KEY: ClassVar[str] = "ifc_class"
    SCHEMA_KEY: ClassVar[str] = "ifc_schema"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the description of an IFC class at the CLI routing stage.
        """
        if not args or args[0] != IfcDescribeCommand.COMPONENT:
            return False

        return IfcDescribeCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        """
        Read the class in the schema.

        Raises:
            LookupError: the schema or the class is not known.
        """
        context: Any = self._request.context
        ifc_class: str = str(context.get_parameter_value(self.CLASS_KEY))
        requested: Any = context.get_parameter_value(self.SCHEMA_KEY)
        schema: str = requested.strip() if isinstance(requested, str) and requested.strip() else self.DEFAULT_SCHEMA
        description: Dict[str, Any] = IfcClassDescription.read(ifc_class, schema)
        return CommandResponse(
            title="IFC Class",
            description=(
                f"The class {description['ifc_class']} of {description['schema']}: "
                f"{len(description['attributes'])} attribute(s) and {len(description['property_sets'])} property set(s)."
            ),
            content=description,
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --describe, with --ifc-class and a value, and optionally --schema with a
        value, in any order and none repeated.
        """
        remaining: List[str] = list(scoped_args)
        if remaining.count(IfcDescribeCommand.DESCRIBE_FLAG) != 1:
            return False
        remaining.remove(IfcDescribeCommand.DESCRIBE_FLAG)

        if len(remaining) % 2 != 0:
            return False
        flags: List[str] = remaining[0::2]
        values: List[str] = remaining[1::2]
        if len(set(flags)) != len(flags) or IfcDescribeCommand.CLASS_FLAG not in flags:
            return False
        if any(flag not in (IfcDescribeCommand.CLASS_FLAG, IfcDescribeCommand.SCHEMA_FLAG) for flag in flags):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
