from pathlib import Path
from typing import Any, ClassVar, List, Optional, Set, Tuple, Type

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim.project.plugin.machine.ifc_element_list.port import (
    IfcElementListProcessStatePort,
    IfcElementListStateTransitionHandlerPort,
)
from infobim.project.plugin.machine.ifc_element_list.state import IfcElementListProcessState


class IfcElementListStateTransitionHandler(IfcElementListStateTransitionHandlerPort):
    """
    Drives the listing of the IFC elements of a project.

    Nothing of the listing is kept on disk, so the machine always starts
    from the beginning and a state is reached only by having just
    performed it. Each state's capability is resolved by id through the
    CapabilityLoader, never imported concretely.
    """

    CAPABILITY_ID_PREFIX: ClassVar[str] = (
        "org.infobim.project.plugin.capability.transformation.target."
    )
    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim",)
    STATECHART_PACKAGE: ClassVar[str] = "infobim.project.plugin.machine.ifc_element_list"
    STATECHART_FILE: ClassVar[str] = "standard_ifc_element_list.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "IfcElementListProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._active_state: IfcElementListProcessStatePort = IfcElementListProcessState.UNDEFINED
        self._performed: Set[IfcElementListProcessStatePort] = set()

    @property
    def current_state(self) -> IfcElementListProcessStatePort:
        return self._active_state

    def can_transit_to(self, to_state: IfcElementListProcessStatePort) -> bool:
        return to_state not in self._performed

    def perform_state_transition(self, to_state: IfcElementListProcessStatePort) -> None:
        self._logger.log_info(
            f"InfoBIM IFC element list transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = f"{self.CAPABILITY_ID_PREFIX}{to_state.value.strip('_')}"
        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"InfoBIM IFC element list capability not found for state: "
                f"{to_state.value} (id: {capability_id})"
            )

        CapabilityExecutor.execute(capability_type(), self._context)
        self._performed.add(to_state)

    def validate_state_transition(
        self,
        from_state: IfcElementListProcessStatePort,
        to_state: IfcElementListProcessStatePort,
    ) -> bool:
        return from_state != to_state and to_state in self._performed

    def bind_active_state(self, state: IfcElementListProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=IfcElementListProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=StatechartLocator.locate(
                self.STATECHART_PACKAGE,
                self.STATECHART_FILE,
            ),
        )
        worker.work()

        project_path: Path = Path(str(self._context.get_parameter_value("container_path"))).expanduser().resolve()
        datasets: List[Any] = self._context.get_parameter_value("ifc_element_datasets") or []
        count: int = sum(len(dataset["entities"]) for dataset in datasets)

        return CommandResponse(
            title="Container Entities",
            description=(
                f"{count} IFC elements in {len(datasets)} IFC models of the "
                f"project «{project_path.name}»."
            ),
            content={"datasets": datasets},
        )
