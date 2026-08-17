from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.element.adapter.parameter import ElementParameterRepository
from infobim.element.plugin.command import support


class ElementParametersUnsetAllCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="element_parameters_unset_all",
        logical_component="element",
        description="Unset every writable parameter on an Element instance.",
        arguments=[
            support.argument(
                ["--project"],
                valued=True,
                description="Select the Project through ProjectIdStrategy.",
            ),
            support.argument(
                ["--global-id"],
                valued=True,
                description="Select the Element instance by GlobalId.",
            ),
            support.argument(
                ["--all"], valued=False, description="Select every writable parameter."
            ),
            support.argument(
                ["--unset"], valued=False, description="Clear the selected values."
            ),
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    @staticmethod
    def accepts(args: list[str]) -> bool:
        return len(args) == 7 and ElementParametersUnsetAllCommand._shape(args[1:])

    @staticmethod
    def _shape(args: list[str]) -> bool:
        return (
            len(args) == 6
            and args[0] == "--project"
            and bool(str(args[1]).strip())
            and args[2] == "--global-id"
            and bool(str(args[3]).strip())
            and args[4:] == ["--all", "--unset"]
        )

    def check(self) -> bool:
        args = list(self._request.command_args)
        if not self._shape(args):
            return False
        support.bind_context(self._request, args)
        return True

    def run(self) -> CommandResponse:
        try:
            mutations = ElementParameterRepository(
                support.value(self._request, "project_path")
            ).unset_all(support.value(self._request, "global_id"))
        except ValueError as error:
            raise CliCommandArgumentException(str(error)) from error
        return CommandResponse(
            title="Element Parameters Unset",
            description="Cleared every writable parameter on the Element instance.",
            content={
                "project_id": support.value(self._request, "project_id"),
                "mutation_count": len(mutations),
                "mutations": [mutation.to_dict() for mutation in mutations],
            },
        )
