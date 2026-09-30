from typing import Any, ClassVar, List, Optional, Tuple, Type
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

from .state import ThreeDViewContextKeys, ThreeDViewProcessState
from ....domain.port.machine import (
    ThreeDViewProcessStatePort,
    ThreeDViewStateEvaluatorPort,
)


class ThreeDViewStateEvaluatorAdapter(ThreeDViewStateEvaluatorPort):
    """
    Reports the state opening the 3D viewer for a Project is already in.

    Injecting the IfcProject or the inspect tree leaves no durable,
    on-disk artifact to observe the way the other machines in this
    codebase check for (see ThreeDViewProcessState's own docstring):
    every launch starts the same way and reads the Project fresh. What
    this evaluates instead is which of PROJECT_TREE_KEY and
    IFC_PROJECT_JSONLD_KEY has already been staged on this context --
    true only once the matching capability has actually run during this
    command's own execution -- so the statechart's own postcondition
    contract still has something real to verify after each transition.
    Neither capability's own class is imported here: ThreeDViewContextKeys
    names the context keys both sides agree on, so this evaluator does
    not need to know which capability, if any, fills them in.
    """

    def evaluate(self, context: CliContextPort) -> ThreeDViewProcessStatePort:
        elements: Any = context.get_parameter_value(
            ThreeDViewContextKeys.THREE_D_ELEMENT_TREE_KEY
        )
        if elements is not None:
            return ThreeDViewProcessState.THREE_D_ELEMENT_TREE_INJECTED

        tree: Any = context.get_parameter_value(
            ThreeDViewContextKeys.PROJECT_TREE_KEY
        )
        if tree is not None:
            return ThreeDViewProcessState.PROJECT_TREE_INJECTED

        jsonld: Any = context.get_parameter_value(
            ThreeDViewContextKeys.IFC_PROJECT_JSONLD_KEY
        )
        if jsonld is not None:
            return ThreeDViewProcessState.IFC_PROJECT_INJECTED

        meshes: Any = context.get_parameter_value(
            ThreeDViewContextKeys.IFC_ELEMENT_MESHES_KEY
        )
        if meshes is not None:
            return ThreeDViewProcessState.IFC_ELEMENT_MESHES_CONVERTED

        return ThreeDViewProcessState.UNDEFINED


class ThreeDViewStateTransitionHandler:
    """
    Drives one Project's viewer launch through its own machine.

    The Project itself is resolved and validated before this runs -- that
    is the command's own precondition, not a state this machine tracks --
    so the only transition here is reading the Project's IfcProject and
    staging it as JSON-LD (on the context, under
    ThreeDViewContextKeys.IFC_PROJECT_JSONLD_KEY) for the viewer page.

    perform_state_transition resolves each target state's capability by
    id through CapabilityLoader, never by importing a concrete
    capability class: that import would tie this machine to one
    particular implementation of the state instead of whichever
    capability declares that id, the same way every other machine in
    this codebase resolves its own transitions.

    Unlike ProjectCreateStateTransitionHandler, execute() returns the
    visited states rather than a finished CommandResponse: the command
    still has to build and open the viewer page from what this machine
    staged, so there is a response left to build after this returns.
    """

    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim",)
    CAPABILITY_ID_PREFIX: ClassVar[str] = (
        "org.infobim.3d.plugin.capability.transformation.target."
    )

    STATECHART_PACKAGE: ClassVar[str] = "infobim._3d.plugin.machine.three_d_view"
    STATECHART_FILE: ClassVar[str] = "standard_three_d_view.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "ThreeDViewProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: ThreeDViewStateEvaluatorPort = (
            ThreeDViewStateEvaluatorAdapter()
        )
        self._active_state: Optional[ThreeDViewProcessStatePort] = None
        self._observed_state: Optional[ThreeDViewProcessStatePort] = None

    @property
    def current_state(self) -> ThreeDViewProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ThreeDViewProcessStatePort:
        """
        The state this launch is in, read once per machine step.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: ThreeDViewProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: ThreeDViewProcessStatePort,
    ) -> None:
        observed_state: ThreeDViewProcessStatePort = self.observed_state
        if observed_state == to_state:
            return

        self._logger.log_info(
            f"InfoBIM 3D view transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = f"{self.CAPABILITY_ID_PREFIX}{to_state.value.strip('_')}"
        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"InfoBIM 3D view capability not found for state: "
                f"{to_state.value} (id: {capability_id})"
            )

        capability: CapabilityPort = capability_type()
        try:
            CapabilityExecutor.execute(
                capability,
                self._context,
                StrategyParamResolver(ResolverLoader()),
            )
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: ThreeDViewProcessStatePort,
        to_state: ThreeDViewProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self.observed_state == to_state

    def execute(self) -> List[str]:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ThreeDViewProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._statechart_file_path(),
        )
        return worker.work()

    def bind_active_state(self, state: ThreeDViewProcessStatePort) -> None:
        self._active_state = state
        self._forget_observed_state()

    def _forget_observed_state(self) -> None:
        """
        Drop the reading, so the next one goes back to disk.
        """
        self._observed_state = None

    def _statechart_file_path(self) -> Path:
        return StatechartLocator.locate(
            self.STATECHART_PACKAGE,
            self.STATECHART_FILE,
        )
