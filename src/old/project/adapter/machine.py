from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import yaml

from infobim.shared.adapter.loader import CapabilityLoader
from infobim.project.domain.machine.project_state import ContainerCreateProcessState
from infobim.cli.plugin.check.has_valid_infobim_config.check import (
    main as check_infobim_config,
)
from infobim.project.plugin.check.is_project_ready.check import (
    main as check_project_ready,
)
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort
from ontobdc.storage.domain.port.machine import (
    ContainerCreateProcessStatePort,
    ContainerCreateStateEvaluatorPort,
    ContainerCreateStateTransitionHandlerPort,
)
from ontobdc.storage.plugin.check.is_container_manifest_synced.check import (
    main as check_container_manifest_synced,
)
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.storage.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)


def _load_statechart_data(statechart_file_path: Path) -> Dict[str, Any]:
    with open(statechart_file_path, "r", encoding="utf-8") as file_handle:
        loaded_data: object = yaml.safe_load(file_handle) or {}
    if not isinstance(loaded_data, dict):
        return {}
    return loaded_data


def _find_state_definition(
    node: Dict[str, Any],
    state_name: str,
) -> Optional[Dict[str, Any]]:
    states: object = node.get("states")
    if isinstance(states, list):
        state_definition: object
        for state_definition in states:
            if not isinstance(state_definition, dict):
                continue

            if str(state_definition.get("name", "")).strip() == state_name:
                return state_definition

            nested_state_definition: Optional[Dict[str, Any]] = _find_state_definition(
                state_definition,
                state_name,
            )
            if nested_state_definition is not None:
                return nested_state_definition

    parallel_states: object = node.get("parallel states")
    if isinstance(parallel_states, list):
        parallel_definition: object
        for parallel_definition in parallel_states:
            if not isinstance(parallel_definition, dict):
                continue
            nested_parallel_definition: Optional[Dict[str, Any]] = _find_state_definition(
                parallel_definition,
                state_name,
            )
            if nested_parallel_definition is not None:
                return nested_parallel_definition

    return None


def _get_declared_transition_targets(
    statechart_file_path: Path,
    active_state_name: str,
) -> List[str]:
    statechart_data: Dict[str, Any] = _load_statechart_data(statechart_file_path)
    statechart_definition: object = statechart_data.get("statechart")
    if not isinstance(statechart_definition, dict):
        return []

    root_state_definition: object = statechart_definition.get("root state")
    if not isinstance(root_state_definition, dict):
        return []

    state_definition: Optional[Dict[str, Any]] = _find_state_definition(
        root_state_definition,
        active_state_name,
    )
    if state_definition is None:
        return []

    transitions: object = state_definition.get("transitions")
    if not isinstance(transitions, list):
        return []

    targets: List[str] = []
    transition: object
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        target_name: str = str(transition.get("target", "")).strip()
        if target_name:
            targets.append(target_name)

    return targets


def _resolve_declared_transition_target(
    statechart_file_path: Path,
    active_state_value: str,
    observed_state_value: str,
) -> Optional[str]:
    active_state_name: str = active_state_value.strip("_")
    observed_state_name: str = observed_state_value.strip("_")
    declared_targets: List[str] = _get_declared_transition_targets(
        statechart_file_path=statechart_file_path,
        active_state_name=active_state_name,
    )
    if not declared_targets:
        return None

    if observed_state_name in declared_targets:
        return observed_state_name

    return declared_targets[-1]


class ContainerCreateStateEvaluatorAdapter(ContainerCreateStateEvaluatorPort):
    @property
    def process_state_class(self) -> Type[ContainerCreateProcessStatePort]:
        return ContainerCreateProcessState

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerCreateProcessStatePort:
        target_path: Path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve()
        root_path: Path = Path(context.root_path).expanduser().resolve()

        if target_path.exists() and not target_path.is_dir():
            return ContainerCreateProcessState.INVALID_PATH

        if check_infobim_config(root_path=str(root_path)) != 0:
            return ContainerCreateProcessState.UNDEFINED

        if target_path.exists() and target_path.is_dir():
            metadata_check_result: int = check_container_metadata_ready(
                root_path=str(root_path),
                container_path=str(target_path),
            )
            if metadata_check_result == 0:
                storage_index_check_result: int = check_container_storage_index_ready(
                    root_path=str(root_path),
                    container_path=str(target_path),
                )
                if storage_index_check_result == 0:
                    manifest_check_result: int = check_container_manifest_synced(
                        root_path=str(root_path),
                        container_path=str(target_path),
                    )
                    if manifest_check_result == 0:
                        project_check_result: int = check_project_ready(container_path=str(target_path))
                        if project_check_result == 0:
                            return ContainerCreateProcessState.PROJECT_READY

                        return ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED

                    return ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY

                return ContainerCreateProcessState.CONTAINER_METADATA_READY

            return ContainerCreateProcessState.DIRECTORY_READY

        return ContainerCreateProcessState.INFOBIM_CONFIG_READY


class ContainerCreateStateTransitionHandler(ContainerCreateStateTransitionHandlerPort):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._target_path: Path = Path(str(self._context.get_parameter_value("container_path"))).expanduser().resolve()
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: ContainerCreateStateEvaluatorPort = ContainerCreateStateEvaluatorAdapter()
        self._active_state: Optional[ContainerCreateProcessStatePort] = None

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> ContainerCreateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ContainerCreateProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[ContainerCreateProcessStatePort]:
        return list(ContainerCreateProcessState)

    def can_transit_to(self, to_state: ContainerCreateProcessStatePort) -> bool:
        active_state: ContainerCreateProcessStatePort = self.current_state
        observed_state: ContainerCreateProcessStatePort = self.observed_state
        next_target_name: Optional[str] = _resolve_declared_transition_target(
            statechart_file_path=self._get_statechart_file_path(),
            active_state_value=active_state.value,
            observed_state_value=observed_state.value,
        )
        if next_target_name is None:
            return False

        return to_state.value.strip("_") == next_target_name

    def perform_state_transition(self, to_state: ContainerCreateProcessStatePort) -> None:
        observed_state: ContainerCreateProcessStatePort = self.observed_state
        if observed_state == to_state:
            return

        self._logger.log_info(
            f"InfoBIM storage container create transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = (
            f"org.ontobdc.storage.plugin.capability.transformation.target.{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"InfoBIM storage container create capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: ContainerCreateProcessStatePort,
        to_state: ContainerCreateProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        observed_state: ContainerCreateProcessStatePort = self.observed_state
        if observed_state == to_state:
            return True

        state_sequence: List[ContainerCreateProcessStatePort] = self.state_sequence
        if to_state not in state_sequence or observed_state not in state_sequence:
            return False

        return state_sequence.index(observed_state) > state_sequence.index(to_state)

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ContainerCreateProcessState,
            state_context_name="ContainerCreateProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states: List[str] = worker.work()
        return self._build_final_response(visited_states)

    def _build_final_response(self, visited_states: List[str]) -> CommandResponse:
        if self.current_state == ContainerCreateProcessState.INVALID_PATH:
            return ExceptionCommandResponse(
                title="Invalid Storage Container Path",
                description="The target path points to an existing file and cannot become a container directory.",
                content={
                    "path": str(self._target_path),
                    "current_state": self.current_state.value,
                    "visited_states": visited_states,
                },
            )

        return CommandResponse(
            title="InfoBIM Storage Container Created",
            description="The local storage container directory, metadata, storage index entry, InfoBIM project configuration, and manifest are ready for the next creation steps.",
            content={
                "path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
                "exists": self._target_path.exists(),
            },
        )

    def _get_statechart_file_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "domain" / "machine" / "standard_container_create.yaml"

    def bind_active_state(self, state: ContainerCreateProcessStatePort) -> None:
        self._active_state = state
