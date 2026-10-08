from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Optional
import importlib

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

from infobim.cli.adapter.shortcut import ServeShortcut
from infobim.cli.plugin.machine.init.port import (
    InfoBIMInitProcessStatePort,
    InfoBIMInitStateEvaluatorPort,
    InfoBIMInitStateTransitionHandlerPort,
)
from infobim.cli.plugin.machine.init.state import InfoBIMInitProcessState
from infobim.cli.plugin.machine.init.statechart import InfoBIMInitStatechart


class InfoBIMInitStateEvaluatorAdapter(InfoBIMInitStateEvaluatorPort):
    """
    Reads the project on disk and reports the state it is already in.

    The states come from the statechart, in order, and each one resolves its
    check by the ``is_<state>.check.main`` convention.
    """

    CHECK_MODULE_PREFIX: ClassVar[str] = "infobim.cli.plugin.check.is_"

    def evaluate(self, context: CliContextPort) -> InfoBIMInitProcessStatePort:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        reached_state: InfoBIMInitProcessStatePort = InfoBIMInitProcessState.UNDEFINED
        state_name: str
        for state_name in InfoBIMInitStatechart.sequence()[1:]:
            state: InfoBIMInitProcessStatePort = InfoBIMInitProcessState.get_state(
                state_name
            )
            if self._check_for(state)(root_path=str(root_path)) != 0:
                return reached_state

            reached_state = state

        return reached_state

    @classmethod
    def _check_for(cls, state: InfoBIMInitProcessStatePort) -> Callable[..., int]:
        module_name: str = f"{cls.CHECK_MODULE_PREFIX}{state.value.strip('_')}.check"
        check: Any = getattr(importlib.import_module(module_name), "main")
        if not callable(check):
            raise TypeError(
                f"InfoBIM init state check is not callable: {module_name}.main"
            )

        return check


class InfoBIMInitStateTransitionHandler(InfoBIMInitStateTransitionHandlerPort):
    """
    Drive the InfoBIM init statechart.

    It knows only its own states. It is meant to run once the OntoBDC project
    it works on is initialized, which is something whoever composes it
    guarantees, not something it assumes by reaching into OntoBDC.
    """

    STATE_CONTEXT_NAME: ClassVar[str] = "InfoBIMInitProcessStatePort"
    CAPABILITY_ID_PREFIX: ClassVar[str] = (
        "org.infobim.cli.plugin.capability.transformation.target."
    )
    FINAL_STATE: ClassVar[InfoBIMInitProcessStatePort] = (
        InfoBIMInitProcessState.SERVE_SHORTCUT_READY
    )

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: InfoBIMInitStateEvaluatorPort = (
            InfoBIMInitStateEvaluatorAdapter()
        )
        self._capability_loader: CapabilityLoader = CapabilityLoader(
            root_packages=("infobim",)
        )
        self._active_state: Optional[InfoBIMInitProcessStatePort] = None
        self._observed_state: Optional[InfoBIMInitProcessStatePort] = None

    @property
    def current_state(self) -> InfoBIMInitProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> InfoBIMInitProcessStatePort:
        """
        The state the project is in on disk, read again after every capability.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: InfoBIMInitProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: InfoBIMInitProcessStatePort) -> None:
        if self._rank(self.observed_state) >= self._rank(to_state):
            return

        self._logger.log_info(
            f"InfoBIM init transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = f"{self.CAPABILITY_ID_PREFIX}{to_state.value.strip('_')}"
        capability_type: Any = self._capability_loader.get(capability_id)
        if capability_type is None:
            raise ValueError(f"InfoBIM init capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        try:
            CapabilityExecutor.execute(capability, self._context)
        finally:
            self._observed_state = None

    def validate_state_transition(
        self,
        from_state: InfoBIMInitProcessStatePort,
        to_state: InfoBIMInitProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._rank(self.observed_state) >= self._rank(to_state)

    def bind_active_state(self, state: InfoBIMInitProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=InfoBIMInitProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=InfoBIMInitStatechart.path(),
        )
        try:
            visited_states: List[str] = worker.work()
        except CodeEvaluationError as error:
            if isinstance(error.__cause__, Exception):
                raise error.__cause__ from None
            raise

        self._observed_state = None
        reached_state: InfoBIMInitProcessStatePort = self.observed_state
        if reached_state != self.FINAL_STATE:
            raise RuntimeError(
                f"InfoBIM init stopped at state '{reached_state.value}' "
                f"instead of '{self.FINAL_STATE.value}'."
            )

        root_path: Path = StorageBootstrap.get_init_root_path(context=self._context)
        content: Dict[str, Any] = {
            "root_path": str(root_path),
            "current_state": reached_state.value,
            "visited_states": visited_states,
            "serve_shortcut": ServeShortcut(root_path).describe(),
        }
        self._logger.log_notice("InfoBIM init finished successfully.")
        return CommandResponse(
            title="Init",
            description="InfoBIM initialization executed successfully.",
            content=content,
        )

    @staticmethod
    def _rank(state: InfoBIMInitProcessStatePort) -> int:
        return InfoBIMInitStatechart.sequence().index(state.value.strip("_"))
