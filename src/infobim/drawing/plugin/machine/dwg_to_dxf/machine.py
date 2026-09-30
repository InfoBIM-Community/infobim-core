from typing import Any, ClassVar, Dict, Optional, Tuple, Type
from pathlib import Path

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim.drawing.plugin.machine.dwg_to_dxf.port import (
    DwgToDxfProcessStatePort,
    DwgToDxfStateEvaluatorPort,
    DwgToDxfStateTransitionHandlerPort,
)
from infobim.drawing.plugin.machine.dwg_to_dxf.state import DwgToDxfProcessState


class DwgToDxfStateEvaluatorAdapter(DwgToDxfStateEvaluatorPort):
    """
    Every run asks for the conversion again; the converter itself returns the
    cached DXF when one already exists for the same DWG content.
    """

    def evaluate(self, context: CliContextPort) -> DwgToDxfProcessStatePort:
        return DwgToDxfProcessState.UNDEFINED


class DwgToDxfStateTransitionHandler(DwgToDxfStateTransitionHandlerPort):
    """
    Drives the DWG to DXF statechart. The state's capability is resolved by
    id through the CapabilityLoader rather than imported concretely.
    """

    _CAPABILITY_IDS: ClassVar[Dict[DwgToDxfProcessStatePort, str]] = {
        DwgToDxfProcessState.DWG_CONVERTED_TO_DXF: (
            "org.infobim.drawing.plugin.capability.transformation.dwg_to_dxf"
        ),
    }
    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim",)

    STATECHART_PACKAGE: ClassVar[str] = "infobim.drawing.plugin.machine.dwg_to_dxf"
    STATECHART_FILE: ClassVar[str] = "standard_dwg_to_dxf.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "DwgToDxfProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: DwgToDxfStateEvaluatorPort = (
            DwgToDxfStateEvaluatorAdapter()
        )
        self._active_state: Optional[DwgToDxfProcessStatePort] = None
        self._last_performed_state: Optional[DwgToDxfProcessStatePort] = None
        self._result: Dict[str, Any] = {}

    @property
    def current_state(self) -> DwgToDxfProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self._state_evaluator.evaluate(self._context)

    def can_transit_to(self, to_state: DwgToDxfProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: DwgToDxfProcessStatePort,
    ) -> None:
        if to_state not in self._CAPABILITY_IDS:
            raise ValueError(
                f"DWG to DXF capability id not declared for state: {to_state.value}"
            )

        capability_id: str = self._CAPABILITY_IDS[to_state]
        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"DWG to DXF capability not found for state: {to_state.value} "
                f"(id: {capability_id})"
            )

        self._logger.log_info(
            f"DWG to DXF transition: {self.current_state.value} -> {to_state.value}",
        )
        self._result = CapabilityExecutor.execute(
            capability_type(),
            self._context,
            StrategyParamResolver(ResolverLoader()),
        )
        self._last_performed_state = to_state

    def validate_state_transition(
        self,
        from_state: DwgToDxfProcessStatePort,
        to_state: DwgToDxfProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._last_performed_state == to_state

    def bind_active_state(self, state: DwgToDxfProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> Dict[str, Any]:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=DwgToDxfProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._statechart_file_path(),
        )
        worker.work()
        return dict(self._result)

    def _statechart_file_path(self) -> Path:
        return StatechartLocator.locate(
            self.STATECHART_PACKAGE,
            self.STATECHART_FILE,
        )
