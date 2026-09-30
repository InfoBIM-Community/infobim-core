from typing import Any, ClassVar, Dict, Optional, Type
from pathlib import Path

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import ResolverLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim._2d.adapter.capability import TwoDCapabilityLoader
from infobim._2d.plugin.machine.dxf_viewer.port import (
    DxfViewerProcessStatePort,
    DxfViewerStateEvaluatorPort,
    DxfViewerStateTransitionHandlerPort,
)
from infobim._2d.plugin.machine.dxf_viewer.state import DxfViewerProcessState


class DxfViewerStateEvaluatorAdapter(DxfViewerStateEvaluatorPort):
    """
    Viewing a DXF file is an action of the current run: the drawing is read
    into the context and shown again every time, so no state is observed
    from a previous run.
    """

    def evaluate(self, context: CliContextPort) -> DxfViewerProcessStatePort:
        return DxfViewerProcessState.UNDEFINED


class DxfViewerStateTransitionHandler(DxfViewerStateTransitionHandlerPort):
    """
    Drives the DXF viewer statechart: load the DXF document into the
    context, then open the viewer. Each state's capability is resolved by
    id through the internal 2D capability loader.
    """

    _CAPABILITY_IDS: ClassVar[Dict[DxfViewerProcessStatePort, str]] = {
        DxfViewerProcessState.DXF_DOCUMENT_LOADED: (
            "org.infobim._2d.plugin.capability.loader.dxf_document"
        ),
        DxfViewerProcessState.DXF_VIEWER_OPENED: (
            "org.infobim.drawing.plugin.capability.loader.dxf_viewer"
        ),
    }

    STATECHART_PACKAGE: ClassVar[str] = "infobim._2d.plugin.machine.dxf_viewer"
    STATECHART_FILE: ClassVar[str] = "standard_dxf_viewer.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "DxfViewerProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: DxfViewerStateEvaluatorPort = (
            DxfViewerStateEvaluatorAdapter()
        )
        self._active_state: Optional[DxfViewerProcessStatePort] = None
        self._last_performed_state: Optional[DxfViewerProcessStatePort] = None
        self._result: Dict[str, Any] = {}

    @property
    def current_state(self) -> DxfViewerProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self._state_evaluator.evaluate(self._context)

    def can_transit_to(self, to_state: DxfViewerProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: DxfViewerProcessStatePort,
    ) -> None:
        if to_state not in self._CAPABILITY_IDS:
            raise ValueError(
                f"DXF viewer capability id not declared for state: {to_state.value}"
            )

        capability_id: str = self._CAPABILITY_IDS[to_state]
        capability_type: Optional[Type[CapabilityPort]] = TwoDCapabilityLoader(
            self._logger
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"DXF viewer capability not found for state: {to_state.value} "
                f"(id: {capability_id})"
            )

        self._logger.log_info(
            f"DXF viewer transition: {self.current_state.value} -> {to_state.value}",
        )
        self._result = CapabilityExecutor.execute(
            capability_type(),
            self._context,
            StrategyParamResolver(ResolverLoader()),
        )
        self._last_performed_state = to_state

    def validate_state_transition(
        self,
        from_state: DxfViewerProcessStatePort,
        to_state: DxfViewerProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._last_performed_state == to_state

    def bind_active_state(self, state: DxfViewerProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> Dict[str, Any]:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=DxfViewerProcessState,
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
