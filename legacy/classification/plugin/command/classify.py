from typing import ClassVar, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class ClassifySuggestionsCommand(CliCommandPort):
    """Stub for semantic classification suggestions from project paths."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="classify_suggestions",
        logical_component="classify",
        description="Suggest semantic classifications from project paths.",
        arguments=[
            {
                "accepts": ["--suggestions"],
                "description": (
                    "Suggest semantic classifications from project folder and "
                    "file names."
                ),
                "usage": "infobim classify --suggestions",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "classify"
    SUGGESTIONS_FLAG: ClassVar[str] = "--suggestions"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """Match the classification suggestions invocation."""
        return args == [
            ClassifySuggestionsCommand.COMPONENT,
            ClassifySuggestionsCommand.SUGGESTIONS_FLAG,
        ]

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """Validate the suggestions flag after command routing."""
        return self._request.command_args == [self.SUGGESTIONS_FLAG]

    def run(self) -> CommandResponse:
        """Return the placeholder response until classification is implemented."""
        return CommandResponse(
            title="InfoBIM Classify",
            description="Classification suggestions are not implemented yet.",
            content={"mode": "suggestions"},
        )
