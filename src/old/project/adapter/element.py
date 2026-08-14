import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from infobim.project.domain.machine.import_state import ElementImportProcessState
from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.adapter.updated import check_project_container_updated
from infobim.shared.adapter.loader import CapabilityLoader
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort
from ontobdc.storage.adapter.bootstrap import get_container_crate_metadata_file_path


class ElementImportStateEvaluatorAdapter:
    def __init__(self, context: CliContextPort):
        self._context: CliContextPort = context

    @property
    def step_repository(self) -> ElementImportStepRepository:
        cached_repository: object = self._context.get_parameter_value("element_import_step_repository")
        if isinstance(cached_repository, ElementImportStepRepository):
            return cached_repository

        repository = ElementImportStepRepository(
            container_path=str(self._context.get_parameter_value("container_path")),
            source_path=str(self._context.get_parameter_value("import_path")),
            element_name=str(self._context.get_parameter_value("element_name")),
        )
        self._context.set_parameter_value("element_import_step_repository", repository)
        return repository

    def evaluate(self) -> ElementImportProcessState:
        container_path: str = str(self._context.get_parameter_value("container_path")).strip()
        root_path: str = str(self._context.root_path).strip()
        if not container_path or check_project_container_updated(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            return ElementImportProcessState.UNDEFINED

        self._context.set_parameter_value(
            "crate_file",
            str(get_container_crate_metadata_file_path(Path(container_path).expanduser().resolve())),
        )

        for state in [
            ElementImportProcessState.LINKED,
            ElementImportProcessState.GENERATED,
            ElementImportProcessState.INSTANTIATED,
            ElementImportProcessState.INSTANCE_PARSED,
            ElementImportProcessState.INSTANCE_DRAFTED,
            ElementImportProcessState.SEMANTICIZED,
            ElementImportProcessState.GROUNDED,
            ElementImportProcessState.ARRANGED,
            ElementImportProcessState.LOCALIZED,
            ElementImportProcessState.SPATIALIZED,
            ElementImportProcessState.EXTRACTED,
            ElementImportProcessState.IDENTIFIED,
        ]:
            if self.is_state_valid(state):
                return state

            if self.step_repository.exists(state):
                self.discard_state_artifact(state)

        return ElementImportProcessState.UPDATED

    def is_state_valid(self, state: ElementImportProcessState) -> bool:
        return self.get_invalid_state_reason(state) is None

    def get_invalid_state_reason(self, state: ElementImportProcessState) -> Optional[str]:
        if not self.step_repository.exists(state):
            return f"Missing artifact for state {state.value}."

        if state == ElementImportProcessState.SEMANTICIZED:
            return self._get_semanticized_invalid_reason()

        if state == ElementImportProcessState.INSTANCE_DRAFTED:
            return self._get_instance_drafted_invalid_reason()

        if state == ElementImportProcessState.INSTANTIATED:
            return self._get_instantiated_invalid_reason()

        if state == ElementImportProcessState.GENERATED:
            return self._get_generated_invalid_reason()

        if state == ElementImportProcessState.LINKED:
            return self._get_linked_invalid_reason()

        return None

    def discard_state_artifact(self, state: ElementImportProcessState) -> bool:
        return self.step_repository.delete(state)

    def _get_semanticized_invalid_reason(self) -> Optional[str]:
        semanticized_payload: Dict[str, Any] = self._load_artifact_payload(ElementImportProcessState.SEMANTICIZED)
        summary: Dict[str, Any] = self._read_summary(semanticized_payload)
        header_count: int = self._read_summary_count(summary, "header_count")
        semanticized_header_count: int = self._read_summary_count(summary, "semanticized_header_count")
        if header_count <= 0:
            return "The semanticized artifact does not expose any grounded headers."
        if semanticized_header_count <= 0:
            return "The semanticized artifact did not map any grounded header to a semantic field."
        return None

    def _get_instance_drafted_invalid_reason(self) -> Optional[str]:
        instance_drafted_payload: Dict[str, Any] = self._load_artifact_payload(ElementImportProcessState.INSTANCE_DRAFTED)
        summary: Dict[str, Any] = self._read_summary(instance_drafted_payload)
        row_group_count: int = self._read_summary_count(summary, "row_group_count")
        ifc_instance_count: int = self._read_summary_count(summary, "ifc_instance_count")
        mapped_field_count: int = self._read_summary_count(summary, "mapped_field_count")
        if row_group_count <= 0:
            return "The instance-drafted artifact does not contain any row group."
        if ifc_instance_count <= 0:
            return "The instance-drafted artifact did not draft any IFC instance."
        if mapped_field_count <= 0:
            return "The instance-drafted artifact did not map any semanticized field to an IFC facade field."
        return None

    def _get_instantiated_invalid_reason(self) -> Optional[str]:
        instantiated_payload: Dict[str, Any] = self._load_artifact_payload(
            ElementImportProcessState.INSTANTIATED,
        )
        summary: Dict[str, Any] = self._read_summary(instantiated_payload)
        ifc_task_count: int = self._read_summary_count(summary, "ifc_task_count")
        if ifc_task_count <= 0:
            return "The instantiated artifact did not materialize any IfcTask IFCJSON instance."

        instances: Any = instantiated_payload.get("ifcjson_instances")
        if not isinstance(instances, list) or len(instances) <= 0:
            return "The instantiated artifact does not expose any IFCJSON instance list."

        return None

    def _get_generated_invalid_reason(self) -> Optional[str]:
        generated_payload: Dict[str, Any] = self._load_artifact_payload(
            ElementImportProcessState.GENERATED,
        )
        summary: Dict[str, Any] = self._read_summary(generated_payload)
        generated_row_count: int = self._read_summary_count(summary, "generated_row_count")
        if generated_row_count <= 0:
            return "The generated artifact did not materialize any worksheet row."

        workbook_path: str = str(generated_payload.get("workbook_path") or "").strip()
        if not workbook_path:
            return "The generated artifact does not expose the workbook path."
        if not Path(workbook_path).exists():
            return f"The generated workbook does not exist: {workbook_path}"

        return None

    def _get_linked_invalid_reason(self) -> Optional[str]:
        linkset_payload: Dict[str, Any] = self._load_artifact_payload(
            ElementImportProcessState.LINKED,
        )
        summary: Dict[str, Any] = self._read_summary(linkset_payload)
        link_count: int = self._read_summary_count(summary, "link_count")
        if link_count <= 0:
            return "The linkset artifact did not materialize any ICDD link."

        linkset_path: str = str(linkset_payload.get("linkset_path") or "").strip()
        if not linkset_path:
            return "The linkset artifact does not expose the payload triple path."
        if not Path(linkset_path).exists():
            return f"The linkset payload file does not exist: {linkset_path}"

        return None

    def _load_artifact_payload(self, state: ElementImportProcessState) -> Dict[str, Any]:
        resource = self.step_repository.reload(state)
        payload: Any = json.loads(str(resource.content))
        if not isinstance(payload, dict):
            raise ValueError(f"The artifact for state {state.value} must be a JSON object.")
        return payload

    def _read_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        summary: Any = payload.get("summary")
        if not isinstance(summary, dict):
            return {}
        return dict(summary)

    def _read_summary_count(self, summary: Dict[str, Any], key: str) -> int:
        value: Any = summary.get(key)
        if isinstance(value, bool):
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        return 0


class ElementImportStateTransitionHandler:
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator = ElementImportStateEvaluatorAdapter(context=context)
        self._active_state: Optional[ElementImportProcessState] = None

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def step_repository(self) -> ElementImportStepRepository:
        return self._state_evaluator.step_repository

    @property
    def current_state(self) -> ElementImportProcessState:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ElementImportProcessState:
        return self._state_evaluator.evaluate()

    @property
    def state_sequence(self) -> List[ElementImportProcessState]:
        return list(ElementImportProcessState)

    def can_transit_to(self, to_state: ElementImportProcessState) -> bool:
        state_sequence: List[ElementImportProcessState] = self.state_sequence
        observed_state: ElementImportProcessState = self.observed_state
        current_state: ElementImportProcessState = self.current_state
        if to_state not in state_sequence or observed_state not in state_sequence or current_state not in state_sequence:
            return False

        current_index: int = state_sequence.index(current_state)
        observed_index: int = state_sequence.index(observed_state)
        target_index: int = state_sequence.index(to_state)
        if observed_index > current_index:
            return current_index < target_index <= observed_index

        return target_index == current_index + 1

    def perform_state_transition(self, to_state: ElementImportProcessState) -> None:
        if self.observed_state == to_state:
            return

        capability_id_by_state: Dict[ElementImportProcessState, str] = {
            ElementImportProcessState.UPDATED:
                "org.infobim.project.plugin.capability.transformation.target.updated",
            ElementImportProcessState.IDENTIFIED:
                "org.infobim.project.plugin.capability.transformation.target.identified",
            ElementImportProcessState.EXTRACTED:
                "org.infobim.project.plugin.capability.transformation.target.extracted",
            ElementImportProcessState.SPATIALIZED:
                "org.infobim.project.plugin.capability.transformation.target.spatialized",
            ElementImportProcessState.LOCALIZED:
                "org.infobim.project.plugin.capability.transformation.target.localized",
            ElementImportProcessState.ARRANGED:
                "org.infobim.project.plugin.capability.transformation.target.arranged",
            ElementImportProcessState.GROUNDED:
                "org.infobim.project.plugin.capability.transformation.target.grounded",
            ElementImportProcessState.SEMANTICIZED:
                "org.infobim.project.plugin.capability.transformation.target.semanticized",
            ElementImportProcessState.INSTANCE_DRAFTED:
                "org.infobim.project.plugin.capability.transformation.target.instance_drafted",
            ElementImportProcessState.INSTANCE_PARSED:
                "org.infobim.project.plugin.capability.transformation.target.instance_parsed",
            ElementImportProcessState.INSTANTIATED:
                "org.infobim.project.plugin.capability.transformation.target.instantiated",
            ElementImportProcessState.GENERATED:
                "org.infobim.project.plugin.capability.transformation.target.generated",
            ElementImportProcessState.LINKED:
                "org.infobim.project.plugin.capability.transformation.target.linked",
        }
        capability_id: Optional[str] = capability_id_by_state.get(to_state)
        if not capability_id:
            raise ValueError(f"Element import capability not found for state: {to_state.value}")

        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"Element import capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: ElementImportProcessState,
        to_state: ElementImportProcessState,
    ) -> bool:
        if from_state == to_state:
            return False
        if to_state == ElementImportProcessState.UPDATED:
            self.bind_active_state(to_state)
            return self.observed_state != ElementImportProcessState.UNDEFINED
        invalid_state_reason: Optional[str] = self._state_evaluator.get_invalid_state_reason(to_state)
        if invalid_state_reason is not None:
            self._state_evaluator.discard_state_artifact(to_state)
            raise ValueError(
                f"Invalid transition to {to_state.value}: {invalid_state_reason}",
            )
        self.bind_active_state(to_state)
        return self._state_evaluator.is_state_valid(to_state)

    def bind_active_state(self, state: ElementImportProcessState) -> None:
        self._active_state = state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ElementImportProcessState,
            state_context_name="ElementImportProcessState",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        worker.work()
        visited_states: List[str] = self._materialized_states()
        current_state: ElementImportProcessState = self.observed_state
        self.bind_active_state(current_state)
        return self._build_final_response(visited_states)

    def _build_final_response(self, visited_states: List[str]) -> CommandResponse:
        content: Dict[str, object] = {
            "project_id": self._context.get_parameter_value("project_id"),
            "element_name": self._context.get_parameter_value("element_name"),
            "element_uri": self._context.get_parameter_value("element_uri"),
            "entity_uri": self._context.get_parameter_value("entity_uri"),
            "import_path": self._context.get_parameter_value("import_path"),
            "semantic": self._context.get_parameter_value("semantic"),
            "document_language_code": self._context.get_parameter_value("document_language_code"),
            "document_language_score": self._context.get_parameter_value("document_language_score"),
            "container_path": self._context.get_parameter_value("container_path"),
            "crate_file": self._context.get_parameter_value("crate_file"),
            "current_state": self.observed_state.value,
            "visited_states": visited_states,
            "step_dir": str(self.step_repository.step_dir),
            "statechart_file": str(self._get_statechart_file_path()),
            "artifacts": {
                "identified": self._artifact_path(ElementImportProcessState.IDENTIFIED),
                "extracted": self._artifact_path(ElementImportProcessState.EXTRACTED),
                "spatialized": self._artifact_path(ElementImportProcessState.SPATIALIZED),
                "localized": self._artifact_path(ElementImportProcessState.LOCALIZED),
                "arranged": self._artifact_path(ElementImportProcessState.ARRANGED),
                "grounded": self._artifact_path(ElementImportProcessState.GROUNDED),
                "semanticized": self._artifact_path(ElementImportProcessState.SEMANTICIZED),
                "instance_drafted": self._artifact_path(ElementImportProcessState.INSTANCE_DRAFTED),
                "instance_parsed": self._artifact_path(ElementImportProcessState.INSTANCE_PARSED),
                "instantiated": self._artifact_path(ElementImportProcessState.INSTANTIATED),
                "generated": self._artifact_path(ElementImportProcessState.GENERATED),
                "linked": self._artifact_path(ElementImportProcessState.LINKED),
            },
        }

        generated_workbook_path: Optional[str] = self._generated_workbook_path()
        if generated_workbook_path:
            content["artifacts"]["generated_document"] = generated_workbook_path
        linkset_payload_path: Optional[str] = self._linked_payload_path()
        if linkset_payload_path:
            content["artifacts"]["linkset_document"] = linkset_payload_path

        if self.observed_state == ElementImportProcessState.UNDEFINED:
            return ExceptionCommandResponse(
                title="Project Import Undefined",
                description="The target project container is not updated yet, so the import flow could not start.",
                content=content,
            )

        return CommandResponse(
            title="Project Import State",
            description="Resolved existing project import artifacts for the selected project element source.",
            content=content,
        )

    def _materialized_states(self) -> List[str]:
        states: List[str] = [ElementImportProcessState.UNDEFINED.value]
        for state in [
            ElementImportProcessState.UPDATED,
            ElementImportProcessState.IDENTIFIED,
            ElementImportProcessState.EXTRACTED,
            ElementImportProcessState.SPATIALIZED,
            ElementImportProcessState.LOCALIZED,
            ElementImportProcessState.ARRANGED,
            ElementImportProcessState.GROUNDED,
            ElementImportProcessState.SEMANTICIZED,
            ElementImportProcessState.INSTANCE_DRAFTED,
            ElementImportProcessState.INSTANCE_PARSED,
            ElementImportProcessState.INSTANTIATED,
            ElementImportProcessState.GENERATED,
            ElementImportProcessState.LINKED,
        ]:
            if state == ElementImportProcessState.UPDATED:
                if self.observed_state != ElementImportProcessState.UNDEFINED:
                    states.append(state.value)
                continue

            if self._state_evaluator.is_state_valid(state):
                states.append(state.value)

        return states

    def _artifact_path(self, state: ElementImportProcessState) -> Optional[str]:
        if not self._state_evaluator.is_state_valid(state):
            return None

        return str(self.step_repository.reload(state).path)

    def _get_statechart_file_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "domain" / "machine" / "standard_element_import.yaml"

    def _generated_workbook_path(self) -> Optional[str]:
        if not self._state_evaluator.is_state_valid(ElementImportProcessState.GENERATED):
            return None

        generated_payload: Dict[str, Any] = self._state_evaluator._load_artifact_payload(ElementImportProcessState.GENERATED)
        workbook_path: str = str(generated_payload.get("workbook_path") or "").strip()
        return workbook_path or None

    def _linked_payload_path(self) -> Optional[str]:
        if not self._state_evaluator.is_state_valid(ElementImportProcessState.LINKED):
            return None

        linkset_payload: Dict[str, Any] = self._state_evaluator._load_artifact_payload(ElementImportProcessState.LINKED)
        linkset_path: str = str(linkset_payload.get("linkset_path") or "").strip()
        return linkset_path or None
