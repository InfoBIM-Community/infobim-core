from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from infobim.a3.domain.machine.state import A3LlmSuggestionProcessState
from infobim.a3.domain.port.machine import (
    A3LlmSuggestionProcessStatePort,
    A3LlmSuggestionStateEvaluatorPort,
    A3LlmSuggestionStateTransitionHandlerPort,
)
from infobim.a3.plugin.capability.transformation.suggestion_pipeline import (
    A3ContainerBoundCapability,
    A3FilesEnumeratedCapability,
    A3LlmEvaluatedCapability,
    A3RoCrateLoadedCapability,
    A3SuggestionsSavedCapability,
    _bound_context,
)
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort


_STATE_CAPABILITIES: Dict[A3LlmSuggestionProcessState, Type[CapabilityPort]] = {
    A3LlmSuggestionProcessState.CONTAINER_BOUND: A3ContainerBoundCapability,
    A3LlmSuggestionProcessState.RO_CRATE_LOADED: A3RoCrateLoadedCapability,
    A3LlmSuggestionProcessState.FILES_ENUMERATED: A3FilesEnumeratedCapability,
    A3LlmSuggestionProcessState.LLM_EVALUATED: A3LlmEvaluatedCapability,
    A3LlmSuggestionProcessState.SUGGESTIONS_SAVED: A3SuggestionsSavedCapability,
}


class A3LlmSuggestionStateEvaluatorAdapter(A3LlmSuggestionStateEvaluatorPort):
    """Evaluate how far the persisted A3 suggestion state has already reached.

    Unlike the InfoBIM project / Surface pipelines, this evaluator is
    intentionally lightweight: it only looks at the runtime context and the
    on-disk suggestion state artifact so re-runs of the command are safe and
    cumulative (later stages are skipped when their outputs already exist).
    """

    @property
    def process_state_class(self) -> Type[A3LlmSuggestionProcessStatePort]:
        return A3LlmSuggestionProcessState

    @property
    def state_sequence(self) -> List[A3LlmSuggestionProcessStatePort]:
        return list(A3LlmSuggestionProcessState)

    def evaluate(self, context: CliContextPort) -> A3LlmSuggestionProcessStatePort:
        try:
            bound = _bound_context(context)
        except Exception:
            return A3LlmSuggestionProcessState.UNDEFINED
        container_path: Path = bound["container_path"]
        from infobim.a3.domain.model.suggestion import state_artifact_path

        artifact: Path = state_artifact_path(container_path)
        if not artifact.is_file():
            return A3LlmSuggestionProcessState.UNDEFINED
        try:
            payload: Any = __import__("json").loads(
                artifact.read_text(encoding="utf-8")
            )
        except Exception:
            return A3LlmSuggestionProcessState.UNDEFINED
        if not isinstance(payload, dict):
            return A3LlmSuggestionProcessState.UNDEFINED
        visited: Any = payload.get("visited_states")
        order: List[A3LlmSuggestionProcessStatePort] = self.state_sequence
        latest: A3LlmSuggestionProcessStatePort = A3LlmSuggestionProcessState.UNDEFINED
        if isinstance(visited, list):
            for value in visited:
                try:
                    parsed: A3LlmSuggestionProcessState = (
                        A3LlmSuggestionProcessState(str(value))
                    )
                except Exception:
                    continue
                if order.index(parsed) > order.index(latest):
                    latest = parsed
        current: Any = payload.get("current_state")
        if isinstance(current, str):
            try:
                parsed_current: A3LlmSuggestionProcessState = (
                    A3LlmSuggestionProcessState(str(current))
                )
                if order.index(parsed_current) > order.index(latest):
                    latest = parsed_current
            except Exception:
                pass
        return latest


class A3LlmSuggestionStateTransitionHandler(
    A3LlmSuggestionStateTransitionHandlerPort
):
    """Orchestrate the A3 LLM file-suggestion statechart."""

    def __init__(
        self,
        context: CliContextPort,
        state_evaluator: Optional[A3LlmSuggestionStateEvaluatorPort] = None,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._state_evaluator = state_evaluator or A3LlmSuggestionStateEvaluatorAdapter()
        self._logger = logger or NullLogRepository()
        self._active_state: Optional[A3LlmSuggestionProcessStatePort] = None
        self._last_transition_state: Optional[A3LlmSuggestionProcessStatePort] = None

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        bound = _bound_context(self._context)
        return Path(bound["container_path"])

    @property
    def observed_state(self) -> A3LlmSuggestionProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def current_state(self) -> A3LlmSuggestionProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def state_sequence(self) -> List[A3LlmSuggestionProcessStatePort]:
        return list(A3LlmSuggestionProcessState)

    def can_transit_to(self, to_state: A3LlmSuggestionProcessStatePort) -> bool:
        sequence: List[A3LlmSuggestionProcessStatePort] = self.state_sequence
        current: A3LlmSuggestionProcessStatePort = self.current_state
        if current not in sequence or to_state not in sequence:
            return False
        current_index: int = sequence.index(current)
        if current_index + 1 >= len(sequence):
            return False
        return sequence[current_index + 1] == to_state

    def perform_state_transition(self, to_state: A3LlmSuggestionProcessStatePort) -> None:
        self._logger.log_info(
            f"A3 LLM suggestion transition: {self.current_state.value} -> {to_state.value}"
        )
        capability_type: Optional[Type[CapabilityPort]] = _STATE_CAPABILITIES.get(
            A3LlmSuggestionProcessState(to_state)
        )
        if capability_type is None:
            raise ValueError(
                f"No A3 LLM suggestion capability mapped to state: {to_state.value}"
            )
        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)
        self._last_transition_state = to_state

    def validate_state_transition(
        self,
        from_state: A3LlmSuggestionProcessStatePort,
        to_state: A3LlmSuggestionProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False
        if self._last_transition_state == to_state:
            return True
        try:
            observed = self.observed_state
            sequence = self.state_sequence
            if observed not in sequence or to_state not in sequence:
                return False
            return sequence.index(observed) >= sequence.index(to_state)
        except Exception:
            return False

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=A3LlmSuggestionProcessState,
            state_context_name="A3LlmSuggestionProcessState",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states: List[str] = worker.work()
        payload: Dict[str, Any] = {
            "project_id": self._context.get_parameter_value("project_id"),
            "project_path": self._context.get_parameter_value("project_path"),
            "container_path": str(self.target_path),
            "element_id": self._context.get_parameter_value("target_element_id"),
            "dimension_property": self._context.get_parameter_value(
                "target_dimension_property"
            ),
            "current_state": self.current_state.value,
            "visited_states": visited_states,
        }
        llm_results: Any = self._context.get_parameter_value(
            "a3_llm_evaluation_results"
        )
        if isinstance(llm_results, dict):
            payload.update(
                {
                    "total_files": llm_results.get("total_files"),
                    "accepted_count": llm_results.get("accepted_count"),
                    "rejected_count": llm_results.get("rejected_count"),
                    "accepted": llm_results.get("accepted"),
                }
            )
        return CommandResponse(
            title="A3 File Suggestions",
            description=(
                "LLM-driven file-suggestion pipeline finished. Files accepted "
                "by the model have been persisted to the container so the "
                "Suggested Files screen can render them for the target "
                "element and dimension-property."
            ),
            content=payload,
        )

    def _get_statechart_file_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "domain"
            / "machine"
            / "standard_llm_suggestion.yaml"
        )

    def bind_active_state(self, state: A3LlmSuggestionProcessStatePort) -> None:
        self._active_state = state
