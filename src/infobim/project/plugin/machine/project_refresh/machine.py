from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type
from pathlib import Path

import yaml

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.shared.domain.port.capability import CapabilityPort
from infobim.project.plugin.machine.project_refresh.port import (
    ProjectRefreshProcessStatePort,
    ProjectRefreshStateEvaluatorPort,
    ProjectRefreshStateTransitionHandlerPort,
)
from infobim.project.plugin.machine.project_refresh.state import (
    ProjectRefreshProcessState,
)
from infobim.project.plugin.check.is_ifc_models_refreshed.check import (
    main as check_ifc_models_refreshed,
)
from infobim.project.plugin.check.is_ifc_project_refreshed.check import (
    main as check_ifc_project_refreshed,
)
from infobim.project.plugin.check.is_project_dataset_refreshed.check import (
    main as check_project_dataset_refreshed,
)


class ProjectRefreshStateEvaluatorAdapter(ProjectRefreshStateEvaluatorPort):
    """
    Reads the project layer on disk and reports the InfoBIM refresh
    state it is already in.

    This evaluator ONLY knows about the two InfoBIM-specific stages. It
    is deliberately unaware of the container refresh states, so it
    cannot drift from the container contract. The command itself runs
    the container handler FIRST, and only asks this evaluator to run
    AFTER that first stage reports success — which is exactly the
    two-handler composition the user requested.
    """

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ProjectRefreshProcessStatePort:
        project_path: Path = self._project_path(context)
        root_path: Path = Path(context.root_path).expanduser().resolve()
        reached_state: ProjectRefreshProcessStatePort = (
            ProjectRefreshProcessState.UNDEFINED
        )

        if check_project_dataset_refreshed(
            project_path=str(project_path),
            root_path=str(root_path),
        ) != 0:
            return reached_state

        reached_state = ProjectRefreshProcessState.PROJECT_DATASET_REFRESHED

        if check_ifc_models_refreshed(
            project_path=str(project_path),
            container_path=str(project_path),
            root_path=str(root_path),
        ) != 0:
            return reached_state

        reached_state = ProjectRefreshProcessState.IFC_MODELS_REFRESHED

        if check_ifc_project_refreshed(project_path=str(project_path)) != 0:
            return reached_state

        reached_state = ProjectRefreshProcessState.IFC_PROJECT_REFRESHED

        # if check_project_ready_to_render(
        #     project_path=str(project_path),
        #     container_path=str(project_path),
        #     root_path=str(root_path),
        # ) != 0:
        #     return reached_state

        return ProjectRefreshProcessState.PROJECT_READY_TO_RENDER

    @staticmethod
    def _project_path(context: CliContextPort) -> Path:
        project_path_value: Any = context.get_parameter_value("container_path")
        if not isinstance(project_path_value, str) or not project_path_value.strip():
            raise ValueError(
                "The project path is missing from the command context."
            )

        return Path(project_path_value).expanduser().resolve()


class ProjectRefreshStateTransitionHandler(ProjectRefreshStateTransitionHandlerPort):
    """
    Drives the InfoBIM-specific post-container refresh steps.

    Each target state's capability is resolved by id through the
    CapabilityLoader rather than imported concretely, so this handler
    stays decoupled from any particular implementation of the
    project-dataset refresh step or the IfcProject refresh step.
    """

    _CAPABILITY_IDS: ClassVar[Dict[ProjectRefreshProcessStatePort, str]] = {
        ProjectRefreshProcessState.PROJECT_DATASET_REFRESHED: (
            "org.infobim.project.plugin.capability.transformation."
            "target.project_dataset_refreshed"
        ),
        ProjectRefreshProcessState.IFC_MODELS_REFRESHED: (
            "org.infobim.project.plugin.capability.transformation."
            "target.ifc_models_refreshed"
        ),
        ProjectRefreshProcessState.IFC_PROJECT_REFRESHED: (
            "org.infobim.project.plugin.capability.transformation."
            "target.ifc_project_refreshed"
        ),
        ProjectRefreshProcessState.PROJECT_READY_TO_RENDER: (
            "org.infobim.project.plugin.capability.transformation."
            "target.project_ready_to_render"
        ),
    }
    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim",)

    STATECHART_PACKAGE: ClassVar[str] = (
        "infobim.project.plugin.machine.project_refresh"
    )
    STATECHART_FILE: ClassVar[str] = "standard_project_refresh.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "ProjectRefreshProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._target_path: Path = Path(
            str(context.get_parameter_value("container_path"))
        ).expanduser().resolve()
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: ProjectRefreshStateEvaluatorPort = (
            ProjectRefreshStateEvaluatorAdapter()
        )
        self._active_state: Optional[ProjectRefreshProcessStatePort] = None
        self._observed_state: Optional[ProjectRefreshProcessStatePort] = None

    @property
    def current_state(self) -> ProjectRefreshProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ProjectRefreshProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: ProjectRefreshProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: ProjectRefreshProcessStatePort,
    ) -> None:
        observed_state: ProjectRefreshProcessStatePort = self.observed_state
        if self._state_reaches(observed_state, to_state):
            return

        self._logger.log_info(
            f"InfoBIM project post-container refresh transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability_id: Optional[str] = self._CAPABILITY_IDS.get(to_state)
        if capability_id is None:
            raise ValueError(
                f"InfoBIM project post-container refresh capability id "
                f"not declared for state: {to_state.value}"
            )

        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"InfoBIM project post-container refresh capability not "
                f"found for state: {to_state.value} (id: {capability_id})"
            )

        capability: CapabilityPort = capability_type()
        try:
            CapabilityExecutor.execute(
                capability,
                self._context,
                StrategyParamResolver(ResolverLoader()),
            )
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: ProjectRefreshProcessStatePort,
        to_state: ProjectRefreshProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._state_reaches(self.observed_state, to_state)

    def _state_reaches(
        self,
        observed_state: ProjectRefreshProcessStatePort,
        target_state: ProjectRefreshProcessStatePort,
    ) -> bool:
        statechart_data: Any = yaml.safe_load(
            self._statechart_file_path().read_text(encoding="utf-8")
        )
        if not isinstance(statechart_data, dict):
            raise TypeError("Project refresh statechart must be a mapping.")

        state_sequence: List[str] = StateWorkerAdapter.compute_state_sequence(
            statechart_data
        )
        observed_name: str = observed_state.value.strip("_")
        target_name: str = target_state.value.strip("_")
        if observed_name not in state_sequence:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the "
                "project refresh statechart."
            )
        if target_name not in state_sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the "
                "project refresh statechart."
            )

        return state_sequence.index(observed_name) >= state_sequence.index(target_name)

    def bind_active_state(self, state: ProjectRefreshProcessStatePort) -> None:
        self._active_state = state
        self._forget_observed_state()

    def _forget_observed_state(self) -> None:
        self._observed_state = None

    def _statechart_file_path(self) -> Path:
        return StatechartLocator.locate(
            self.STATECHART_PACKAGE,
            self.STATECHART_FILE,
        )

    def _final_response(self, visited_states: List[str]) -> CommandResponse:
        if self.current_state != ProjectRefreshProcessState.PROJECT_READY_TO_RENDER:
            return ExceptionCommandResponse(
                title="InfoBIM Project Refresh Did Not Complete",
                description=(
                    "The InfoBIM-specific project refresh stages could "
                    "not reach the final PROJECT_READY_TO_RENDER state."
                ),
                content={
                    "path": str(self._target_path),
                    "current_state": self.current_state.value,
                    "visited_states": visited_states,
                },
            )

        return CommandResponse(
            title="InfoBIM Project Layer Refreshed",
            description=(
                "The InfoBIM reserved dataset and the project's "
                "IfcProject declaration are refreshed against the "
                "freshly-refreshed project container."
            ),
            content={
                "path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
                "exists": self._target_path.exists(),
            },
        )

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ProjectRefreshProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._statechart_file_path(),
        )
        visited_states: List[str] = worker.work()

        return self._final_response(visited_states)
