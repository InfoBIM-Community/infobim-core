from __future__ import annotations

from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.view.adapter.surface.machine import (
    SurfaceGenerationStateTransitionHandler,
)
from ontobdc.view.domain.machine.surface_state import (
    SurfaceGenerationProcessState,
)
from ontobdc.view.domain.port.surface_machine import (
    SurfaceGenerationProcessStatePort,
)
from ontobdc.view.plugin.capability.transformation.data_gathered import (
    DataGatheredCapability,
)

from infobim.view.adapter.presentation import (
    InfoBIMPresentationContextAdapter,
)
from infobim.view.domain.model import InfoBIMProjectPresentation
from infobim.view.plugin.capability.surface_matched import (
    InfoBIMSurfaceMatchedCapability,
)


class InfoBIMSurfaceGenerationStateTransitionHandler(
    SurfaceGenerationStateTransitionHandler
):
    """Specialize only BIM data projection and component matching."""

    def __init__(
        self,
        *,
        context,
        presentation: InfoBIMProjectPresentation,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        self._presentation = presentation
        self._presentation_adapter = InfoBIMPresentationContextAdapter()

    def perform_state_transition(
        self,
        to_state: SurfaceGenerationProcessStatePort,
    ) -> None:
        if to_state == SurfaceGenerationProcessState.DATA_GATHERED:
            super().perform_state_transition(to_state)
            model_resource = self._presentation_adapter.augment(
                DataGatheredCapability.state_path(self.context),
                self._presentation,
            )
            self.context.set_parameter_value(
                "infobim_project_resource",
                self._presentation.project_subject,
            )
            self.context.set_parameter_value(
                "infobim_ifc_model_resource",
                model_resource,
            )
            return

        if to_state == SurfaceGenerationProcessState.SURFACE_MATCHED:
            CapabilityExecutor.execute(
                InfoBIMSurfaceMatchedCapability(),
                self.context,
            )
            return

        super().perform_state_transition(to_state)

