from typing import Any, ClassVar, List, Optional, Tuple

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim.context.plugin.machine.entity_inspection.port import (
    EntityInspectionProcessStatePort,
    EntityInspectionStateEvaluatorPort,
)
from infobim.context.plugin.machine.entity_inspection.state import EntityInspectionProcessState
from infobim.context.plugin.machine.entity_inspection.statechart import EntityInspectionStatechart

CAPABILITY_ROOT_PACKAGES: Tuple[str, ...] = ("ontobdc", "infobim")


def _capability_for(loader: CapabilityLoader, state: EntityInspectionProcessStatePort) -> CapabilityPort:
    for capability_id in EntityInspectionStatechart.capability_ids(state):
        capability_type: Any = loader.get(capability_id)
        if capability_type is not None:
            return capability_type()

    raise ValueError(f"InfoBIM entity inspection capability not found for state: {state.value}")


class EntityInspectionStateEvaluatorAdapter(EntityInspectionStateEvaluatorPort):
    """Reports the furthest state whose capability is already satisfied."""

    def __init__(self, loader: CapabilityLoader) -> None:
        self._loader: CapabilityLoader = loader

    def evaluate(self, context: CliContextPort) -> EntityInspectionProcessStatePort:
        reached_state: EntityInspectionProcessStatePort = EntityInspectionProcessState.UNDEFINED
        for state_name in EntityInspectionStatechart.sequence()[1:]:
            state: EntityInspectionProcessStatePort = EntityInspectionProcessState.get_state(state_name)
            if not _capability_for(self._loader, state).is_satisfied(context):
                return reached_state
            reached_state = state

        return reached_state


class EntityInspectionStateTransitionHandler:
    """Drives the InfoBIM entity inspection: URI resolved, then information found."""

    ENTITY_KEY: ClassVar[str] = "entity_id"
    INFORMATION_KEY: ClassVar[str] = "entity_information"
    STATE_CONTEXT_NAME: ClassVar[str] = "EntityInspectionProcessStatePort"

    def __init__(self, context: CliContextPort, logger: Optional[LogRepositoryPort] = None) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._loader: CapabilityLoader = CapabilityLoader(root_packages=CAPABILITY_ROOT_PACKAGES)
        self._state_evaluator: EntityInspectionStateEvaluatorPort = EntityInspectionStateEvaluatorAdapter(self._loader)
        self._active_state: Optional[EntityInspectionProcessStatePort] = None
        self._observed_state: Optional[EntityInspectionProcessStatePort] = None

    @property
    def current_state(self) -> EntityInspectionProcessStatePort:
        return self._active_state if self._active_state is not None else self.observed_state

    @property
    def observed_state(self) -> EntityInspectionProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: EntityInspectionProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: EntityInspectionProcessStatePort) -> None:
        if self._reaches(self.observed_state, to_state):
            return

        self._logger.log_info(
            f"InfoBIM entity inspection transition: {self.current_state.value} -> {to_state.value}"
        )
        try:
            CapabilityExecutor.execute(
                _capability_for(self._loader, to_state),
                self._context,
                StrategyParamResolver(ResolverLoader()),
            )
        finally:
            self._observed_state = None

    def validate_state_transition(
        self,
        from_state: EntityInspectionProcessStatePort,
        to_state: EntityInspectionProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._reaches(self.observed_state, to_state)

    def bind_active_state(self, state: EntityInspectionProcessStatePort) -> None:
        self._active_state = state
        self._observed_state = None

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=EntityInspectionProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=EntityInspectionStatechart.path(),
        )
        try:
            worker.work()
        except CodeEvaluationError as error:
            cause: Optional[BaseException] = error.__cause__
            if isinstance(cause, Exception):
                raise cause from None
            raise

        if self.current_state != EntityInspectionProcessState.ENTITY_INFORMATION_FOUND:
            raise RuntimeError(
                f"Entity inspection stopped at state '{self.current_state.value}' "
                f"instead of '{EntityInspectionProcessState.ENTITY_INFORMATION_FOUND.value}'."
            )
        entity_id: Optional[str] = RequiredParameter.optional(self._context, self.ENTITY_KEY)
        description: str = (
            "Entities published by brasidatacenter."
            if entity_id is None
            else f"Facade of the entity <{entity_id}>."
        )

        return CommandResponse(
            title="Context Entity Inspect",
            description=description,
            content=self._context.get_parameter_value(self.INFORMATION_KEY),
        )

    @staticmethod
    def _reaches(
        observed_state: EntityInspectionProcessStatePort,
        target_state: EntityInspectionProcessStatePort,
    ) -> bool:
        sequence: List[str] = EntityInspectionStatechart.sequence()
        observed_name: str = observed_state.name.lower()
        target_name: str = target_state.name.lower()
        for name in (observed_name, target_name):
            if name not in sequence:
                raise ValueError(f"State '{name}' is absent from the InfoBIM entity inspection statechart.")

        return sequence.index(observed_name) >= sequence.index(target_name)
