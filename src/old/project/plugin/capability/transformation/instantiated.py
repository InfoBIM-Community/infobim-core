import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class InstantiatedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.instantiated",
        version="1.0.0",
        name="Project element import transformation to Instantiated",
        description="Materialize IfcTask IFCJSON instances from the parsed realistic task grid.",
        author=["TRAE"],
        tags=["project", "import", "instantiated", "ifcjson", "ifctask"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Instantiated"

    def description(self, lang: str = "en") -> str:
        return "Materialize IfcTask IFCJSON instances from the parsed realistic task grid."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        instance_parsed_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.INSTANCE_PARSED)
        instance_parsed_payload: Dict[str, Any] = json.loads(str(instance_parsed_resource.content))
        realistic_tables: List[Dict[str, Any]] = list(instance_parsed_payload.get("realistic_tables", []))
        if not realistic_tables:
            raise ValueError("The instance parsed artifact does not contain any realistic table.")

        ifcjson_instances: List[Dict[str, Any]] = []
        ifc_task_time_count: int = 0
        for table in realistic_tables:
            for row in list(table.get("rows", [])):
                row_reference: Dict[str, Any] = dict(row.get("row_reference", {}))
                task_name: str = str(row_reference.get("task_name") or "").strip()
                identification: str = str(row_reference.get("work_breakdown_structure") or "").strip()
                duration_text: str = str(row_reference.get("duration") or "").strip()
                if not task_name and not identification:
                    continue

                instance_payload: Dict[str, Any] = self._build_ifc_task_instance(
                    step_repository=step_repository,
                    table=table,
                    row=row,
                    task_name=task_name,
                    identification=identification,
                    duration_text=duration_text,
                )
                if "TaskTime" in instance_payload:
                    ifc_task_time_count += 1
                ifcjson_instances.append(instance_payload)

        if not ifcjson_instances:
            raise ValueError("The realistic task grid did not produce any IfcTask IFCJSON instance.")

        instantiated_payload: Dict[str, Any] = {
            "source_state": ElementImportProcessState.INSTANCE_PARSED.value,
            "source_artifact": str(instance_parsed_resource.path),
            "summary": {
                "ifc_task_count": len(ifcjson_instances),
                "ifc_task_time_count": ifc_task_time_count,
                "table_count": len(realistic_tables),
            },
            "ifcjson_instances": ifcjson_instances,
        }
        instantiated_path: Path = step_repository.write_text_file(
            state=ElementImportProcessState.INSTANTIATED,
            content=json.dumps(instantiated_payload, ensure_ascii=False, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(instantiated_path))
        return {
            "resulting_state": ElementImportProcessState.INSTANTIATED,
            "path": str(instantiated_path),
            "ifc_task_count": len(ifcjson_instances),
        }

    def _build_ifc_task_instance(
        self,
        step_repository: ElementImportStepRepository,
        table: Dict[str, Any],
        row: Dict[str, Any],
        task_name: str,
        identification: str,
        duration_text: str,
    ) -> Dict[str, Any]:
        global_id_seed: str = "|".join(
            [
                str(step_repository.source_hash),
                str(table.get("global_table_index") or ""),
                str(table.get("page_number") or ""),
                str(table.get("table_index") or ""),
                str(row.get("row_index") or ""),
                identification,
                task_name,
            ]
        )
        task_instance: Dict[str, Any] = {
            "type": "IfcTask",
            "GlobalId": str(uuid.uuid5(uuid.NAMESPACE_URL, global_id_seed)),
            "Identification": identification or None,
            "Name": task_name or None,
            "IsMilestone": False,
            "_source": {
                "page_number": table.get("page_number"),
                "table_index": table.get("table_index"),
                "global_table_index": table.get("global_table_index"),
                "row_index": row.get("row_index"),
                "row_block_index": row.get("row_block_index"),
                "source_extracted_row_index": row.get("source_extracted_row_index"),
                "source_extracted_cells": row.get("source_extracted_cells", []),
                "alignment_score": row.get("alignment_score"),
            },
        }

        schedule_duration: Optional[str] = self._to_ifc_duration(duration_text)
        if schedule_duration is not None:
            task_instance["TaskTime"] = {
                "type": "IfcTaskTime",
                "ScheduleDuration": schedule_duration,
            }
        elif duration_text:
            task_instance["_source"]["raw_duration"] = duration_text

        return {
            key: value
            for key, value in task_instance.items()
            if value is not None
        }

    def _to_ifc_duration(self, raw_duration: str) -> Optional[str]:
        duration_value: str = str(raw_duration).strip()
        if not duration_value:
            return None

        if not re.fullmatch(r"\d+", duration_value):
            return None

        return f"P{int(duration_value)}W"
