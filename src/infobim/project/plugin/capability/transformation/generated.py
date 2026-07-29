import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from infobim.shared.adapter.entity_workbook import (
    EntityWorkbookAdapter,
    EntityWorkbookArtifact,
    EntityWorkbookField,
)
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class GeneratedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.generated",
        version="1.0.0",
        name="Project element import transformation to Generated",
        description="Generate an Excel workbook from the instantiated IfcTask payload.",
        author=["TRAE"],
        tags=["project", "import", "generated", "xlsx", "ifctask"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Generated"

    def description(self, lang: str = "en") -> str:
        return "Generate an Excel workbook from the instantiated IfcTask payload."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        instantiated_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.INSTANTIATED)
        instantiated_payload: Dict[str, Any] = json.loads(str(instantiated_resource.content))
        ifcjson_instances: List[Dict[str, Any]] = list(instantiated_payload.get("ifcjson_instances", []))
        if not ifcjson_instances:
            raise ValueError("The instantiated artifact does not expose any IfcTask payload to generate the workbook.")

        output_dir: Path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve() / "payload" / "document"
        ontobdc_dir: Path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve() / ".__ontobdc__"
        adapter = EntityWorkbookAdapter()
        fields: List[EntityWorkbookField] = [
            EntityWorkbookField("GlobalId"),
            EntityWorkbookField("Identification"),
            EntityWorkbookField("Name"),
            EntityWorkbookField("IsMilestone", "boolean"),
            EntityWorkbookField("TaskTime"),
        ]
        records: List[Dict[str, Any]] = [
            {
                "GlobalId": instance_payload.get("GlobalId"),
                "Identification": instance_payload.get("Identification"),
                "Name": instance_payload.get("Name"),
                "IsMilestone": instance_payload.get("IsMilestone"),
                "TaskTime": self._task_time_value(
                    dict(instance_payload.get("TaskTime", {}))
                ),
            }
            for instance_payload in ifcjson_instances
        ]
        artifact: EntityWorkbookArtifact = adapter.generate(
            output_dir=output_dir,
            workbook_name=self._build_workbook_name(step_repository),
            worksheet_name="IfcTask",
            fields=fields,
            records=records,
            datapackage_path=ontobdc_dir / "datapackage.json",
            package_name=self._build_datapackage_name(step_repository),
            resource_name="ifc_task",
            primary_key=["GlobalId"],
        )

        generated_payload: Dict[str, Any] = {
            "source_state": ElementImportProcessState.INSTANTIATED.value,
            "source_artifact": str(instantiated_resource.path),
            "datapackage_path": str(artifact.datapackage_path),
            "workbook_path": str(artifact.workbook_path),
            "workbook_format": "xlsx",
            "worksheet_name": artifact.worksheet_name,
            "validation": artifact.validation,
            "summary": {
                "generated_row_count": artifact.generated_row_count,
                "ifc_task_count": len(ifcjson_instances),
            },
        }
        generated_artifact_path: Path = step_repository.write_text_file(
            state=ElementImportProcessState.GENERATED,
            content=json.dumps(generated_payload, ensure_ascii=False, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(generated_artifact_path))
        context.set_parameter_value(
            "generated_workbook_path",
            str(artifact.workbook_path),
        )
        return {
            "resulting_state": ElementImportProcessState.GENERATED,
            "path": str(generated_artifact_path),
            "datapackage_path": str(artifact.datapackage_path),
            "workbook_path": str(artifact.workbook_path),
            "generated_row_count": artifact.generated_row_count,
        }

    def _build_workbook_name(self, step_repository: ElementImportStepRepository) -> str:
        source_stem: str = re.sub(r"[^0-9A-Za-z_-]+", "_", step_repository.source_path.stem).strip("_")
        element_name: str = re.sub(r"[^0-9A-Za-z_-]+", "_", step_repository.element_name).strip("_")
        if not source_stem:
            source_stem = "document"
        if not element_name:
            element_name = "element"
        return f"{source_stem}__{element_name}__{step_repository.source_hash[:8]}.xlsx"

    def _build_datapackage_name(self, step_repository: ElementImportStepRepository) -> str:
        source_stem: str = re.sub(r"[^0-9A-Za-z_-]+", "_", step_repository.source_path.stem).strip("_").lower()
        element_name: str = re.sub(r"[^0-9A-Za-z_-]+", "_", step_repository.element_name).strip("_").lower()
        if not source_stem:
            source_stem = "document"
        if not element_name:
            element_name = "element"
        return f"{source_stem}_{element_name}"

    def _task_time_value(self, task_time_payload: Dict[str, Any]) -> Dict[str, Any]:
        if not task_time_payload:
            return {}

        serialized_payload: Dict[str, Any] = {
            key: value
            for key, value in task_time_payload.items()
            if key != "type"
        }
        if not serialized_payload:
            return {}

        return serialized_payload
