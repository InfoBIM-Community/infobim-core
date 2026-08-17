from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.element.adapter.parameter import ElementParameterRepository
from infobim.element.plugin.command import support


class ElementParameterSetAllCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="element_parameter_set_all",
        logical_component="element",
        description="Set one parameter on every occurrence of an Element instance.",
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
                ["--set"], valued=True, description="Set the parameter value."
            ),
            support.argument(
                ["--all"],
                valued=False,
                description="Apply to every occurrence of the Element.",
            ),
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    @staticmethod
    def accepts(args: list[str]) -> bool:
        return len(args) == 10 and ElementParameterSetAllCommand._shape(args[1:])

    @staticmethod
    def _shape(args: list[str]) -> bool:
        return (
            len(args) == 9
            and args[0] == "--project"
            and bool(str(args[1]).strip())
            and args[2] == "--global-id"
            and bool(str(args[3]).strip())
            and args[4] == "--parameter"
            and bool(str(args[5]).strip())
            and args[6] == "--set"
            and bool(str(args[7]).strip())
            and args[8] == "--all"
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
            ).set(
                support.value(self._request, "global_id"),
                support.value(self._request, "parameter_uri"),
                support.value(self._request, "set_value"),
                all_occurrences=True,
            )
        except ValueError as error:
            raise CliCommandArgumentException(str(error)) from error
        return CommandResponse(
            title="Element Parameter Set Everywhere",
            description="Updated the parameter on every occurrence of the Element.",
            content={
                "project_id": support.value(self._request, "project_id"),
                "mutation_count": len(mutations),
                "mutations": [mutation.to_dict() for mutation in mutations],
            },
        )
