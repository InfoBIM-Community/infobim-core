from typing import ClassVar, List, Tuple

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse

from infobim.cli.plugin.command.base import InfoBIMBaseCommand


class InfoBIMWelcomeCommand(InfoBIMBaseCommand):
    """
    Default / no-arguments command shown by ``infobim``.

    Analogue at dispatch level of ontobdc's ``CliBaseCommand``: this is the
    concrete class that owns the empty-argument fallback and the global
    ``--help`` / ``-h`` flags. The shared infrastructure (logger wiring,
    tree rendering helper, InfoBIM package/executable constants) lives in
    the parent :class:`InfoBIMBaseCommand` so other commands can reuse it
    without creating two fallbacks that fight in ``CliCommandRunAdapter``.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="welcome",
        logical_component="cli",
        description="Display the InfoBIM commands and options.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "hello",
                ],
                "description": (
                    "Explicitly render the InfoBIM command tree. Same as "
                    "running the bare `infobim` executable, or invoking "
                    "`infobim --help` / `infobim -h`, but written out as "
                    "a positional subcommand for discoverability."
                ),
            },
        ],
    )

    EXCLUDED_COMMAND_IDS: ClassVar[Tuple[str, ...]] = ("welcome",)

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the bare executable, or an explicit request for the tree.
        """
        if not args:
            return True

        return len(args) == 1 and args[0] in ["--help", "-h"]

    def __init__(self, request: CliCommandRequest) -> None:
        super().__init__(request)

    def run(self) -> HelpCommandResponse:
        """
        List the commands this executable answers to.
        """
        return self._render_help_tree(
            title="InfoBIM Commands",
            description="Available commands and options.",
            excluded_command_ids=self.EXCLUDED_COMMAND_IDS,
        )
