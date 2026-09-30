from typing import Any, ClassVar, Dict, Tuple, Type

from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim.drawing.plugin.machine.drawing_view_discovery.port import (
    DrawingViewDiscoveryProcessStatePort,
)
from infobim._drawing_interactive.adapter.capability import InteractiveDrawingCapabilityLoader
from infobim.drawing.plugin.machine.drawing_view_discovery.state import (
    DrawingViewDiscoveryState,
)
from infobim.drawing.plugin.machine.drawing_view_discovery.machine import (
    DrawingViewDiscoveryStateTransitionHandler,
    DrawingViewDiscoveryStateEvaluatorAdapter,
)


class InteractiveDrawingViewDiscoveryStateEvaluatorAdapter(
    DrawingViewDiscoveryStateEvaluatorAdapter
):
    """
    Resolve the capabilities of the interactive Drawing View discovery.

    The states, and the capabilities they run, are those of the standard
    discovery. The final state then also presents the views interactively,
    after its relationships were modelled and validated with SHACL: the
    presentation is how this machine ends, not a state of the workflow.
    The presentation lives in the private ``_drawing_interactive`` package
    and is loaded from there, only by this machine.
    """

    INTERACTIVE_CAPABILITY_PREFIX: ClassVar[str] = "org.infobim._drawing_interactive."
    PRESENTATION_CAPABILITY_ID: ClassVar[str] = (
        "org.infobim._drawing_interactive.plugin.capability.loader."
        "drawing_views_interactively_presented"
    )
    STATE_TO_CAPABILITY_IDS: ClassVar[
        Dict[DrawingViewDiscoveryProcessStatePort, Tuple[str, ...]]
    ] = {
        **DrawingViewDiscoveryStateEvaluatorAdapter.STATE_TO_CAPABILITY_IDS,
        DrawingViewDiscoveryState.DRAWING_VIEW_RELATIONSHIPS_MODELED: (
            *DrawingViewDiscoveryStateEvaluatorAdapter.STATE_TO_CAPABILITY_IDS[
                DrawingViewDiscoveryState.DRAWING_VIEW_RELATIONSHIPS_MODELED
            ],
            PRESENTATION_CAPABILITY_ID,
        ),
    }
    STATECHART_PACKAGE: ClassVar[str] = (
        "infobim.drawing.plugin.machine.interactive_drawing_view_discovery"
    )
    STATECHART_FILE: ClassVar[str] = "standard_interactive_drawing_view_discovery.yaml"

    def _capability(
        self,
        state: DrawingViewDiscoveryProcessStatePort,
        capability_id: str,
    ) -> CapabilityPort:
        """
        Load the presentation from its private package, and every other
        capability as the standard discovery does.
        """
        if not capability_id.startswith(self.INTERACTIVE_CAPABILITY_PREFIX):
            return super()._capability(state, capability_id)
        capability_type: Any = InteractiveDrawingCapabilityLoader(self._logger).get(
            capability_id
        )
        if capability_type is None:
            raise ValueError(
                "Drawing View discovery capability not found for state: "
                f"{state.value} (id: {capability_id})"
            )
        return capability_type()


class InteractiveDrawingViewDiscoveryStateTransitionHandler(
    DrawingViewDiscoveryStateTransitionHandler
):
    """
    Drive the interactive Drawing View discovery statechart.

    It runs exactly as the standard discovery and, once the relationships
    of the sheet conform to SHACL, opens the interactive view browser.
    """

    EVALUATOR_TYPE: ClassVar[Type[DrawingViewDiscoveryStateEvaluatorAdapter]] = (
        InteractiveDrawingViewDiscoveryStateEvaluatorAdapter
    )
