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

from infobim._2d.adapter.capability import TwoDCapabilityLoader
from infobim._2d.plugin.machine.element_creation_from_point.port import (
    ElementCreationFromPointProcessStatePort,
    ElementCreationFromPointStateEvaluatorPort,
    ElementCreationFromPointStateTransitionHandlerPort,
)
from infobim._2d.plugin.machine.element_creation_from_point.state import (
    ElementCreationFromPointProcessState,
)


class ElementCreationFromPointStateEvaluatorAdapter(
    ElementCreationFromPointStateEvaluatorPort
):
    """
    Evaluate progress from the outputs the capabilities leave behind.

    Each state runs the capabilities declared for it, in order, resolved by
    id: OntoBDC capabilities through the OntoBDC capability loader, private
    InfoBIM 2D capabilities through the 2D loader, and the other InfoBIM
    capabilities through the capability loader of the InfoBIM package.

    The semantic states and FILE_METADATA_EXTRACTED persist their results
    and are observed through their capability's ``is_satisfied``. Loading
    the drawing, opening the viewer session, capturing points on that same
    session and creating the IFC elements at those points are actions of
    the current invocation: they are never observed as reached and are
    validated by having been performed. The elements themselves persist in
    the IFC model, but which of them this invocation created is known only
    to the run that created them.
    """

    STATE_TO_CAPABILITY_IDS: ClassVar[
        Dict[ElementCreationFromPointProcessStatePort, Tuple[str, ...]]
    ] = {
        ElementCreationFromPointProcessState.TEXT_NORMALIZED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "text_normalized",
        ),
        ElementCreationFromPointProcessState.TEXT_LANGUAGE_IDENTIFIED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "text_language_identified",
        ),
        ElementCreationFromPointProcessState.TEXT_LEMMATIZED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "text_lemmatized",
        ),
        ElementCreationFromPointProcessState.ONTOLOGY_TERM_RESOLVED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "ontology_term_resolved",
        ),
        ElementCreationFromPointProcessState.KIND_REPRESENTATION_RESOLVED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "kind_representation_resolved",
        ),
        ElementCreationFromPointProcessState.FILE_METADATA_EXTRACTED: (
            "org.ontobdc.storage.plugin.capability.transformation."
            "single_file_metadata_extracted",
        ),
        ElementCreationFromPointProcessState.DRAWING_DOCUMENTS_LOADED: (
            "org.infobim._2d.plugin.capability.transformation.dxf_path_resolved",
            "org.ontobdc.storage.plugin.capability.transformation."
            "single_file_metadata_extracted",
            "org.infobim._2d.plugin.capability.loader.dxf_document",
        ),
        ElementCreationFromPointProcessState.DXF_VIEWER_OPENED: (
            "org.infobim._2d.plugin.capability.loader.dxf_viewer_session",
        ),
        ElementCreationFromPointProcessState.POINTS_CAPTURED: (
            "org.infobim._2d.plugin.capability.loader.points_captured",
        ),
        ElementCreationFromPointProcessState.IFC_ELEMENTS_CREATED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "ifc_elements_created",
        ),
    }
    ACTION_STATES: ClassVar[Tuple[ElementCreationFromPointProcessStatePort, ...]] = (
        ElementCreationFromPointProcessState.DRAWING_DOCUMENTS_LOADED,
        ElementCreationFromPointProcessState.DXF_VIEWER_OPENED,
        ElementCreationFromPointProcessState.POINTS_CAPTURED,
        ElementCreationFromPointProcessState.IFC_ELEMENTS_CREATED,
    )
    ONTOBDC_CAPABILITY_PREFIX: ClassVar[str] = "org.ontobdc."
    INFOBIM_2D_CAPABILITY_PREFIX: ClassVar[str] = "org.infobim._2d."
    INFOBIM_CAPABILITY_PREFIX: ClassVar[str] = "org.infobim."
    INFOBIM_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim",)
    STATECHART_PACKAGE: ClassVar[str] = (
        "infobim._2d.plugin.machine.element_creation_from_point"
    )
    STATECHART_FILE: ClassVar[str] = "standard_element_creation_from_point.yaml"

    def __init__(self, logger: LogRepositoryPort) -> None:
        self._logger: LogRepositoryPort = logger

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ElementCreationFromPointProcessStatePort:
        reached_state: ElementCreationFromPointProcessStatePort = (
            ElementCreationFromPointProcessState.UNDEFINED
        )
        state_name: str
        for state_name in self.state_sequence()[1:]:
            state: ElementCreationFromPointProcessStatePort = (
                ElementCreationFromPointProcessState.get_state(state_name)
            )
            if state in self.ACTION_STATES:
                return reached_state
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
        state: ElementCreationFromPointProcessStatePort,
    ) -> List[CapabilityPort]:
        if state not in self.STATE_TO_CAPABILITY_IDS:
            raise ValueError(
                "Element creation from point capability ids not declared for "
                f"state: {state.value}"
            )
        return [
            self._capability(state, capability_id)
            for capability_id in self.STATE_TO_CAPABILITY_IDS[state]
        ]

    def _capability(
        self,
        state: ElementCreationFromPointProcessStatePort,
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
                "Element creation from point capability not found for state: "
                f"{state.value} (id: {capability_id})"
            )
        return capability_type()

    @classmethod
    def _statechart_data(cls) -> Dict[str, Any]:
        return yaml.safe_load(
            cls.statechart_file_path().read_text(encoding="utf-8")
        )


class ElementCreationFromPointStateTransitionHandler(
    ElementCreationFromPointStateTransitionHandlerPort
):
    """
    Drive the element creation from point statechart.

    Each state runs the capabilities declared for it, from the text that
    names the kind to the IFC elements created at the captured points.
    """

    STATE_CONTEXT_NAME: ClassVar[str] = "ElementCreationFromPointProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: ElementCreationFromPointStateEvaluatorAdapter = (
            ElementCreationFromPointStateEvaluatorAdapter(self._logger)
        )
        self._active_state: Optional[ElementCreationFromPointProcessStatePort] = None
        self._observed_state: Optional[ElementCreationFromPointProcessStatePort] = (
            None
        )
        self._last_performed_state: Optional[
            ElementCreationFromPointProcessStatePort
        ] = None
        self._result: Dict[str, Any] = {}

    @property
    def current_state(self) -> ElementCreationFromPointProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> ElementCreationFromPointProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)
        return self._observed_state

    def can_transit_to(
        self,
        to_state: ElementCreationFromPointProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: ElementCreationFromPointProcessStatePort,
    ) -> None:
        if to_state not in self._state_evaluator.ACTION_STATES and self._state_reaches(
            self.observed_state, to_state
        ):
            return

        capabilities: List[CapabilityPort] = self._state_evaluator.capabilities_for(
            to_state
        )
        self._logger.log_info(
            "Element creation from point transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        try:
            capability: CapabilityPort
            for capability in capabilities:
                self._result = CapabilityExecutor.execute(
                    capability,
                    self._context,
                    StrategyParamResolver(ResolverLoader()),
                )
            self._last_performed_state = to_state
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: ElementCreationFromPointProcessStatePort,
        to_state: ElementCreationFromPointProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False
        if to_state in self._state_evaluator.ACTION_STATES:
            return self._last_performed_state == to_state
        return self._state_reaches(self.observed_state, to_state)

    def bind_active_state(
        self,
        state: ElementCreationFromPointProcessStatePort,
    ) -> None:
        self._active_state = state
        self._forget_observed_state()

    def execute(self) -> Dict[str, Any]:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ElementCreationFromPointProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._state_evaluator.statechart_file_path(),
        )
        worker.work()
        final_state: ElementCreationFromPointProcessStatePort = (
            ElementCreationFromPointProcessState.IFC_ELEMENTS_CREATED
        )
        # The final state is an action of this run, so it is the last state
        # performed rather than a state the evaluator can observe.
        if self._last_performed_state != final_state:
            reached: str = (
                self._last_performed_state.value
                if self._last_performed_state is not None
                else self.observed_state.value
            )
            raise RuntimeError(
                "Element creation from point stopped at state "
                f"'{reached}' instead of '{final_state.value}'."
            )
        return dict(self._result)

    def _state_reaches(
        self,
        observed_state: ElementCreationFromPointProcessStatePort,
        target_state: ElementCreationFromPointProcessStatePort,
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
