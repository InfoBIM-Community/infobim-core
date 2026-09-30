from typing import Any, Dict, List, Optional
from pathlib import Path
from importlib import import_module

import yaml

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.context.adapter.taxonomy import (
    PARAMETER_KEY, REPRESENTATION_PARAMETER_KEY, CAPABILITY_PREFIX, MACHINE_PACKAGE, MACHINE_FILE,
)
from infobim.context.adapter.kind_resolution_event import KindResolutionEvent

DxfVectorProcessState: Any = import_module(MACHINE_PACKAGE + ".state").DxfVectorProcessState


DxfVectorStateEvaluatorPort: Any = import_module(MACHINE_PACKAGE + ".port").DxfVectorStateEvaluatorPort
DxfVectorStateTransitionHandlerPort: Any = import_module(MACHINE_PACKAGE + ".port").DxfVectorStateTransitionHandlerPort


class DxfVectorStateEvaluator(DxfVectorStateEvaluatorPort):
    """Observe durable per-document evidence through loader-resolved capabilities.

    The parameter strategy supplies the current kind. Context values alone never
    prove completion; capabilities validate ETL provenance before reporting ready.
    """

    def evaluate(self, context: CliContextPort) -> DxfVectorProcessState:
        KindResolutionEvent.required(context, PARAMETER_KEY)
        reached: DxfVectorProcessState = DxfVectorProcessState.UNDEFINED
        name: str
        for name in self.sequence()[1:]:
            state: DxfVectorProcessState = DxfVectorProcessState.get_state(name)
            capability: Any = self.capability(state)
            if not capability.is_satisfied(context):
                return reached
            reached = state
        return reached

    @staticmethod
    def sequence() -> List[str]:
        path: Path = StatechartLocator.locate(MACHINE_PACKAGE, MACHINE_FILE)
        data: Dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        return StateWorkerAdapter.compute_state_sequence(data)

    @staticmethod
    def capability(state: DxfVectorProcessState) -> Any:
        identifier: str = CAPABILITY_PREFIX + state.value.strip("_")
        capability_type: Any = CapabilityLoader(root_packages=("infobim", "ontobdc")).get(identifier)
        if capability_type is None:
            raise ValueError(f"Capability not found: {identifier}")
        return capability_type()


class DxfVectorStateTransitionHandler(DxfVectorStateTransitionHandlerPort):
    def __init__(
        self, context: CliContextPort, logger: Optional[LogRepositoryPort] = None
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = NullLogRepository() if logger is None else logger
        self._evaluator: DxfVectorStateEvaluator = DxfVectorStateEvaluator()
        self._active_state: Optional[DxfVectorProcessState] = None
        self._observed_state: Optional[DxfVectorProcessState] = None

    @property
    def current_state(self) -> DxfVectorProcessState:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> DxfVectorProcessState:
        if self._observed_state is None:
            self._observed_state = self._evaluator.evaluate(self._context)
        return self._observed_state

    def bind_active_state(self, state: DxfVectorProcessState) -> None:
        self._active_state = state
        self._observed_state = None

    def can_transit_to(self, to_state: DxfVectorProcessState) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: DxfVectorProcessState) -> None:
        capability: Any = self._evaluator.capability(to_state)
        try:
            if not capability.is_satisfied(self._context):
                CapabilityExecutor.execute(capability, self._context)
        finally:
            self._observed_state = None

    def validate_state_transition(
        self, from_state: DxfVectorProcessState, to_state: DxfVectorProcessState
    ) -> bool:
        sequence: List[str] = self._evaluator.sequence()
        return (
            from_state != to_state
            and sequence.index(self.observed_state.value.strip("_"))
            >= sequence.index(to_state.value.strip("_"))
        )

    def execute(self) -> CommandResponse:
        self._active_state = None
        self._observed_state = None
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=DxfVectorProcessState,
            state_context_name="DxfVectorProcessState",
            handler=self, logger=self._logger,
            statechart_file_path=StatechartLocator.locate(MACHINE_PACKAGE, MACHINE_FILE),
        )
        visited_states: List[str] = worker.work()
        return CommandResponse(
            title="InfoBIM 2D: Element creation from vector",
            description="Element kind and representation resolution.",
            content={
                PARAMETER_KEY: self._context.get_parameter_value(PARAMETER_KEY),
                REPRESENTATION_PARAMETER_KEY: self._context.get_parameter_value(REPRESENTATION_PARAMETER_KEY),
                "visited_states": visited_states,
            },
        )
