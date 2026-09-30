from typing import Any, ClassVar, Dict, List, Tuple, Optional
from pathlib import Path

import yaml

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim.ifc.plugin.machine.ifc_model_create.state import IfcModelCreateProcessState
from infobim.ifc.plugin.machine.ifc_model_create.port import (
    IfcModelCreateProcessStatePort,
    IfcModelCreateStateEvaluatorPort,
    IfcModelCreateStateTransitionHandlerPort,
)


class IfcModelCreateStateEvaluatorAdapter(IfcModelCreateStateEvaluatorPort):
    """
    Evaluate progress from what the disk and the project's RO-Crate hold.

    Both states persist, so each is observed through its capability's
    ``is_satisfied``: a model that already exists and is declared makes the
    machine reach its final state without doing anything.
    """

    STATE_TO_CAPABILITY_IDS: ClassVar[
        Dict[IfcModelCreateProcessStatePort, Tuple[str, ...]]
    ] = {
        IfcModelCreateProcessState.IFC_MODEL_FILE_CREATED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "ifc_model_file_created",
        ),
        IfcModelCreateProcessState.IFC_MODEL_DECLARED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "ifc_model_declared",
        ),
    }
    INFOBIM_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim",)
    STATECHART_PACKAGE: ClassVar[str] = "infobim.ifc.plugin.machine.ifc_model_create"
    STATECHART_FILE: ClassVar[str] = "standard_ifc_model_create.yaml"

    def evaluate(
        self,
        context: CliContextPort,
    ) -> IfcModelCreateProcessStatePort:
        reached_state: IfcModelCreateProcessStatePort = (
            IfcModelCreateProcessState.UNDEFINED
        )
        state_name: str
        for state_name in self.state_sequence()[1:]:
            state: IfcModelCreateProcessStatePort = (
                IfcModelCreateProcessState.get_state(state_name)
            )
            capability: CapabilityPort
            for capability in self.capabilities_for(state):
                if not capability.is_satisfied(context):
                    return reached_state
            reached_state = state
        return reached_state

    @classmethod
    def state_sequence(cls) -> List[str]:
        return StateWorkerAdapter.compute_state_sequence(cls._statechart_data())

    @classmethod
    def statechart_file_path(cls) -> Path:
        return StatechartLocator.locate(cls.STATECHART_PACKAGE, cls.STATECHART_FILE)

    def capabilities_for(
        self,
        state: IfcModelCreateProcessStatePort,
    ) -> List[CapabilityPort]:
        if state not in self.STATE_TO_CAPABILITY_IDS:
            raise ValueError(
                f"IFC model creation capability ids not declared for state: "
                f"{state.value}"
            )
        return [
            self._capability(state, capability_id)
            for capability_id in self.STATE_TO_CAPABILITY_IDS[state]
        ]

    def _capability(
        self,
        state: IfcModelCreateProcessStatePort,
        capability_id: str,
    ) -> CapabilityPort:
        capability_type: Any = CapabilityLoader(
            root_packages=self.INFOBIM_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"IFC model creation capability not found for state: "
                f"{state.value} (id: {capability_id})"
            )
        return capability_type()

    @classmethod
    def _statechart_data(cls) -> Dict[str, Any]:
        return yaml.safe_load(
            cls.statechart_file_path().read_text(encoding="utf-8")
        )


class IfcModelCreateStateTransitionHandler(IfcModelCreateStateTransitionHandlerPort):
    """
    Drive the IFC model creation statechart.

    The run names the model's path under ``ifc_model_path`` and its project
    under ``container_path``; the machine writes the basic model there and
    declares it in the project's RO-Crate.
    """

    STATE_CONTEXT_NAME: ClassVar[str] = "IfcModelCreateProcessStatePort"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: IfcModelCreateStateEvaluatorAdapter = (
            IfcModelCreateStateEvaluatorAdapter()
        )
        self._active_state: Optional[IfcModelCreateProcessStatePort] = None
        self._observed_state: Optional[IfcModelCreateProcessStatePort] = None

    @property
    def current_state(self) -> IfcModelCreateProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> IfcModelCreateProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)
        return self._observed_state

    def can_transit_to(
        self,
        to_state: IfcModelCreateProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: IfcModelCreateProcessStatePort,
    ) -> None:
        if self._state_reaches(self.observed_state, to_state):
            return

        capabilities: List[CapabilityPort] = self._state_evaluator.capabilities_for(
            to_state
        )
        self._logger.log_info(
            "IFC model creation transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        try:
            capability: CapabilityPort
            for capability in capabilities:
                CapabilityExecutor.execute(
                    capability,
                    self._context,
                    StrategyParamResolver(ResolverLoader()),
                )
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: IfcModelCreateProcessStatePort,
        to_state: IfcModelCreateProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False
        return self._state_reaches(self.observed_state, to_state)

    def bind_active_state(
        self,
        state: IfcModelCreateProcessStatePort,
    ) -> None:
        self._active_state = state
        self._forget_observed_state()

    def execute(self) -> Path:
        """
        Bring the project's IFC model to being declared and return its path.
        """
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=IfcModelCreateProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._state_evaluator.statechart_file_path(),
        )
        worker.work()
        self._forget_observed_state()
        final_state: IfcModelCreateProcessStatePort = (
            IfcModelCreateProcessState.IFC_MODEL_DECLARED
        )
        if self.observed_state != final_state:
            raise RuntimeError(
                "IFC model creation stopped at state "
                f"'{self.observed_state.value}' instead of '{final_state.value}'."
            )
        return Path(self._context.get_parameter_value(self.IFC_MODEL_PATH_KEY))

    def _state_reaches(
        self,
        observed_state: IfcModelCreateProcessStatePort,
        target_state: IfcModelCreateProcessStatePort,
    ) -> bool:
        state_sequence: List[str] = self._state_evaluator.state_sequence()
        observed_name: str = observed_state.name.lower()
        target_name: str = target_state.name.lower()
        if observed_name not in state_sequence:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the statechart."
            )
        if target_name not in state_sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the statechart."
            )
        return state_sequence.index(observed_name) >= state_sequence.index(
            target_name
        )

    def _forget_observed_state(self) -> None:
        self._observed_state = None
