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

from infobim.ifc.plugin.machine.dxf_import.state import (
    IfcImportContextKeys,
    IfcImportProcessState,
)


class IfcImportStateEvaluatorAdapter:
    def evaluate(self, context: CliContextPort) -> IfcImportProcessState:
        reached = IfcImportProcessState.UNDEFINED

        source = context.get_parameter_value(IfcImportContextKeys.DXF_SOURCE_KEY)
        if not isinstance(source, str) or not source.strip():
            return reached
        source_path = Path(source).expanduser().resolve()
        if source_path.suffix.lower() != ".dxf" or not source_path.is_file():
            return reached
        reached = IfcImportProcessState.DXF_SOURCE_READY

        kind = context.get_parameter_value(
            IfcImportContextKeys.REPRESENTATION_KIND_KEY
        )
        if not isinstance(kind, str) or not kind.strip():
            return reached
        reached = IfcImportProcessState.REPRESENTATION_KIND_DEFINED

        geometry = context.get_parameter_value(
            IfcImportContextKeys.DXF_GEOMETRY_KEY
        )
        if not isinstance(geometry, dict):
            return reached
        entity_count = geometry.get("entity_count")
        entity_types = geometry.get("entity_types")
        if (
            not isinstance(entity_count, int)
            or entity_count < 0
            or not isinstance(entity_types, dict)
        ):
            return reached
        reached = IfcImportProcessState.DXF_GEOMETRY_READ

        if context.get_parameter_value(
            IfcImportContextKeys.IMPORT_READY_KEY
        ) is not True:
            return reached

        return IfcImportProcessState.IMPORT_READY


class IfcImportStateTransitionHandler:
    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim", "ontobdc")
    STATECHART_PACKAGE: ClassVar[str] = (
        "infobim.ifc.plugin.machine.dxf_import"
    )
    STATECHART_FILE: ClassVar[str] = "standard_dxf_import.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "IfcImportProcessState"

    CAPABILITY_IDS: ClassVar[Dict[IfcImportProcessState, str]] = {
        IfcImportProcessState.DXF_SOURCE_READY: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "dxf_source_ready"
        ),
        IfcImportProcessState.REPRESENTATION_KIND_DEFINED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "representation_kind_defined"
        ),
        IfcImportProcessState.DXF_GEOMETRY_READ: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "dxf_geometry_read"
        ),
        IfcImportProcessState.IMPORT_READY: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "import_ready"
        ),
    }

    RUN_LOCAL_KEYS: ClassVar[Tuple[str, ...]] = (
        IfcImportContextKeys.DXF_SOURCE_KEY,
        IfcImportContextKeys.REPRESENTATION_KIND_KEY,
        IfcImportContextKeys.DXF_GEOMETRY_KEY,
        IfcImportContextKeys.IMPORT_READY_KEY,
    )

    STATE_ORDER: ClassVar[Tuple[IfcImportProcessState, ...]] = (
        IfcImportProcessState.UNDEFINED,
        IfcImportProcessState.DXF_SOURCE_READY,
        IfcImportProcessState.REPRESENTATION_KIND_DEFINED,
        IfcImportProcessState.DXF_GEOMETRY_READ,
        IfcImportProcessState.IMPORT_READY,
    )

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._logger = logger or NullLogRepository()
        self._state_evaluator = IfcImportStateEvaluatorAdapter()
        self._active_state: Optional[IfcImportProcessState] = None
        self._observed_state: Optional[IfcImportProcessState] = None

    @property
    def current_state(self) -> IfcImportProcessState:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> IfcImportProcessState:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)
        return self._observed_state

    def can_transit_to(self, to_state: IfcImportProcessState) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: IfcImportProcessState) -> None:
        if self._is_reached(to_state):
            return

        self._logger.log_info(
            "IFC DXF import transition: "
            f"{self.current_state.value} -> {to_state.value}"
        )
        capability_id = self.CAPABILITY_IDS.get(to_state)
        if capability_id is None:
            raise ValueError(
                "IFC DXF import capability id not declared for state: "
                f"{to_state.value}"
            )

        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                "IFC DXF import capability not found for state: "
                f"{to_state.value} (id: {capability_id})"
            )

        try:
            CapabilityExecutor.execute(
                capability_type(),
                self._context,
                StrategyParamResolver(
                    ResolverLoader(root_packages=self.CAPABILITY_ROOT_PACKAGES)
                ),
            )
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: IfcImportProcessState,
        to_state: IfcImportProcessState,
    ) -> bool:
        if from_state == to_state:
            return False
        return self._is_reached(to_state)

    def execute(self) -> CommandResponse:
        self._clear_run_local_state()
        worker = StateWorkerAdapter(
            state_adapter=IfcImportProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._statechart_file_path(),
        )
        visited_states: List[str] = worker.work()

        geometry: Any = self._context.get_parameter_value(
            IfcImportContextKeys.DXF_GEOMETRY_KEY
        )
        geometry = geometry if isinstance(geometry, dict) else {}

        return CommandResponse(
            title="InfoBIM IFC: DXF Import",
            description=(
                "The DXF source was validated and inspected, and the import "
                "is ready for future IFC-writing states. No IFC representation "
                "was written."
            ),
            content={
                "kind": self._context.get_parameter_value(
                    IfcImportContextKeys.REPRESENTATION_KIND_KEY
                ),
                "source": self._context.get_parameter_value(
                    IfcImportContextKeys.DXF_SOURCE_KEY
                ),
                "entity_count": geometry.get("entity_count", 0),
                "entity_types": geometry.get("entity_types", {}),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
                "status": "ready",
            },
        )

    def bind_active_state(self, state: IfcImportProcessState) -> None:
        self._active_state = state

    def _forget_observed_state(self) -> None:
        self._observed_state = None

    def _clear_run_local_state(self) -> None:
        for key in self.RUN_LOCAL_KEYS:
            if self._context.has_parameter(key):
                self._context.delete_parameter(key)
        self._active_state = None
        self._forget_observed_state()

    def _is_reached(self, target: IfcImportProcessState) -> bool:
        observed = self._state_evaluator.evaluate(self._context)
        return self.STATE_ORDER.index(observed) >= self.STATE_ORDER.index(target)

    @classmethod
    def _statechart_file_path(cls) -> Path:
        return StatechartLocator.locate(
            cls.STATECHART_PACKAGE,
            cls.STATECHART_FILE,
        )
