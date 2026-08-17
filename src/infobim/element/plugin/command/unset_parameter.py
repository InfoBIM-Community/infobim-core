from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.element.adapter.parameter import ElementParameterRepository
from infobim.element.plugin.command import support


class ElementParameterUnsetCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="element_parameter_unset",
        logical_component="element",
        description="Unset one semantic parameter on one Element instance.",
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
                ["--parameter"],
                valued=True,
                description="Select the parameter by semantic URI.",
            ),
            support.argument(
                ["--unset"], valued=False, description="Clear the parameter value."
            ),
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    @staticmethod
    def accepts(args: list[str]) -> bool:
        return len(args) == 8 and ElementParameterUnsetCommand._shape(args[1:])

    @staticmethod
    def _shape(args: list[str]) -> bool:
        return (
            len(args) == 7
            and args[0] == "--project"
            and bool(str(args[1]).strip())
            and args[2] == "--global-id"
            and bool(str(args[3]).strip())
            and args[4] == "--parameter"
            and bool(str(args[5]).strip())
            and args[6] == "--unset"
        )

    def check(self) -> bool:
        args = list(self._request.command_args)
        if not self._shape(args):
            return False
        support.bind_context(self._request, args)
        return True

    def run(self) -> CommandResponse:
        try:
            mutation = ElementParameterRepository(
                support.value(self._request, "project_path")
            ).unset(
                support.value(self._request, "global_id"),
                support.value(self._request, "parameter_uri"),
            )
        except ValueError as error:
            raise CliCommandArgumentException(str(error)) from error
        return CommandResponse(
            title="Element Parameter Unset",
            description="Cleared one semantic parameter on one Element instance.",
            content={
                "project_id": support.value(self._request, "project_id"),
                "mutation": mutation.to_dict(),
            },
        )
