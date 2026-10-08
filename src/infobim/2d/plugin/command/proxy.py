from typing import ClassVar, Dict, List, Optional, Type

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim._2d.adapter.command import TwoDCommandLoader


class TwoDProxyCommand(CliCommandPort, LoggerAwarePort):
    """Delegate the public ``2d`` component to commands under ``infobim._2d``."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="two_d_proxy",
        logical_component="2d",
        description="Delegate 2D commands to the internal infobim._2d package.",
        depends_on=None,
        arguments=[
            {
                "accepts": ["2d"],
                "description": "Delegate every 2D command to infobim._2d.",
                "usage": "infobim 2d [flags/parameters]",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "2d"
    # Declarative link to the loader that resolves this proxy's real,
    # privately-housed commands (the same one used in _resolve_command
    # below) -- lets static tooling such as the doc generator show those
    # real commands in place of this one-line stub, as if they were
    # natively registered under the public "2d" component.
    PROXIED_COMMAND_LOADER: ClassVar[Type[TwoDCommandLoader]] = TwoDCommandLoader

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return bool(args) and args[0] == TwoDProxyCommand.COMPONENT

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Optional[LogStrategyConfig] = None

    @property
    def log_strategy(self) -> Optional[LogStrategyConfig]:
        return self._log_strategy

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        return True

    def run(self) -> CommandResponse:
        raw_args: List[str] = [self.COMPONENT, *self._request.command_args]
        command_class: Type[CliCommandPort] = self._resolve_command(raw_args)
        command_request: CliCommandRequest = CliCommandRequest(
            logical_component=command_class.METADATA.logical_component,
            component_action=command_class.METADATA.id,
            command_args=list(self._request.command_args),
            context=self._request.context,
        )
        command: CliCommandPort = command_class(command_request)

        if self._log_strategy is not None and isinstance(command, LoggerAwarePort):
            command.set_log_strategy(self._log_strategy)

        if not command.check():
            raise CliCommandArgumentException(
                f"Invalid 2D command arguments: {raw_args}",
                command_args=raw_args,
            )

        return command.run()

    def _resolve_command(self, raw_args: List[str]) -> Type[CliCommandPort]:
        candidates: Dict[str, Type[CliCommandPort]] = {}
        command_class: Type[CliCommandPort]
        for command_class in TwoDCommandLoader(self._logger).get_all():
            if command_class.accepts(raw_args):
                candidates[command_class.METADATA.id] = command_class

        if len(candidates) == 1:
            return next(iter(candidates.values()))

        if not candidates:
            raise CliCommandArgumentException(
                f"Invalid 2D command arguments: {raw_args}",
                command_args=raw_args,
            )

        raise CliCommandArgumentException(
            f"Multiple internal 2D commands match: {raw_args}",
            command_args=raw_args,
        )
