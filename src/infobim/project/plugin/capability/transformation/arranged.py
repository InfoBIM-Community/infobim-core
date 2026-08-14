import json
from typing import Any, Dict, Optional

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.adapter.strategy import StrategyCapabilityLoader
from infobim.project.domain.machine.import_state import ElementImportProcessState
from infobim.project.plugin.capability.strategy import StrategyCapability
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import CapabilityExecutor, TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class ArrangedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.arranged",
        version="1.0.0",
        name="Project element import transformation to Arranged",
        description="Materialize the arranged placeholder artifact for the project import flow.",
        author=["TRAE"],
        tags=["project", "import", "arranged"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Arranged"

    def description(self, lang: str = "en") -> str:
        return "Materialize the arranged placeholder artifact for the project import flow."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        spatialized_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.SPATIALIZED)
        spatialized_payload: Dict[str, Any] = json.loads(str(spatialized_resource.content))
        spatial_structure: Dict[str, Any] = dict(spatialized_payload.get("spatial_structure", {}))
        element_name: str = str(context.get_parameter_value("element_name")).strip()
        document_kind: str = self._resolve_document_kind(spatial_structure=spatial_structure)
        selected_strategy: StrategyCapability = self._resolve_strategy(
            document_kind=document_kind,
            element_name=element_name,
            context=context,
        )
        strategy_result: Dict[str, Any] = CapabilityExecutor.execute(selected_strategy, context)
        context.set_parameter_value("arrangement_strategy_id", selected_strategy.metadata.id)
        context.set_parameter_value("arrangement_strategy_name", selected_strategy.metadata.name)

        arranged_path = step_repository.write_text_file(
            state=ElementImportProcessState.ARRANGED,
            content=json.dumps(
                {
                    "document_kind": document_kind,
                    "resource": spatialized_payload.get("resource", {}),
                    "selected_strategy": {
                        "id": selected_strategy.metadata.id,
                        "name": selected_strategy.metadata.name,
                    },
                    "spatial_structure": spatial_structure,
                    "strategy_result": strategy_result,
                },
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            ),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(arranged_path))
        return {
            "resulting_state": ElementImportProcessState.ARRANGED,
            "path": str(arranged_path),
            "document_kind": document_kind,
            "selected_strategy": selected_strategy.metadata.id,
        }

    def _resolve_document_kind(self, spatial_structure: Dict[str, Any]) -> str:
        if bool(spatial_structure.get("is_tabular")):
            return "tabular"

        return "unstructured"

    def _resolve_strategy(
        self,
        document_kind: str,
        element_name: str,
        context: CliContextPort,
    ) -> StrategyCapability:
        matching_strategies: list[StrategyCapability] = []
        for capability_type in StrategyCapabilityLoader().get_all():
            if not isinstance(capability_type, type):
                continue
            if not issubclass(capability_type, StrategyCapability):
                continue

            strategy: StrategyCapability = capability_type()
            if strategy.matches(document_kind=document_kind, element_name=element_name, context=context):
                matching_strategies.append(strategy)

        if not matching_strategies:
            raise ValueError(
                f"No arrangement strategy matched document_kind='{document_kind}' and element_name='{element_name}'."
            )

        return max(
            matching_strategies,
            key=lambda strategy: strategy.priority(
                document_kind=document_kind,
                element_name=element_name,
                context=context,
            ),
        )
