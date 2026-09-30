from typing import Any, ClassVar, Dict, List, Tuple, Type, Optional
from pathlib import Path

import yaml

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim._2d.adapter.capability import TwoDCapabilityLoader
from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.plugin.machine.drawing_view_discovery.port import (
    DrawingViewDiscoveryProcessStatePort,
    DrawingViewDiscoveryStateEvaluatorPort,
    DrawingViewDiscoveryStateTransitionHandlerPort,
)
from infobim.drawing.plugin.machine.drawing_view_discovery.state import (
    DrawingViewDiscoveryState,
)


class DrawingViewDiscoveryStateEvaluatorAdapter(DrawingViewDiscoveryStateEvaluatorPort):
    """
    Resolve the capabilities of each Drawing View discovery state.

    Every state works on what the current invocation read from the sheet,
    so none is observed as reached: each is validated by having been
    performed. The first state also loads the sheet, reusing the open-file
    metadata, the DWG to DXF path resolution and the DXF loader of the 2D
    stack, then indexes its model space.
    """

    STATE_TO_CAPABILITY_IDS: ClassVar[
        Dict[DrawingViewDiscoveryProcessStatePort, Tuple[str, ...]]
    ] = {
        DrawingViewDiscoveryState.DRAWING_VIEWPORTS_DISCOVERED: (
            "org.ontobdc.storage.plugin.capability.transformation."
            "single_file_metadata_extracted",
            "org.infobim._2d.plugin.capability.transformation.dxf_path_resolved",
            "org.ontobdc.storage.plugin.capability.transformation."
            "single_file_metadata_extracted",
            "org.infobim._2d.plugin.capability.loader.dxf_document",
            "org.infobim.drawing.plugin.capability.loader.drawing_sheet_entities",
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_viewports_discovered",
        ),
        DrawingViewDiscoveryState.DRAWING_VIEW_TITLES_RESOLVED: (
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_view_titles_resolved",
        ),
        DrawingViewDiscoveryState.DRAWING_VIEW_FRAMES_DETECTED: (
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_view_frames_detected",
        ),
        DrawingViewDiscoveryState.DRAWING_VIEW_REFERENCES_DETECTED: (
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_view_references_detected",
        ),
        DrawingViewDiscoveryState.DRAWING_VIEW_CLUSTERS_DETECTED: (
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_view_clusters_detected",
        ),
        DrawingViewDiscoveryState.DRAWING_VIEWS_CLASSIFIED: (
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_views_classified",
        ),
        DrawingViewDiscoveryState.DRAWING_VIEWS_EXTRACTED: (
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_views_extracted",
        ),
        DrawingViewDiscoveryState.DRAWING_VIEW_RELATIONSHIPS_MODELED: (
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_view_relationships_modeled",
        ),
    }
    ONTOBDC_CAPABILITY_PREFIX: ClassVar[str] = "org.ontobdc."
    INFOBIM_2D_CAPABILITY_PREFIX: ClassVar[str] = "org.infobim._2d."
    INFOBIM_CAPABILITY_PREFIX: ClassVar[str] = "org.infobim."
    INFOBIM_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim",)
    STATECHART_PACKAGE: ClassVar[str] = (
        "infobim.drawing.plugin.machine.drawing_view_discovery"
    )
    STATECHART_FILE: ClassVar[str] = "standard_drawing_view_discovery.yaml"

    def __init__(self, logger: LogRepositoryPort) -> None:
        self._logger: LogRepositoryPort = logger

    def evaluate(
        self,
        context: CliContextPort,
    ) -> DrawingViewDiscoveryProcessStatePort:
        return DrawingViewDiscoveryState.UNDEFINED

    @classmethod
    def state_sequence(cls) -> List[str]:
        return StateWorkerAdapter.compute_state_sequence(cls._statechart_data())

    @classmethod
    def statechart_file_path(cls) -> Path:
        return StatechartLocator.locate(cls.STATECHART_PACKAGE, cls.STATECHART_FILE)

    def capabilities_for(
        self,
        state: DrawingViewDiscoveryProcessStatePort,
    ) -> List[CapabilityPort]:
        if state not in self.STATE_TO_CAPABILITY_IDS:
            raise ValueError(
                "Drawing View discovery capability ids not declared for state: "
                f"{state.value}"
            )
        return [
            self._capability(state, capability_id)
            for capability_id in self.STATE_TO_CAPABILITY_IDS[state]
        ]

    def _capability(
        self,
        state: DrawingViewDiscoveryProcessStatePort,
        capability_id: str,
    ) -> CapabilityPort:
        capability_type: Any
        if capability_id.startswith(self.ONTOBDC_CAPABILITY_PREFIX):
            capability_type = CapabilityLoader().get(capability_id)
        elif capability_id.startswith(self.INFOBIM_2D_CAPABILITY_PREFIX):
            capability_type = TwoDCapabilityLoader(self._logger).get(capability_id)
        elif capability_id.startswith(self.INFOBIM_CAPABILITY_PREFIX):
            capability_type = CapabilityLoader(
                root_packages=self.INFOBIM_ROOT_PACKAGES
            ).get(capability_id)
        else:
            raise ValueError(
                f"Capability id '{capability_id}' belongs to no known loader."
            )
        if capability_type is None:
            raise ValueError(
                "Drawing View discovery capability not found for state: "
                f"{state.value} (id: {capability_id})"
            )
        return capability_type()

    @classmethod
    def _statechart_data(cls) -> Dict[str, Any]:
        return yaml.safe_load(
            cls.statechart_file_path().read_text(encoding="utf-8")
        )


class DrawingViewDiscoveryStateTransitionHandler(
    DrawingViewDiscoveryStateTransitionHandlerPort
):
    """
    Drive the Drawing View discovery statechart.

    Every state runs, from loading the sheet to modelling, and validating
    with SHACL, how the sheet relates to the views extracted from it.
    """

    STATE_CONTEXT_NAME: ClassVar[str] = "DrawingViewDiscoveryProcessStatePort"
    EVALUATOR_TYPE: ClassVar[Type[DrawingViewDiscoveryStateEvaluatorAdapter]] = (
        DrawingViewDiscoveryStateEvaluatorAdapter
    )
    FINAL_STATE: ClassVar[DrawingViewDiscoveryProcessStatePort] = (
        DrawingViewDiscoveryState.DRAWING_VIEW_RELATIONSHIPS_MODELED
    )

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: DrawingViewDiscoveryStateEvaluatorAdapter = (
            self.EVALUATOR_TYPE(self._logger)
        )
        self._active_state: Optional[DrawingViewDiscoveryProcessStatePort] = None
        self._observed_state: Optional[DrawingViewDiscoveryProcessStatePort] = None
        self._last_performed_state: Optional[DrawingViewDiscoveryProcessStatePort] = (
            None
        )

    @property
    def current_state(self) -> DrawingViewDiscoveryProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> DrawingViewDiscoveryProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)
        return self._observed_state

    def can_transit_to(
        self,
        to_state: DrawingViewDiscoveryProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: DrawingViewDiscoveryProcessStatePort,
    ) -> None:
        capabilities: List[CapabilityPort] = self._state_evaluator.capabilities_for(
            to_state
        )
        self._logger.log_info(
            "Drawing View discovery transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability: CapabilityPort
        for capability in capabilities:
            CapabilityExecutor.execute(
                capability,
                self._context,
                StrategyParamResolver(ResolverLoader()),
            )
        self._last_performed_state = to_state

    def validate_state_transition(
        self,
        from_state: DrawingViewDiscoveryProcessStatePort,
        to_state: DrawingViewDiscoveryProcessStatePort,
    ) -> bool:
        return from_state != to_state and self._last_performed_state == to_state

    def bind_active_state(
        self,
        state: DrawingViewDiscoveryProcessStatePort,
    ) -> None:
        self._active_state = state
        self._observed_state = None

    def execute(self) -> Dict[str, Any]:
        """
        Run the discovery to its final state and return what it settled.
        """
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=DrawingViewDiscoveryState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._state_evaluator.statechart_file_path(),
        )
        worker.work()

        if self._last_performed_state != self.FINAL_STATE:
            reached: str = (
                self._last_performed_state.value
                if self._last_performed_state is not None
                else self.observed_state.value
            )
            raise RuntimeError(
                "Drawing View discovery stopped at state "
                f"'{reached}' instead of '{self.FINAL_STATE.value}'."
            )
        return {
            DrawingViewContextKeys.VIEWS: self._context.get_parameter_value(
                DrawingViewContextKeys.VIEWS
            ),
            DrawingViewContextKeys.VIEWS_DIRECTORY: self._context.get_parameter_value(
                DrawingViewContextKeys.VIEWS_DIRECTORY
            ),
            DrawingViewContextKeys.RELATIONSHIPS: self._context.get_parameter_value(
                DrawingViewContextKeys.RELATIONSHIPS
            ),
        }
