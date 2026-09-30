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

from infobim._3d.adapter.capability import ThreeDCapabilityLoader
from infobim._3d.plugin.machine.ifc_viewer.port import (
    IfcViewerProcessStatePort,
    IfcViewerStateEvaluatorPort,
    IfcViewerStateTransitionHandlerPort,
)
from infobim._3d.plugin.machine.ifc_viewer.state import IfcViewerProcessState


class IfcViewerStateEvaluatorAdapter(IfcViewerStateEvaluatorPort):
    """
    Viewing an IFC file is an action of the current run: the model is read
    into the context, triangulated and shown again every time, so no state
    is observed from a previous run.
    """

    def evaluate(self, context: CliContextPort) -> IfcViewerProcessStatePort:
        return IfcViewerProcessState.UNDEFINED


class IfcViewerStateTransitionHandler(IfcViewerStateTransitionHandlerPort):
    """
    Drives the IFC 3D viewer statechart: load the IFC model into the
    context, triangulate it into Qt Quick 3D geometries, then open the
    viewer. Each state's capability is resolved by id through the internal
    3D capability loader.
    """

    _CAPABILITY_IDS: ClassVar[Dict[IfcViewerProcessStatePort, str]] = {
        IfcViewerProcessState.IFC_DOCUMENT_LOADED: (
            "org.infobim._3d.plugin.capability.loader.ifc_document"
        ),
        IfcViewerProcessState.IFC_QUICK3D_GEOMETRIES_CREATED: (
            "org.infobim._3d.plugin.capability.loader.ifc_quick3d_geometry"
        ),
        IfcViewerProcessState.IFC_3D_VIEWER_OPENED: (
            "org.infobim._3d.plugin.capability.loader.ifc_viewer"
        ),
    }

    STATECHART_PACKAGE: ClassVar[str] = "infobim._3d.plugin.machine.ifc_viewer"
    STATECHART_FILE: ClassVar[str] = "standard_ifc_viewer.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "IfcViewerProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: IfcViewerStateEvaluatorPort = (
            IfcViewerStateEvaluatorAdapter()
        )
        self._active_state: Optional[IfcViewerProcessStatePort] = None
        self._last_performed_state: Optional[IfcViewerProcessStatePort] = None
        self._result: Dict[str, Any] = {}

    @property
    def current_state(self) -> IfcViewerProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self._state_evaluator.evaluate(self._context)

    def can_transit_to(self, to_state: IfcViewerProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: IfcViewerProcessStatePort,
    ) -> None:
        if to_state not in self._CAPABILITY_IDS:
            raise ValueError(
                f"IFC 3D viewer capability id not declared for state: {to_state.value}"
            )

        capability_id: str = self._CAPABILITY_IDS[to_state]
        capability_type: Optional[Type[CapabilityPort]] = ThreeDCapabilityLoader(
            self._logger
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"IFC 3D viewer capability not found for state: {to_state.value} "
                f"(id: {capability_id})"
            )

        self._logger.log_info(
            f"IFC 3D viewer transition: {self.current_state.value} -> {to_state.value}",
        )
        self._result = CapabilityExecutor.execute(
            capability_type(),
            self._context,
            StrategyParamResolver(ResolverLoader()),
        )
        self._last_performed_state = to_state

    def validate_state_transition(
        self,
        from_state: IfcViewerProcessStatePort,
        to_state: IfcViewerProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._last_performed_state == to_state

    def bind_active_state(self, state: IfcViewerProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> Dict[str, Any]:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=IfcViewerProcessState,
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
