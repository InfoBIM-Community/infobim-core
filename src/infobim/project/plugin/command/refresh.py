from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Type, Union

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.container.plugin.machine.container_refresh.port import (
    ContainerRefreshStateTransitionHandlerPort,
)
from ontobdc.container.plugin.machine.container_refresh.machine import (
    ContainerRefreshStateTransitionHandler,
)

from infobim.project.adapter.contract import ProjectGuard
from infobim.project.plugin.machine.project_refresh.port import (
    ProjectRefreshStateTransitionHandlerPort,
)
from infobim.project.plugin.machine.project_refresh.machine import (
    ProjectRefreshStateTransitionHandler,
)


class ProjectRefreshCommand(CliCommandPort, LoggerAwarePort):
    """
    Refresh an existing InfoBIM project container by running two stages in
    sequence:

    1. The standard OntoBDC container refresh state machine — the same one
       the command used to proxy to via :class:`ContainerCommandProxy`.
    2. The InfoBIM-specific project refresh state machine, which goes past
       the container-level final state and refreshes the reserved
       ``.__infobim__`` dataset and the IfcProject declaration on top of
       the refreshed container.

    The two handlers are kept as separate objects and run one after the
    other, exactly as the user specified. This preserves the boundary
    between the OntoBDC container contract and the InfoBIM project
    contract rather than mixing them in a single aggregate handler.

    The :class:`ContainerCommandProxy` translation step between
    ``--global-id`` and ``--container`` is performed inline rather than
    via inheritance, so the command can wrap two handlers instead of one.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_refresh",
        logical_component="project",
        description="Refresh an existing InfoBIM Project container.",
        arguments=[
            {
                "accepts": [
                    "--global-id",
                ],
                "valued": True,
                "description": (
                    "Select which project to refresh, by the GlobalId "
                    "carried by its IfcProject or by the container "
                    "storage identifier. When omitted, resolve the "
                    "project from the current working directory."
                ),
                "type": "str",
            },
            {
                "accepts": [
                    "--refresh",
                ],
                "valued": False,
                "description": (
                    "Run the project refresh pipeline on the selected "
                    "InfoBIM project. Refreshing rebuilds datasets, "
                    "datapackage and RO-Crate from the files the project "
                    "container actually holds; it never writes values "
                    "into metadata fields (use `project --update <source>` "
                    "instead)."
                ),
            },
        ],
    )

    TARGET: ClassVar[Type[Union[
        ContainerRefreshStateTransitionHandlerPort,
        ProjectRefreshStateTransitionHandlerPort,
    ]]] = ContainerRefreshStateTransitionHandlerPort

    COMPONENT: ClassVar[str] = "project"
    TARGET_COMPONENT: ClassVar[str] = "container"
    REFRESH_FLAG: ClassVar[str] = "--refresh"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    TARGET_SELECTOR_FLAG: ClassVar[str] = "--container"

    @classmethod
    def translate_selector(cls, args: List[str]) -> List[str]:
        """
        Return the arguments under the flag name the container command reads.

        Mirrors :meth:`ContainerCommandProxy.translate_selector`.
        """
        return [
            cls.TARGET_SELECTOR_FLAG if argument == cls.SELECTOR_FLAG else argument
            for argument in args
        ]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != ProjectRefreshCommand.COMPONENT:
            return False

        scoped: List[str] = list(args[1:])

        if ProjectRefreshCommand.REFRESH_FLAG not in scoped:
            return False

        refresh_index: int = scoped.index(ProjectRefreshCommand.REFRESH_FLAG)
        before: List[str] = scoped[:refresh_index]
        after: List[str] = scoped[refresh_index + 1:]
        remaining: List[str] = before + after
        if ProjectRefreshCommand.SELECTOR_FLAG in remaining:
            gid_index: int = remaining.index(ProjectRefreshCommand.SELECTOR_FLAG)
            if gid_index + 1 >= len(remaining):
                return False
            if not bool(str(remaining[gid_index + 1]).strip()):
                return False

            del remaining[gid_index:gid_index + 2]

        return len(remaining) == 0

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Optional[Any] = None

    @property
    def log_strategy(self) -> Optional[Any]:
        return self._log_strategy

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def _resolve_container_path(self) -> str:
        raw_value: Any = self._request.context.get_parameter_value(
            "container_path"
        )
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise CliCommandArgumentException(
                "No target InfoBIM Project container could be resolved. "
                "Either set the current CLI target container or pass the "
                f"project global id with the {self.SELECTOR_FLAG} flag."
            )

        return str(raw_value).strip()

    def _guard_project(self, container_path: str) -> None:
        """
        Refuse a selected container that is not an InfoBIM project.

        Mirrors :meth:`ContainerCommandProxy.guard_project`.
        """
        ProjectGuard.guard(
            Path(container_path).expanduser().resolve(),
            self._request.context.root_path,
        )

    def check(self) -> bool:
        command_args: List[str] = list(self._request.command_args)
        if self.REFRESH_FLAG not in command_args:
            return False

        refresh_index: int = command_args.index(self.REFRESH_FLAG)
        rest: List[str] = command_args[refresh_index + 1:]
        if self.SELECTOR_FLAG in rest:
            gid_index: int = rest.index(self.SELECTOR_FLAG)
            if gid_index + 1 >= len(rest):
                raise CliCommandArgumentException(
                    f"The {self.SELECTOR_FLAG} flag requires a value."
                )
            if not bool(str(rest[gid_index + 1]).strip()):
                raise CliCommandArgumentException(
                    f"The {self.SELECTOR_FLAG} flag value cannot be empty."
                )

            del rest[gid_index:gid_index + 2]

        if rest:
            raise CliCommandArgumentException(
                f"Unexpected extra arguments for the project refresh "
                f"command: {rest}."
            )

        self._request.command_args = self.translate_selector(
            self._request.command_args
        )

        container_path: str = self._resolve_container_path()
        self._guard_project(container_path)
        self._request.context.set_parameter_value(
            "container_path", container_path
        )

        return True

    def _run_container_refresh_stage(self) -> CommandResponse:
        container_handler: ContainerRefreshStateTransitionHandlerPort = (
            ContainerRefreshStateTransitionHandler(
                context=self._request.context,
                logger=self._logger,
            )
        )
        return container_handler.execute()

    def _run_project_refresh_stage(self) -> CommandResponse:
        project_handler: ProjectRefreshStateTransitionHandlerPort = (
            ProjectRefreshStateTransitionHandler(
                context=self._request.context,
                logger=self._logger,
            )
        )
        return project_handler.execute()

    def run(self) -> CommandResponse:
        container_response: CommandResponse = self._run_container_refresh_stage()
        is_container_ok: bool = not isinstance(
            container_response, ExceptionCommandResponse
        )
        if not is_container_ok:
            merged_failure_content: Dict[str, Any] = {
                **(container_response.content or {}),
                "project_refresh_stage_skipped": True,
            }
            if (
                isinstance(container_response.title, str)
                and container_response.title
            ):
                merged_failure_content["container_failure_title"] = (
                    container_response.title
                )
            return ExceptionCommandResponse(
                title="OntoBDC Container Refresh Failed",
                description=(
                    "The OntoBDC container refresh stage could not "
                    "complete, so the InfoBIM project-specific refresh "
                    "stage was not started."
                ),
                content=merged_failure_content,
            )

        project_response: CommandResponse = self._run_project_refresh_stage()
        merged_content: Dict[str, Any] = {}
        merged_content.update(container_response.content or {})
        merged_content.update(project_response.content or {})
        merged_content["container_visited_states"] = (
            container_response.content or {}
        ).get("visited_states", [])
        merged_content["project_visited_states"] = (
            project_response.content or {}
        ).get("visited_states", [])

        return CommandResponse(
            title="InfoBIM Project Refreshed",
            description=(
                "The project container went through the standard OntoBDC "
                "container refresh stage and then through the "
                "InfoBIM-specific project refresh stage on top of the "
                "refreshed container."
            ),
            content=merged_content,
        )
