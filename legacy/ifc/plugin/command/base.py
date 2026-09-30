from typing import ClassVar, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class IfcBaseCommand(CliCommandPort):
    """
    Answers the bare ``infobim ifc`` component and its help flags.

    Every component in this executable has one, so that typing the
    component alone says what it can do instead of routing nowhere.

    STUB.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_base",
        logical_component="ifc",
        description="Base InfoBIM IFC command handler.",
        depends_on=None,
    )

    COMPONENT: ClassVar[str] = "ifc"
    HELP_FLAGS: ClassVar[List[str]] = ["--help", "-h"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the bare component and its help flags at the routing stage.
        """
        if not args or args[0] != IfcBaseCommand.COMPONENT:
            return False

        return len(args) == 1 or (
            len(args) == 2 and args[1] in IfcBaseCommand.HELP_FLAGS
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        raise NotImplementedError(
            "The IFC component help is not implemented yet."
        )

    def run(self) -> CommandResponse:
        raise NotImplementedError(
            "The IFC component help is not implemented yet."
        )
