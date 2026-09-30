from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim.drawing.plugin.machine.line.state import DxfLineProcessState


class DxfLineStateEvaluator:
    def evaluate(self, context: CliContextPort) -> DxfLineProcessState:
        if context.has_parameter("line_trace_text"):
            trace_text = context.get_parameter_value("line_trace_text")
            if isinstance(trace_text, str) and trace_text.strip():
                return DxfLineProcessState.TRACE_READY

        if context.has_parameter("line_trace"):
            trace = context.get_parameter_value("line_trace")
            if isinstance(trace, list) and len(trace) >= 2:
                return DxfLineProcessState.LINE_CAPTURED

        if context.has_parameter("line_dxf_document"):
            return DxfLineProcessState.DXF_LOADED

        return DxfLineProcessState.UNDEFINED


class DxfLineStateTransitionHandler:
    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim", "ontobdc")
    STATECHART_PACKAGE: ClassVar[str] = "infobim.drawing.plugin.machine.line"
    STATECHART_FILE: ClassVar[str] = "standard_line.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "DxfLineProcessState"

    CAPABILITY_IDS: ClassVar[Dict[DxfLineProcessState, str]] = {
        DxfLineProcessState.DXF_LOADED: (
            "org.infobim.drawing.plugin.capability.transformation."
            "line.target.dxf_loaded"
        ),
        DxfLineProcessState.LINE_CAPTURED: (
            "org.infobim.drawing.plugin.capability.transformation."
            "line.target.line_captured"
        ),
        DxfLineProcessState.TRACE_READY: (
            "org.infobim.drawing.plugin.capability.transformation."
            "line.target.trace_ready"
        ),
    }

    RUN_LOCAL_KEYS: ClassVar[Tuple[str, ...]] = (
        "line_dxf_document",
        "line_trace",
        "line_trace_text",
    )

    STATE_ORDER: ClassVar[Tuple[DxfLineProcessState, ...]] = (
        DxfLineProcessState.UNDEFINED,
        DxfLineProcessState.DXF_LOADED,
        DxfLineProcessState.LINE_CAPTURED,
        DxfLineProcessState.TRACE_READY,
    )

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._logger = logger or NullLogRepository()
        self._evaluator = DxfLineStateEvaluator()
        self._active_state: Optional[DxfLineProcessState] = None

    @property
    def current_state(self) -> DxfLineProcessState:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> DxfLineProcessState:
        return self._evaluator.evaluate(self._context)

    def bind_active_state(self, state: DxfLineProcessState) -> None:
        self._active_state = state

    def can_transit_to(self, to_state: DxfLineProcessState) -> bool:
        return not self._is_reached(to_state)

    def perform_state_transition(self, to_state: DxfLineProcessState) -> None:
        if self._is_reached(to_state):
            return

        self._logger.log_info(
            f"DXF line transition: {self.current_state.value} -> {to_state.value}"
        )
        capability_id = self.CAPABILITY_IDS.get(to_state)
        if capability_id is None:
            raise ValueError(
                f"DXF line capability id not declared for state: {to_state.value}"
            )

        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                "DXF line capability not found for state: "
                f"{to_state.value} (id: {capability_id})"
            )

        CapabilityExecutor.execute(
            capability_type(),
            self._context,
            StrategyParamResolver(
                ResolverLoader(root_packages=self.CAPABILITY_ROOT_PACKAGES)
            ),
        )

    def validate_state_transition(
        self,
        from_state: DxfLineProcessState,
        to_state: DxfLineProcessState,
    ) -> bool:
        if from_state == to_state:
            return False
        return self._is_reached(to_state)

    def execute(self) -> CommandResponse:
        self._clear_run_local_state()
        worker = StateWorkerAdapter(
            state_adapter=DxfLineProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._statechart_path(),
        )
        visited_states: List[str] = worker.work()

        raw_points: Any = self._context.get_parameter_value("line_trace")
        points = (
            [[float(point[0]), float(point[1])] for point in raw_points]
            if isinstance(raw_points, list)
            else []
        )

        return CommandResponse(
            title="InfoBIM 2D: Line",
            description=(
                "Captured a freehand line over the DXF in modelspace "
                "coordinates. The source DXF was not modified."
            ),
            content={
                "source": self._context.get_parameter_value("dxf_path"),
                "point_count": len(points),
                "points": points,
                "trace": self._context.get_parameter_value("line_trace_text"),
                "visited_states": visited_states,
            },
        )

    def _clear_run_local_state(self) -> None:
        for key in self.RUN_LOCAL_KEYS:
            if self._context.has_parameter(key):
                self._context.delete_parameter(key)
        self._active_state = None

    def _is_reached(self, target: DxfLineProcessState) -> bool:
        observed = self._evaluator.evaluate(self._context)
        return self.STATE_ORDER.index(observed) >= self.STATE_ORDER.index(target)

    @classmethod
    def _statechart_path(cls) -> Path:
        return StatechartLocator.locate(
            cls.STATECHART_PACKAGE,
            cls.STATECHART_FILE,
        )
