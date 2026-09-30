from typing import ClassVar, List, Optional, Tuple

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class IfcMoveCommand(CliCommandPort):
    """Stub for displacing an existing IFC element along one axis."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_move",
        logical_component="ifc",
        description=(
            "Move an existing IFC element along one axis, relative to its "
            "current position."
        ),
        arguments=[
            {
                "accepts": ["--move"],
                "valued": True,
                "parameter": "axis",
                "description": "Axis to move the element along: x, y or z.",
                "usage": (
                    "infobim ifc --move <axis> --by <amount> "
                    "--element <title>"
                ),
            },
            {
                "accepts": ["--by"],
                "valued": True,
                "parameter": "amount",
                "description": "Distance to move along the given axis.",
            },
            {
                "accepts": ["--element"],
                "valued": True,
                "parameter": "element",
                "description": "Title of the element to move.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    FLAG: ClassVar[str] = "--move"
    BY_FLAG: ClassVar[str] = "--by"
    ELEMENT_FLAG: ClassVar[str] = "--element"
    FLAGS: ClassVar[List[str]] = [FLAG, BY_FLAG, ELEMENT_FLAG]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """Match the move invocation at the CLI routing stage."""
        if not args or args[0] != IfcMoveCommand.COMPONENT:
            return False

        return IfcMoveCommand._values(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """Validate the move flags after command routing."""
        return self._values(self._request.command_args) is not None

    def run(self) -> CommandResponse:
        """Return the placeholder response until moving is implemented."""
        values = self._values(self._request.command_args)
        axis, amount, element = values if values is not None else (None, None, None)

        return CommandResponse(
            title="InfoBIM IFC Move",
            description="Moving an element is not implemented yet.",
            content={"axis": axis, "by": amount, "element": element},
        )

    @staticmethod
    def _values(
        scoped_args: List[str],
    ) -> Optional[Tuple[str, str, str]]:
        remaining: List[str] = list(scoped_args)
        axis: Optional[str] = IfcMoveCommand._extract(remaining, IfcMoveCommand.FLAG)
        amount: Optional[str] = IfcMoveCommand._extract(
            remaining, IfcMoveCommand.BY_FLAG
        )
        element: Optional[str] = IfcMoveCommand._extract(
            remaining, IfcMoveCommand.ELEMENT_FLAG
        )
        if axis is None or amount is None or element is None or remaining:
            return None

        return axis, amount, element

    @staticmethod
    def _extract(remaining: List[str], flag: str) -> Optional[str]:
        if flag not in remaining:
            return None

        index: int = remaining.index(flag)
        if index + 1 >= len(remaining):
            return None

        value: str = remaining[index + 1]
        if not value.strip() or value in IfcMoveCommand.FLAGS:
            return None

        del remaining[index:index + 2]
        return value.strip()
