from pathlib import Path
from typing import Dict, List, Optional, Type

from infobim.project.adapter.render import ProjectCreateResponseRenderer
from infobim.project.domain.machine.state import ProjectCreateProcessState
from infobim.project.plugin.capability.transformation.ifc_project_facade_ready import IfcProjectFacadeReadyCapability
from infobim.project.plugin.capability.transformation.ifc_project_ready import IfcProjectReadyCapability
from infobim.project.plugin.capability.transformation.ontobdc_container_ready import OntoBDCContainerReadyCapability
from infobim.project.plugin.capability.transformation.project_dataset_ready import ProjectDatasetReadyCapability
from infobim.project.plugin.capability.transformation.project_ready import ProjectReadyCapability
from infobim.project.plugin.check.is_ifc_project_facade_ready import evaluate as is_facade_ready
from infobim.project.plugin.check.is_ifc_project_ready import evaluate as is_ifc_project_ready
from infobim.project.plugin.check.is_ontobdc_container_ready import evaluate as is_container_ready
from infobim.project.plugin.check.is_project_dataset_ready import evaluate as is_dataset_ready
from infobim.project.plugin.check.is_project_ready import evaluate as is_project_ready
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort


class ProjectCreateStateEvaluatorAdapter:
    @property
    def process_state_class(self) -> Type[ProjectCreateProcessState]:
        return ProjectCreateProcessState

    def evaluate(self, context: CliContextPort) -> ProjectCreateProcessState:
        target_path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve()
        root_path = str(context.root_path)

        if target_path.exists() and not target_path.is_dir():
            return ProjectCreateProcessState.INVALID_PATH

        if is_project_ready(container_path=str(target_path), root_path=root_path):
            return ProjectCreateProcessState.PROJECT_READY
        if is_ifc_project_ready(container_path=str(target_path)):
            return ProjectCreateProcessState.IFC_PROJECT_READY
        if is_facade_ready(container_path=str(target_path)):
            return ProjectCreateProcessState.IFC_PROJECT_FACADE_READY
        if is_dataset_ready(container_path=str(target_path), root_path=root_path):
            return ProjectCreateProcessState.PROJECT_DATASET_READY
        if is_container_ready(container_path=str(target_path), root_path=root_path):
            return ProjectCreateProcessState.ONTOBDC_CONTAINER_READY
        return ProjectCreateProcessState.UNDEFINED


class ProjectCreateStateTransitionHandler:
    _CAPABILITIES: Dict[ProjectCreateProcessState, Type[CapabilityPort]] = {
        ProjectCreateProcessState.ONTOBDC_CONTAINER_READY: OntoBDCContainerReadyCapability,
        ProjectCreateProcessState.PROJECT_DATASET_READY: ProjectDatasetReadyCapability,
        ProjectCreateProcessState.IFC_PROJECT_FACADE_READY: IfcProjectFacadeReadyCapability,
        ProjectCreateProcessState.IFC_PROJECT_READY: IfcProjectReadyCapability,
        ProjectCreateProcessState.PROJECT_READY: ProjectReadyCapability,
    }

    def __init__(self, context: CliContextPort, logger: Optional[LogRepositoryPort] = None) -> None:
        self._context = context
        self._target_path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve()
        self._logger = logger or NullLogRepository()
        self._state_evaluator = ProjectCreateStateEvaluatorAdapter()
        self._active_state: Optional[ProjectCreateProcessState] = None
        self._renderer = ProjectCreateResponseRenderer()

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> ProjectCreateProcessState:
        return self._active_state if self._active_state is not None else self.observed_state

    @property
    def observed_state(self) -> ProjectCreateProcessState:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[ProjectCreateProcessState]:
        return list(ProjectCreateProcessState)

    def can_transit_to(self, to_state: ProjectCreateProcessState) -> bool:
        active_state = self.current_state
        if active_state == ProjectCreateProcessState.UNDEFINED:
            expected = (
                ProjectCreateProcessState.INVALID_PATH
                if self.observed_state == ProjectCreateProcessState.INVALID_PATH
                else ProjectCreateProcessState.ONTOBDC_CONTAINER_READY
            )
            return to_state == expected
        return active_state != to_state

    def perform_state_transition(self, to_state: ProjectCreateProcessState) -> None:
        if to_state == ProjectCreateProcessState.INVALID_PATH:
            return
        if self.observed_state == to_state:
            return
        capability_type = self._CAPABILITIES.get(to_state)
        if capability_type is None:
            raise ValueError(f"InfoBIM project creation capability not found for state: {to_state.value}")
        capability = capability_type()
        self._logger.log_info(f"InfoBIM project create transition: {self.current_state.value} -> {to_state.value}")
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(self, from_state: ProjectCreateProcessState, to_state: ProjectCreateProcessState) -> bool:
        if from_state == to_state:
            return False
        observed_state = self.observed_state
        if observed_state == to_state:
            return True
        # `is_project_ready` is a superset check over the earlier stages (see
        # infobim.project.plugin.check.is_project_ready), so satisfying a deep
        # stage such as IFC_PROJECT_READY can make the freshly observed state
        # skip straight to PROJECT_READY in the same step. Treat reaching a
        # later stage in the declared sequence as fulfilling an earlier target
        # instead of failing the transition postcondition.
        order = self.state_sequence
        if observed_state not in order or to_state not in order:
            return False
        return order.index(observed_state) > order.index(to_state)

    def execute(self) -> CommandResponse:
        worker = StateWorkerAdapter(
            state_adapter=ProjectCreateProcessState,
            state_context_name="ProjectCreateProcessState",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states = worker.work()
        return self._renderer.render(
            target_path=self._target_path,
            current_state=self.current_state,
            visited_states=visited_states,
        )

    def _get_statechart_file_path(self) -> Path:
        return StatechartLocator.locate(
            __file__,
            "standard_project_create.yaml",
        )

    def bind_active_state(self, state: ProjectCreateProcessState) -> None:
        self._active_state = state


ContainerCreateStateTransitionHandler = ProjectCreateStateTransitionHandler
