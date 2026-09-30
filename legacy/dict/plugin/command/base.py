from typing import ClassVar, List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class DictBaseCommand(CliCommandPort):
    """
    Answers the bare ``infobim dict`` component and its help flags.

    Every component in this executable has one, so that typing the
    component alone says what it can do instead of routing nowhere.

    STUB.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="dict_base",
        logical_component="dict",
        description="Base InfoBIM dictionary command handler.",
        depends_on=None,
    )

    COMPONENT: ClassVar[str] = "dict"
    HELP_FLAGS: ClassVar[List[str]] = ["--help", "-h"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the bare component and its help flags at the routing stage.
        """
        if not args or args[0] != DictBaseCommand.COMPONENT:
            return False

        return len(args) == 1 or (
            len(args) == 2 and args[1] in DictBaseCommand.HELP_FLAGS
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        raise NotImplementedError(
            "The dictionary component help is not implemented yet."
        )

    def run(self) -> CommandResponse:
        raise NotImplementedError(
            "The dictionary component help is not implemented yet."
        )
