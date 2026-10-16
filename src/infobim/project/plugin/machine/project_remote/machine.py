from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort

from ontobdc.container.domain.model.remote import RemoteContainerUrl
from ontobdc.container.plugin.machine.container_remote.machine import (
    RemoteContainerStateEvaluatorAdapter,
)
from ontobdc.container.plugin.machine.container_remote.port import (
    RemoteContainerProcessStatePort,
    RemoteContainerStateEvaluatorPort,
)

from infobim.project.plugin.machine.project_remote.port import (
    ProjectRemoteProcessStatePort,
    ProjectRemoteStateEvaluatorPort,
)
from infobim.project.plugin.machine.project_remote.state import ProjectRemoteProcessState
from infobim.project.plugin.machine.project_remote.statechart import ProjectRemoteStatechart


def _load_state_capability(
    loader: CapabilityLoader,
    state: ProjectRemoteProcessStatePort,
) -> CapabilityPort:
    capability_id: str = ProjectRemoteStatechart.capability_id(state)
    capability_type: Any = loader.get(capability_id)
    if capability_type is None:
        raise ValueError(f"InfoBIM project remote capability not found: {capability_id}")

    return capability_type()


class ProjectRemoteStateEvaluatorAdapter(ProjectRemoteStateEvaluatorPort):
    """
    Reads the remote connection on disk and reports the state it is already in.

    The OntoBDC remote container connection's own evaluation runs first and
    unchanged; the InfoBIM states continue from where it stopped. The two
    enums share their values, which is what lets the container's answer be
    read as a project state.
    """

    def __init__(self) -> None:
        self._container_evaluator: RemoteContainerStateEvaluatorPort = (
            RemoteContainerStateEvaluatorAdapter()
        )

    def evaluate(self, context: CliContextPort) -> ProjectRemoteProcessStatePort:
        container_state: RemoteContainerProcessStatePort = (
            self._container_evaluator.evaluate(context)
        )
        reached_state: ProjectRemoteProcessStatePort = ProjectRemoteProcessState(
            container_state.value
        )
        if reached_state != ProjectRemoteProcessState.CONTAINER_REFRESHED:
            return reached_state

        # Nothing past the container connection is a cheaply re-checkable
        # fact either: project_set replaces a file from the network, and
        # project_refreshed is itself a nested machine run. Both are always
        # re-verified rather than trusted from a past run.
        return reached_state


class ProjectRemoteStateTransitionHandler:
    """
    Drives an OntoBDC remote container connection all the way to being an
    InfoBIM project.

    The container states are reached by the container's own capabilities,
    named here rather than rewritten, and the project states by InfoBIM's.
    Each target state's capability is resolved by id through
    CapabilityLoader, scanning both root packages, never by importing a
    concrete capability class.
    """

    STATE_CONTEXT_NAME: ClassVar[str] = "ProjectRemoteProcessStatePort"
    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("ontobdc", "infobim")

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._capability_loader: CapabilityLoader = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        )
        self._state_evaluator: ProjectRemoteStateEvaluatorPort = (
            ProjectRemoteStateEvaluatorAdapter()
        )
        self._active_state: Optional[ProjectRemoteProcessStatePort] = None
        self._observed_state: Optional[ProjectRemoteProcessStatePort] = None
        self._last_performed_state: Optional[ProjectRemoteProcessStatePort] = None

    @property
    def current_state(self) -> ProjectRemoteProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ProjectRemoteProcessStatePort:
        """
        The state the connection is in on disk, read again after every capability.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: ProjectRemoteProcessStatePort) -> bool:
        if self.current_state == ProjectRemoteProcessState.REMOTE_CONTAINER_REACHABLE:
            return to_state == self._expected_storage_root_state()

        return self.current_state != to_state

    def _expected_storage_root_state(self) -> ProjectRemoteProcessStatePort:
        """
        Which of the two storage root branches applies right now.

        A real storage root is used when one is found; otherwise a
        temporary one is initialized so the connection can still complete.
        """
        capability: CapabilityPort = _load_state_capability(
            self._capability_loader,
            ProjectRemoteProcessState.STORAGE_ROOT_RECOVERED,
        )
        is_satisfied: Any = getattr(capability, "is_satisfied", None)
        if callable(is_satisfied) and is_satisfied(self._context):
            return ProjectRemoteProcessState.STORAGE_ROOT_RECOVERED

        return ProjectRemoteProcessState.TEMP_STORAGE_ROOT_INITIALIZED

    def perform_state_transition(self, to_state: ProjectRemoteProcessStatePort) -> None:
        if (
            not ProjectRemoteStatechart.is_terminal(to_state)
            and self.observed_state == to_state
        ):
            return

        self._logger.log_info(
            f"InfoBIM project remote transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability: CapabilityPort = _load_state_capability(self._capability_loader, to_state)
        try:
            CapabilityExecutor.execute(capability, self._context)
            self._last_performed_state = to_state
        finally:
            self._observed_state = None

    def validate_state_transition(
        self,
        from_state: ProjectRemoteProcessStatePort,
        to_state: ProjectRemoteProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        if to_state in (
            ProjectRemoteProcessState.STORAGE_ROOT_RECOVERED,
            ProjectRemoteProcessState.TEMP_STORAGE_ROOT_INITIALIZED,
            ProjectRemoteProcessState.CONTAINER_CREATED,
            ProjectRemoteProcessState.CONTAINER_FILES_DOWNLOADED,
            ProjectRemoteProcessState.CONTAINER_REFRESHED,
            ProjectRemoteProcessState.PROJECT_SET,
        ):
            # None of these is ever observable from disk: reachability,
            # right before all of them, has no persisted fact of its own
            # and is always re-verified, so the evaluator can never walk
            # past it. Success here can only be confirmed by having just
            # performed it.
            return self._last_performed_state == to_state

        if ProjectRemoteStatechart.is_terminal(to_state):
            return self._last_performed_state == to_state

        sequence: List[str] = ProjectRemoteStatechart.sequence()
        observed_name: str = self.observed_state.value.strip("_")
        target_name: str = to_state.value.strip("_")
        if observed_name not in sequence:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the "
                "InfoBIM project remote statechart."
            )
        if target_name not in sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the InfoBIM "
                "project remote statechart."
            )

        return sequence.index(observed_name) >= sequence.index(target_name)

    def bind_active_state(self, state: ProjectRemoteProcessStatePort) -> None:
        self._active_state = state
        self._observed_state = None

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ProjectRemoteProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=ProjectRemoteStatechart.path(),
        )
        try:
            visited_states: List[str] = worker.work()
        except CodeEvaluationError as error:
            cause: Optional[BaseException] = error.__cause__
            if isinstance(cause, Exception):
                raise cause from None
            raise

        url: str = str(self._context.get_parameter_value("remote_url")).strip()
        destination: Path = RemoteContainerUrl.destination(
            url, self._context.get_parameter_value("remote_download_dir")
        )
        content: Dict[str, Any] = {
            "url": url,
            "path": str(destination),
            "current_state": self.current_state.value,
            "visited_states": visited_states,
        }
        self._logger.log_notice("InfoBIM project remote connection finished successfully.")

        return CommandResponse(
            title="InfoBIM Project Remote",
            description=(
                "The remote InfoBIM project was downloaded, created and "
                "refreshed locally."
            ),
            content=content,
        )
