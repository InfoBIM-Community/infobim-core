import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from infobim.shared.adapter.config import ConfigDataAdapter
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.plugin.capability.query_ifc_class_attributes import QueryIfcClassAttributesCapability


class InstanceParsedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.instance_parsed",
        version="1.0.0",
        name="Project element import transformation to Instance Parsed",
        description="Interpret and clean drafted IFC instance data for the project import flow.",
        author=["TRAE"],
        tags=["project", "import", "instance_parsed", "ifc", "placeholder"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Instance Parsed"

    def description(self, lang: str = "en") -> str:
        return "Interpret and clean drafted IFC instance data for the project import flow."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: ElementImportStepRepository = self._get_element_import_step_repository(context)

        instance_drafted_resource: LocalContextFileResource = step_repository.reload(
            ElementImportProcessState.INSTANCE_DRAFTED,
        )
        instance_drafted_payload: Dict[str, Any] = json.loads(str(instance_drafted_resource.content))
        semanticized_payload: Dict[str, Any] = self._load_json(
            step_repository=step_repository,
            state=ElementImportProcessState.SEMANTICIZED,
        )
        arranged_payload: Dict[str, Any] = self._load_json(
            step_repository=step_repository,
            state=ElementImportProcessState.ARRANGED,
        )

        strategy_result: Dict[str, Any] = dict(arranged_payload.get("strategy_result", {}))
        table_columns_payload: Dict[str, Any] = dict(strategy_result.get("table_columns", {}))
        arranged_tables: List[Dict[str, Any]] = list(table_columns_payload.get("tables", []))
        semanticized_tables: List[Dict[str, Any]] = list(semanticized_payload.get("semanticized_tables", []))
        if not arranged_tables:
            raise ValueError("The arranged artifact does not expose any table metadata.")
        if not semanticized_tables:
            raise ValueError("The semanticized artifact does not expose any semanticized table metadata.")

        ifc_class_attributes: Dict[str, List[str]] = self._collect_ifc_class_data(
            instance_drafted_payload=instance_drafted_payload,
        )
        ifc_schema_name: str = self._get_ifc_schema_name(context=context)
        ifc_classes: Dict[str, List[Dict[str, Any]]] = {}
        for ifc_class_name in ifc_class_attributes.keys():
            context.set_parameter_value("ifc_schema_name", ifc_schema_name)
            context.set_parameter_value("ifc_class_name", ifc_class_name)
            ifc_class_payload: Dict[str, Any] = QueryIfcClassAttributesCapability().execute(context)
            ifc_classes[ifc_class_name] = list(ifc_class_payload.get("ifc_attributes", []))

        extracted_resource: LocalContextFileResource = step_repository.reload(
            ElementImportProcessState.EXTRACTED,
        )
        extracted_tables: List[List[List[str]]] = self._parse_extracted_tables(
            extracted_content=str(extracted_resource.content),
        )

        realistic_tables: List[Dict[str, Any]] = self._build_realistic_tables(
            arranged_tables=arranged_tables,
            semanticized_tables=semanticized_tables,
            extracted_tables=extracted_tables,
        )

        instance_parsed_payload: Dict[str, Any] = {
            "source_state": ElementImportProcessState.INSTANCE_DRAFTED.value,
            "source_artifact": str(instance_drafted_resource.path),
            "summary": {
                "table_count": len(realistic_tables),
                "row_count": sum(len(table.get("rows", [])) for table in realistic_tables),
                "cell_count": sum(
                    len(row.get("cells", []))
                    for table in realistic_tables
                    for row in table.get("rows", [])
                ),
                "instance_drafted_row_group_count": len(list(instance_drafted_payload.get("row_groups", []))),
            },
            "ifc_classes": ifc_classes,
            "ifc_class_attributes": ifc_class_attributes,
            "realistic_tables": realistic_tables,
        }
        instance_parsed_path: Path = step_repository.write_text_file(
            state=ElementImportProcessState.INSTANCE_PARSED,
            content=json.dumps(instance_parsed_payload, ensure_ascii=False, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(instance_parsed_path))
        return {
            "resulting_state": ElementImportProcessState.INSTANCE_PARSED,
            "path": str(instance_parsed_path),
            "table_count": len(realistic_tables),
            "row_count": instance_parsed_payload["summary"]["row_count"],
        }

    def _get_element_import_step_repository(self, context: CliContextPort) -> ElementImportStepRepository:
        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        return step_repository

    def _load_json(
        self,
        step_repository: ElementImportStepRepository,
        state: ElementImportProcessState,
    ) -> Dict[str, Any]:
        resource: LocalContextFileResource = step_repository.reload(state)
        return json.loads(str(resource.content))

    def _build_realistic_tables(
        self,
        arranged_tables: List[Dict[str, Any]],
        semanticized_tables: List[Dict[str, Any]],
        extracted_tables: List[List[List[str]]],
    ) -> List[Dict[str, Any]]:
        if len(arranged_tables) != len(extracted_tables):
            raise ValueError(
                "The arranged and extracted artifacts expose a different number of tables."
            )

        semanticized_table_index: Dict[Tuple[int, int], Dict[str, Any]] = {
            (
                int(table.get("page_number", 0)),
                int(table.get("table_index", 0)),
            ): dict(table)
            for table in semanticized_tables
        }

        realistic_tables: List[Dict[str, Any]] = []
        for table_position, arranged_table in enumerate(arranged_tables, start=1):
            page_number: int = int(arranged_table.get("page_number", 0))
            table_index: int = int(arranged_table.get("table_index", 0))
            semanticized_table: Optional[Dict[str, Any]] = semanticized_table_index.get((page_number, table_index))
            if semanticized_table is None:
                raise ValueError(
                    f"Missing semanticized metadata for arranged table page={page_number} table={table_index}."
                )

            realistic_tables.append(
                self._build_realistic_table(
                    table_position=table_position,
                    arranged_table=dict(arranged_table),
                    semanticized_table=semanticized_table,
                    extracted_rows=list(extracted_tables[table_position - 1]),
                )
            )

        return realistic_tables

    def _build_realistic_table(
        self,
        table_position: int,
        arranged_table: Dict[str, Any],
        semanticized_table: Dict[str, Any],
        extracted_rows: List[List[str]],
    ) -> Dict[str, Any]:
        arranged_columns: List[Dict[str, Any]] = [dict(column) for column in list(arranged_table.get("columns", []))]
        header_index: Dict[int, Dict[str, Any]] = {
            int(header.get("column_index", 0)): dict(header)
            for header in list(semanticized_table.get("headers", []))
        }
        arranged_row_blocks: List[Dict[str, Any]] = self._build_arranged_row_blocks(
            arranged_columns=arranged_columns,
            header_index=header_index,
        )
        leading_header_block_count: int = self._count_leading_header_blocks(arranged_row_blocks)
        extracted_data_rows: List[List[str]] = extracted_rows[3:] if len(extracted_rows) > 3 else []
        extracted_cursor: int = 0
        realistic_rows: List[Dict[str, Any]] = []
        row_index: int = 0

        for block_index, row_block in enumerate(arranged_row_blocks[leading_header_block_count:], start=1):
            extracted_row_window: List[List[str]] = list(
                extracted_data_rows[extracted_cursor: extracted_cursor + max(len(row_block.get("columns", [])), 1) + 4]
            )
            expanded_rows: List[Dict[str, Any]] = self._expand_arranged_row_block(
                row_block=row_block,
                row_block_index=block_index,
                extracted_row_window=extracted_row_window,
            )
            for expanded_row in expanded_rows:
                source_extracted_row: List[str] = []
                source_extracted_row_index: Optional[int] = None
                if extracted_cursor < len(extracted_data_rows):
                    source_extracted_row = list(extracted_data_rows[extracted_cursor])
                    source_extracted_row_index = extracted_cursor + 1
                    extracted_cursor += 1

                row_index += 1
                realistic_rows.append(
                    {
                        "row_index": row_index,
                        "row_block_index": block_index,
                        "cells": expanded_row["cells"],
                        "row_reference": self._build_realistic_row_reference(expanded_row["cells"]),
                        "source_extracted_row_index": source_extracted_row_index,
                        "source_extracted_cells": source_extracted_row,
                        "alignment_score": self._calculate_alignment_score(
                            resolved_cells=expanded_row["cells"],
                            extracted_cells=source_extracted_row,
                        ),
                    }
                )

        return {
            "global_table_index": arranged_table.get("global_table_index") or arranged_table.get("index") or table_position,
            "page_number": arranged_table.get("page_number"),
            "table_index": arranged_table.get("table_index"),
            "column_count": len(arranged_columns),
            "header_count": len(header_index),
            "row_count": len(realistic_rows),
            "headers": [
                {
                    "column_index": int(header.get("column_index", 0)),
                    "header": header.get("header"),
                    "semantic_key": header.get("semantic_key"),
                    "header_field_uri": header.get("header_field_uri"),
                }
                for header in list(semanticized_table.get("headers", []))
            ],
            "rows": realistic_rows,
        }

    def _build_arranged_row_blocks(
        self,
        arranged_columns: List[Dict[str, Any]],
        header_index: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        max_row_count: int = 0
        for column in arranged_columns:
            max_row_count = max(max_row_count, len(list(column.get("content", []))))

        row_blocks: List[Dict[str, Any]] = []
        for row_position in range(max_row_count):
            row_columns: List[Dict[str, Any]] = []
            for column in arranged_columns:
                column_index: int = int(column.get("index", 0))
                content_rows: List[str] = [str(value) for value in list(column.get("content", []))]
                semantic_header: Dict[str, Any] = dict(header_index.get(column_index, {}))
                row_columns.append(
                    {
                        "column_index": column_index,
                        "header": column.get("header") or column.get("label"),
                        "semantic_key": semantic_header.get("semantic_key"),
                        "header_field_uri": semantic_header.get("header_field_uri"),
                        "value": self._normalize_cell(content_rows[row_position]) if row_position < len(content_rows) else "",
                    }
                )

            row_blocks.append(
                {
                    "row_position": row_position + 1,
                    "columns": row_columns,
                }
            )

        return row_blocks

    def _count_leading_header_blocks(self, row_blocks: List[Dict[str, Any]]) -> int:
        leading_header_block_count: int = 0
        for row_block in row_blocks:
            semantic_values: List[str] = [
                str(column.get("value") or "").strip()
                for column in row_block.get("columns", [])
                if int(column.get("column_index", 0)) <= 3
            ]
            if any(semantic_values):
                break
            leading_header_block_count += 1

        return leading_header_block_count

    def _expand_arranged_row_block(
        self,
        row_block: Dict[str, Any],
        row_block_index: int,
        extracted_row_window: List[List[str]],
    ) -> List[Dict[str, Any]]:
        columns: List[Dict[str, Any]] = [dict(column) for column in list(row_block.get("columns", []))]
        wbs_column: Optional[Dict[str, Any]] = next(
            (column for column in columns if str(column.get("semantic_key") or "").strip() == "work_breakdown_structure"),
            None,
        )
        task_name_column: Optional[Dict[str, Any]] = next(
            (column for column in columns if str(column.get("semantic_key") or "").strip() == "task_name"),
            None,
        )
        duration_column: Optional[Dict[str, Any]] = next(
            (column for column in columns if str(column.get("semantic_key") or "").strip() == "duration"),
            None,
        )

        wbs_values: List[str] = self._split_logical_values(str((wbs_column or {}).get("value") or ""))
        task_name_lines: List[str] = self._split_logical_values(str((task_name_column or {}).get("value") or ""))
        logical_row_count: int = max(len(wbs_values), len(task_name_lines), 1)
        task_name_values: List[str] = self._coerce_task_name_lines(task_name_lines, logical_row_count)
        raw_duration_values: List[str] = self._split_logical_values(str((duration_column or {}).get("value") or ""))
        duration_values: List[str] = self._coerce_scalar_values(
            raw_duration_values,
            logical_row_count,
            wbs_values=wbs_values,
            task_name_values=task_name_values,
            extracted_row_window=extracted_row_window,
        )

        expanded_rows: List[Dict[str, Any]] = []
        for logical_index in range(logical_row_count):
            cells: List[Dict[str, Any]] = []
            for column in columns:
                semantic_key: str = str(column.get("semantic_key") or "").strip()
                resolved_value: str = ""
                if semantic_key == "work_breakdown_structure":
                    resolved_value = wbs_values[logical_index] if logical_index < len(wbs_values) else ""
                elif semantic_key == "task_name":
                    resolved_value = task_name_values[logical_index] if logical_index < len(task_name_values) else ""
                elif semantic_key == "duration":
                    resolved_value = duration_values[logical_index] if logical_index < len(duration_values) else ""
                else:
                    resolved_value = str(column.get("value") or "") if logical_index == 0 else ""

                cells.append(
                    {
                        "column_index": int(column.get("column_index", 0)),
                        "header": column.get("header"),
                        "semantic_key": column.get("semantic_key"),
                        "header_field_uri": column.get("header_field_uri"),
                        "value": resolved_value,
                        "row_block_index": row_block_index,
                        "logical_row_index": logical_index + 1,
                    }
                )

            expanded_rows.append({"cells": cells})

        return expanded_rows

    def _build_realistic_row_reference(self, cells: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        semantic_value_index: Dict[str, str] = {}
        for cell in cells:
            semantic_key: str = str(cell.get("semantic_key") or "").strip()
            cell_value: str = str(cell.get("value") or "").strip()
            if semantic_key and cell_value and semantic_key not in semantic_value_index:
                semantic_value_index[semantic_key] = cell_value

        return {
            "identifier": semantic_value_index.get("identifier"),
            "work_breakdown_structure": semantic_value_index.get("work_breakdown_structure"),
            "task_name": semantic_value_index.get("task_name"),
            "duration": semantic_value_index.get("duration"),
        }

    def _calculate_alignment_score(
        self,
        resolved_cells: List[Dict[str, Any]],
        extracted_cells: List[str],
    ) -> float:
        resolved_text: str = " ".join(
            str(cell.get("value") or "").strip()
            for cell in resolved_cells
            if str(cell.get("value") or "").strip()
        )
        extracted_text: str = " ".join(
            str(cell).strip()
            for cell in extracted_cells
            if str(cell).strip()
        )
        resolved_tokens: Set[str] = set(self._normalize_comparison_text(resolved_text).split())
        extracted_tokens: Set[str] = set(self._normalize_comparison_text(extracted_text).split())
        if not resolved_tokens and not extracted_tokens:
            return 1.0
        if not resolved_tokens or not extracted_tokens:
            return 0.0

        intersection_count: int = len(resolved_tokens.intersection(extracted_tokens))
        union_count: int = len(resolved_tokens.union(extracted_tokens))
        if union_count <= 0:
            return 0.0

        return round(intersection_count / union_count, 4)

    def _get_ifc_schema_name(self, context: CliContextPort) -> str:
        config_adapter: ConfigDataAdapter = ConfigDataAdapter(root_dir=str(context.root_path))
        ifc_config: Dict[str, Any] = dict(config_adapter.infobim_config.get("ifc", {}))
        ifc_schema_name: str = str(ifc_config.get("preferedSchema") or "").strip()
        if not ifc_schema_name:
            raise ValueError("InfoBIM IFC preferred schema is not configured.")

        return ifc_schema_name

    def _collect_ifc_class_data(self, instance_drafted_payload: Dict[str, Any]) -> Dict[str, List[str]]:
        ifc_class_attribute_index: Dict[str, Dict[str, None]] = {}

        for row_group in list(instance_drafted_payload.get("row_groups", [])):
            for ifc_instance in list(row_group.get("ifc_instances", [])):
                ifc_class_name: str = str(ifc_instance.get("ifc_class_name") or "").strip()
                if not ifc_class_name:
                    continue

                if ifc_class_name not in ifc_class_attribute_index:
                    ifc_class_attribute_index[ifc_class_name] = {}

                for field in list(ifc_instance.get("fields", [])):
                    ifc_attribute_name: str = str(field.get("ifc_attribute_name") or "").strip()
                    if ifc_attribute_name and ifc_attribute_name not in ifc_class_attribute_index[ifc_class_name]:
                        ifc_class_attribute_index[ifc_class_name][ifc_attribute_name] = None

        return {
            ifc_class_name: list(ifc_attribute_index.keys())
            for ifc_class_name, ifc_attribute_index in ifc_class_attribute_index.items()
        }

    def _parse_extracted_tables(self, extracted_content: str) -> List[List[List[str]]]:
        blocks: List[List[str]] = []
        current_block: List[str] = []
        for raw_line in extracted_content.splitlines():
            line: str = str(raw_line).strip()
            if self._is_table_row(line):
                current_block.append(line)
                continue

            if self._is_valid_table_block(current_block):
                blocks.append(list(current_block))
            current_block = []

        if self._is_valid_table_block(current_block):
            blocks.append(list(current_block))

        return [self._parse_markdown_table(block) for block in blocks]

    def _is_table_row(self, line: str) -> bool:
        return line.count("|") >= 2

    def _is_valid_table_block(self, block: List[str]) -> bool:
        return len(block) >= 2 and self._is_header_separator(block[1])

    def _is_header_separator(self, line: str) -> bool:
        cells: List[str] = [cell.strip() for cell in line.strip().strip("|").split("|")]
        return bool(cells) and all((not cell) or set(cell) <= {"-", ":"} for cell in cells)

    def _parse_markdown_table(self, block: List[str]) -> List[List[str]]:
        table_lines: List[str] = [block[0], *block[2:]]
        rows: List[List[str]] = []
        for line in table_lines:
            raw_cells: List[str] = line.strip().strip("|").split("|")
            rows.append([self._normalize_cell(cell) for cell in raw_cells])

        return rows

    def _normalize_cell(self, raw_cell: str) -> str:
        normalized_cell: str = str(raw_cell).strip()
        normalized_cell = re.sub(r"(?i)<br\s*/?>", "\n", normalized_cell)
        normalized_cell = re.sub(r"\*\*(.*?)\*\*", r"\1", normalized_cell)
        normalized_cell = re.sub(r"_(.*?)_", r"\1", normalized_cell)
        normalized_cell = re.sub(r"`([^`]+)`", r"\1", normalized_cell)
        normalized_cell = html.unescape(normalized_cell)
        normalized_cell = self._decode_unicode_escapes(normalized_cell)
        normalized_cell = re.sub(r"[ \t]+", " ", normalized_cell)
        normalized_cell = re.sub(r" *\n *", "\n", normalized_cell)
        return normalized_cell.strip()

    def _split_logical_values(self, value: str) -> List[str]:
        if not value.strip():
            return []

        return [
            part.strip()
            for part in str(value).split("\n")
            if part.strip()
        ]

    def _coerce_task_name_lines(self, lines: List[str], target_count: int) -> List[str]:
        if target_count <= 0:
            return []
        if not lines:
            return [""] * target_count
        if target_count == 1:
            return ["\n".join(lines).strip()]
        if len(lines) <= target_count:
            return lines + ([""] * (target_count - len(lines)))

        resolved_lines: List[str] = [lines[0]]
        for index, line in enumerate(lines[1:], start=1):
            remaining_lines: int = len(lines) - index
            remaining_slots: int = target_count - len(resolved_lines)
            if remaining_slots <= 0:
                resolved_lines[-1] = f"{resolved_lines[-1]}\n{line}".strip()
                continue
            if remaining_lines < remaining_slots or self._looks_like_wrapped_continuation(line):
                resolved_lines[-1] = f"{resolved_lines[-1]}\n{line}".strip()
                continue
            resolved_lines.append(line)

        if len(resolved_lines) < target_count:
            resolved_lines.extend([""] * (target_count - len(resolved_lines)))

        return resolved_lines[:target_count]

    def _coerce_scalar_values(
        self,
        values: List[str],
        target_count: int,
        wbs_values: List[str],
        task_name_values: List[str],
        extracted_row_window: List[List[str]],
    ) -> List[str]:
        if target_count <= 0:
            return []
        if not values:
            return [""] * target_count
        if len(values) >= target_count:
            return values[:target_count]

        if len(values) == 1 and target_count > 1:
            matched_index: Optional[int] = self._resolve_scalar_target_index(
                scalar_value=values[0],
                wbs_values=wbs_values,
                task_name_values=task_name_values,
                extracted_row_window=extracted_row_window,
            )
            resolved_values: List[str] = [""] * target_count
            resolved_values[matched_index if matched_index is not None else 0] = values[0]
            return resolved_values

        return [values[0], *([""] * max(target_count - 1, 0))]

    def _resolve_scalar_target_index(
        self,
        scalar_value: str,
        wbs_values: List[str],
        task_name_values: List[str],
        extracted_row_window: List[List[str]],
    ) -> Optional[int]:
        candidate_rows: List[List[str]] = []
        for extracted_row in extracted_row_window:
            comparable_values: List[str] = [str(cell).strip() for cell in extracted_row if str(cell).strip()]
            if not comparable_values:
                continue
            if scalar_value not in comparable_values:
                continue
            candidate_rows.append(comparable_values)

        if not candidate_rows:
            return None

        best_index: Optional[int] = None
        best_score: float = -1.0
        for logical_index in range(max(len(wbs_values), len(task_name_values), 1)):
            comparable_text: str = " ".join(
                part
                for part in [
                    wbs_values[logical_index] if logical_index < len(wbs_values) else "",
                    task_name_values[logical_index] if logical_index < len(task_name_values) else "",
                ]
                if part
            )
            logical_tokens: Set[str] = set(self._normalize_comparison_text(comparable_text).split())
            if not logical_tokens:
                continue

            logical_score: float = 0.0
            for candidate_row in candidate_rows:
                candidate_text: str = " ".join(value for value in candidate_row if value != scalar_value)
                candidate_tokens: Set[str] = set(self._normalize_comparison_text(candidate_text).split())
                if not candidate_tokens:
                    continue
                intersection_count: int = len(logical_tokens.intersection(candidate_tokens))
                union_count: int = len(logical_tokens.union(candidate_tokens))
                score: float = intersection_count / union_count if union_count > 0 else 0.0
                logical_score = max(logical_score, score)

            if logical_score > best_score:
                best_score = logical_score
                best_index = logical_index

        return best_index

    def _looks_like_wrapped_continuation(self, value: str) -> bool:
        candidate: str = str(value).strip()
        if not candidate:
            return True
        return bool(
            re.match(r"^[,.;:)\]}]|^[a-zà-ÿ]|^\(|^\+|^/|^-|^de\b|^da\b|^do\b|^das\b|^dos\b", candidate)
        )

    def _normalize_comparison_text(self, value: str) -> str:
        normalized_value: str = str(value).lower()
        normalized_value = re.sub(r"\s+", " ", normalized_value)
        normalized_value = re.sub(r"[^\w\sà-ÿ]", " ", normalized_value)
        normalized_value = re.sub(r"\s+", " ", normalized_value)
        return normalized_value.strip()

    def _decode_unicode_escapes(self, value: str) -> str:
        decoded_value: str = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda match: chr(int(match.group(1), 16)),
            value,
        )
        decoded_value = re.sub(
            r"\\U([0-9a-fA-F]{8})",
            lambda match: chr(int(match.group(1), 16)),
            decoded_value,
        )
        return decoded_value
