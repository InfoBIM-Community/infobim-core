from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.container.plugin.machine.container_create.machine import (
    ContainerCreateStateEvaluatorAdapter,
)
from ontobdc.container.plugin.machine.container_create.port import (
    ContainerCreateProcessStatePort,
    ContainerCreateStateEvaluatorPort,
)

from infobim.project.plugin.machine.project_create.state import ProjectCreateProcessState
from infobim.project.plugin.machine.project_create.port import (
    ProjectCreateProcessStatePort,
    ProjectCreateStateEvaluatorPort,
)
from infobim.project.plugin.check.is_ifc_project_ready.check import (
    main as check_ifc_project_ready,
)
from infobim.project.plugin.check.is_project_dataset_ready.check import (
    main as check_project_dataset_ready,
)


class ProjectCreateStateEvaluatorAdapter(ProjectCreateStateEvaluatorPort):
    """
    Reads the project on disk and reports the state it is already in.

    A project is a container that carries more, so the container's own
    evaluation runs first and unchanged; the project states continue from
    where it stopped. The two enums share their values, which is what lets
    the container's answer be read as a project state.
    """

    def __init__(self) -> None:
        self._container_evaluator: ContainerCreateStateEvaluatorPort = (
            ContainerCreateStateEvaluatorAdapter()
        )

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ProjectCreateProcessStatePort:
        """
        Return the state the target project directory is already in.
        """
        container_state: ContainerCreateProcessStatePort = (
            self._container_evaluator.evaluate(context)
        )
        reached_state: ProjectCreateProcessStatePort = (
            ProjectCreateProcessState(container_state.value)
        )
        if reached_state != ProjectCreateProcessState.CONTAINER_MANIFEST_SYNCED:
            return reached_state

        project_path: Path = self._project_path(context)
        root_path: Path = Path(context.root_path).expanduser().resolve()

        if check_project_dataset_ready(
            project_path=str(project_path),
            root_path=str(root_path),
        ) != 0:
            return reached_state

        reached_state = ProjectCreateProcessState.PROJECT_DATASET_READY

        if check_ifc_project_ready(project_path=str(project_path)) != 0:
            return reached_state

        return ProjectCreateProcessState.IFC_PROJECT_READY

    @staticmethod
    def _project_path(context: CliContextPort) -> Path:
        project_path_value: Any = context.get_parameter_value("container_path")
        if not isinstance(project_path_value, str) or not project_path_value.strip():
            raise ValueError(
                "The project path is missing from the command context."
            )

        return Path(project_path_value).expanduser().resolve()


class ProjectCreateStateTransitionHandler:
    """
    Drives an OntoBDC container all the way to being an InfoBIM project.

    The container states are reached by the container's own capabilities,
    named here rather than rewritten, and the project states by InfoBIM's.

    Each target state's capability is resolved by id through
    CapabilityLoader, never by importing a concrete capability class:
    that import would tie this machine to one particular implementation
    of the state instead of whichever capability declares that id.
    _CAPABILITY_IDS still has to name each id explicitly rather than
    template it from the state's own value, because the two families of
    states below live under different id prefixes (org.ontobdc.container
    for the states this project machine reuses from the container's own
    creation, org.infobim.project for the ones specific to a project).
    """

    _CAPABILITY_IDS: ClassVar[Dict[ProjectCreateProcessStatePort, str]] = {
        ProjectCreateProcessState.DIRECTORY_READY: (
            "org.ontobdc.container.plugin.capability.transformation."
            "target.directory_ready"
        ),
        ProjectCreateProcessState.CONTAINER_METADATA_READY: (
            "org.ontobdc.container.plugin.capability.transformation."
            "target.container_metadata_ready"
        ),
        ProjectCreateProcessState.CONTAINER_STORAGE_INDEX_READY: (
            "org.ontobdc.container.plugin.capability.transformation."
            "target.container_storage_index_ready"
        ),
        ProjectCreateProcessState.CONTAINER_MANIFEST_SYNCED: (
            "org.ontobdc.container.plugin.capability.transformation."
            "target.container_manifest_synced"
        ),
        ProjectCreateProcessState.PROJECT_DATASET_READY: (
            "org.infobim.project.plugin.capability.transformation."
            "target.project_dataset_ready"
        ),
        ProjectCreateProcessState.IFC_PROJECT_READY: (
            "org.infobim.project.plugin.capability.transformation."
            "target.ifc_project_ready"
        ),
    }
    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("ontobdc", "infobim")

    STATECHART_PACKAGE: ClassVar[str] = "infobim.project.plugin.machine.project_create"
    STATECHART_FILE: ClassVar[str] = "standard_project_create.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "ProjectCreateProcessStatePort"

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
        self._state_evaluator: ProjectCreateStateEvaluatorPort = (
            ProjectCreateStateEvaluatorAdapter()
        )
        self._active_state: Optional[ProjectCreateProcessStatePort] = None
        self._observed_state: Optional[ProjectCreateProcessStatePort] = None

    @property
    def current_state(self) -> ProjectCreateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ProjectCreateProcessStatePort:
        """
        The state the project is in on disk, read once per machine step.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: ProjectCreateProcessStatePort) -> bool:
        active_state: ProjectCreateProcessStatePort = self.current_state
        if active_state == ProjectCreateProcessState.UNDEFINED:
            expected_state: ProjectCreateProcessStatePort = (
                ProjectCreateProcessState.INVALID_PATH
                if self.observed_state == ProjectCreateProcessState.INVALID_PATH
                else ProjectCreateProcessState.DIRECTORY_READY
            )
            return to_state == expected_state

        return active_state != to_state

    def perform_state_transition(
        self,
        to_state: ProjectCreateProcessStatePort,
    ) -> None:
        observed_state: ProjectCreateProcessStatePort = self.observed_state
        if observed_state == to_state:
            return

        self._logger.log_info(
            f"InfoBIM project create transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability_id: Optional[str] = self._CAPABILITY_IDS.get(to_state)
        if capability_id is None:
            raise ValueError(
                f"InfoBIM project create capability id not declared for "
                f"state: {to_state.value}"
            )

        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"InfoBIM project create capability not found for state: "
                f"{to_state.value} (id: {capability_id})"
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
        from_state: ProjectCreateProcessStatePort,
        to_state: ProjectCreateProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self.observed_state == to_state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ProjectCreateProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._statechart_file_path(),
        )
        visited_states: List[str] = worker.work()

        return self._final_response(visited_states)

    def bind_active_state(self, state: ProjectCreateProcessStatePort) -> None:
        self._active_state = state
        self._forget_observed_state()

    def _forget_observed_state(self) -> None:
        """
        Drop the reading, so the next one goes back to disk.
        """
        self._observed_state = None

    def _statechart_file_path(self) -> Path:
        return StatechartLocator.locate(
            self.STATECHART_PACKAGE,
            self.STATECHART_FILE,
        )

    def _final_response(self, visited_states: List[str]) -> CommandResponse:
        if self.current_state == ProjectCreateProcessState.INVALID_PATH:
            return ExceptionCommandResponse(
                title="Invalid InfoBIM Project Path",
                description=(
                    "The target path points to an existing file and cannot "
                    "become a project directory."
                ),
                content={
                    "path": str(self._target_path),
                    "current_state": self.current_state.value,
                    "visited_states": visited_states,
                },
            )

        return CommandResponse(
            title="InfoBIM Project Created",
            description=(
                "The project container, its reserved InfoBIM dataset and its "
                "IfcProject declaration are in place."
            ),
            content={
                "path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
                "exists": self._target_path.exists(),
            },
        )
