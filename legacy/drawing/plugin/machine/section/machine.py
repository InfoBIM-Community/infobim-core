from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter

from infobim.drawing.plugin.machine.section.state import IfcSectionProcessState


class IfcSectionStateEvaluator:
    """Infer the reached transient state from the command context."""

    def evaluate(self, context: CliContextPort) -> IfcSectionProcessState:
        if context.has_parameter("section_dxf_path"):
            return IfcSectionProcessState.DXF_WRITTEN

        strategy = (
            context.get_parameter_value("section_strategy")
            if context.has_parameter("section_strategy")
            else None
        )
        if context.has_parameter("section_segments"):
            if isinstance(strategy, str) and strategy.startswith("native_plan"):
                return IfcSectionProcessState.NATIVE_PLAN_EXTRACTED
            if strategy == "body_section":
                return IfcSectionProcessState.BODY_SECTION_GENERATED

        if context.has_parameter("section_native_plan_available"):
            return IfcSectionProcessState.REPRESENTATIONS_INSPECTED
        if context.has_parameter("section_ifc_model"):
            return IfcSectionProcessState.IFC_LOADED
        return IfcSectionProcessState.UNDEFINED


class IfcSectionStateTransitionHandler:
    """Thin state-machine handler; each target state is owned by a capability."""

    CAPABILITY_PREFIX = (
        "org.infobim.drawing.plugin.capability.transformation.section.target."
    )

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._logger = logger or NullLogRepository()
        self._evaluator = IfcSectionStateEvaluator()
        self._active_state: Optional[IfcSectionProcessState] = None

    @property
    def current_state(self) -> IfcSectionProcessState:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> IfcSectionProcessState:
        return self._evaluator.evaluate(self._context)

    def bind_active_state(self, state: IfcSectionProcessState) -> None:
        self._active_state = state

    def can_transit_to(self, to_state: IfcSectionProcessState) -> bool:
        return self.current_state != to_state

    def has_native_plan(self) -> bool:
        return bool(
            self._context.get_parameter_value("section_native_plan_available")
        )

    def has_no_native_plan(self) -> bool:
        return not self.has_native_plan()

    def perform_state_transition(self, to_state: IfcSectionProcessState) -> None:
        capability_id = f"{self.CAPABILITY_PREFIX}{to_state.value.strip('_')}"
        capability_type = CapabilityLoader(
            root_packages=("infobim", "ontobdc")
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"IFC section capability not found: {capability_id}"
            )

        result: Dict[str, Any] = CapabilityExecutor.execute(
            capability_type(),
            self._context,
            StrategyParamResolver(
                ResolverLoader(root_packages=("infobim", "ontobdc"))
            ),
        )
        for key, value in result.items():
            self._context.set_parameter_value(key, value)

    def validate_state_transition(
        self,
        from_state: IfcSectionProcessState,
        to_state: IfcSectionProcessState,
    ) -> bool:
        if from_state == to_state:
            return False
        observed = self.observed_state
        if observed == to_state:
            return True
        raise ValueError(
            "IFC section transition contract failed: "
            f"{from_state.value} -> {to_state.value}; observed {observed.value}"
        )

    def execute(self) -> CommandResponse:
        worker = StateWorkerAdapter(
            state_adapter=IfcSectionProcessState,
            state_context_name="IfcSectionProcessState",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._statechart_path(),
        )
        visited_states: List[str] = worker.work()

        return CommandResponse(
            title="InfoBIM 2D: IFC Section",
            description=(
                "Generated a DXF from the IFC's native PLAN_VIEW representation "
                "when available; otherwise generated a horizontal section of "
                "the 3D Body."
            ),
            content={
                "source": self._context.get_parameter_value("ifc_path"),
                "z": self._context.get_parameter_value("section_z"),
                "strategy": self._context.get_parameter_value(
                    "section_strategy"
                ),
                "output": self._context.get_parameter_value(
                    "section_dxf_path"
                ),
                "segments": self._context.get_parameter_value(
                    "section_segment_count"
                ),
                "visited_states": visited_states,
            },
        )

    @staticmethod
    def _statechart_path() -> Path:
        return StatechartLocator.locate(
            "infobim.drawing.plugin.machine.section",
            "standard_section.yaml",
        )
