import csv
import html
import io
import json
import re
from typing import Any, Dict, List, Optional

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from infobim.project.plugin.capability.strategy import StrategyCapability
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import QueryCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class _TabularIfcWorkScheduleSupport:
    def _get_step_repository(self, context: CliContextPort) -> ElementImportStepRepository:
        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )

        return step_repository

    def _collect_table_blocks(self, extracted_content: str) -> List[List[str]]:
        blocks: List[List[str]] = []
        current_block: List[str] = []

        for raw_line in extracted_content.splitlines():
            line: str = raw_line.strip()
            if self._is_table_row(line):
                current_block.append(line)
                continue

            if self._is_valid_table_block(current_block):
                blocks.append(list(current_block))
            current_block = []

        if self._is_valid_table_block(current_block):
            blocks.append(list(current_block))

        return blocks

    def _is_valid_table_block(self, block: List[str]) -> bool:
        return len(block) >= 2 and self._is_header_separator(block[1])

    def _is_table_row(self, line: str) -> bool:
        return line.count("|") >= 2

    def _is_header_separator(self, line: str) -> bool:
        cells: List[str] = [cell.strip() for cell in line.strip().strip("|").split("|")]
        return bool(cells) and all(cell and set(cell) <= {"-", ":"} for cell in cells)

    def _parse_markdown_table(self, block: List[str]) -> List[List[str]]:
        table_lines: List[str] = [block[0], *block[2:]]
        rows: List[List[str]] = []
        for line in table_lines:
            raw_cells: List[str] = line.strip().strip("|").split("|")
            rows.append([self._normalize_cell(cell) for cell in raw_cells])

        return rows

    def _normalize_cell(self, cell: str) -> str:
        normalized: str = cell.strip()
        normalized = normalized.replace("<br>", "\n")
        normalized = re.sub(r"\*\*(.*?)\*\*", r"\1", normalized)
        normalized = re.sub(r"_(.*?)_", r"\1", normalized)
        normalized = re.sub(r"`([^`]+)`", r"\1", normalized)
        return html.unescape(normalized)

    def _rows_to_csv(self, rows: List[List[str]]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
        for row in rows:
            writer.writerow(row)

        return buffer.getvalue()


class TabularIfcWorkScheduleColumnsQueryCapability(_TabularIfcWorkScheduleSupport, QueryCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.query.tabular_ifc_work_schedule_columns",
        version="1.0.0",
        name="Tabular IfcWorkSchedule column boxes",
        description="Estimate table column bounding boxes for tabular IfcWorkSchedule imports.",
        author=["TRAE"],
        tags=["project", "import", "query", "tabular", "ifcworkschedule", "columns"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Tabular IfcWorkSchedule column boxes"

    def description(self, lang: str = "en") -> str:
        return "Estimate table column bounding boxes for tabular IfcWorkSchedule imports."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import fitz
        except ImportError as exc:
            raise ValueError("The 'pymupdf' package is required to resolve real table column widths.") from exc

        step_repository: ElementImportStepRepository = self._get_step_repository(context)
        identified_resource = step_repository.reload(ElementImportProcessState.IDENTIFIED)
        identified_payload: Dict[str, Any] = json.loads(str(identified_resource.content))
        source_path: str = str(identified_payload.get("path", "")).strip()
        if not source_path:
            raise ValueError("The identified import artifact does not contain the source PDF path.")

        tables: List[Dict[str, Any]] = []
        with fitz.open(source_path) as document:
            for page_index, page in enumerate(document, start=1):
                for table_index, table in enumerate(page.find_tables().tables, start=1):
                    extracted_rows: List[List[Any]] = list(table.extract())
                    header_row_index: int = self._resolve_header_row_index(extracted_rows)
                    if header_row_index < 0 or header_row_index >= len(table.rows):
                        continue

                    header_cells: List[Any] = list(table.rows[header_row_index].cells)
                    header_labels: List[str] = [
                        self._normalize_table_value(value)
                        for value in extracted_rows[header_row_index]
                    ]
                    data_rows: List[List[Any]] = extracted_rows[header_row_index + 1 :]
                    columns: List[Dict[str, Any]] = self._build_real_columns(
                        header_labels=header_labels,
                        header_cells=header_cells,
                        data_rows=data_rows,
                    )
                    if not columns:
                        continue

                    tables.append(
                        {
                            "page_number": page_index,
                            "table_index": table_index,
                            "table_bbox": [round(float(value), 3) for value in table.bbox],
                            "column_count": len(columns),
                            "row_count": len(data_rows),
                            "columns": columns,
                            "source": "fitz.find_tables",
                        }
                    )

        result: Dict[str, Any] = {
            "element_name": str(context.get_parameter_value("element_name")),
            "table_count": len(tables),
            "tables": tables,
        }
        context.set_parameter_value("table_column_boxes", result)
        return result

    def _resolve_header_row_index(self, rows: List[List[Any]]) -> int:
        for index, row in enumerate(rows):
            non_empty_count: int = len([value for value in row if self._normalize_table_value(value)])
            if non_empty_count >= 2:
                return index

        return -1

    def _build_real_columns(
        self,
        header_labels: List[str],
        header_cells: List[Any],
        data_rows: List[List[Any]],
    ) -> List[Dict[str, Any]]:
        columns: List[Dict[str, Any]] = []
        for index, header_cell in enumerate(header_cells):
            if not header_cell:
                continue

            x0, y0, x1, y1 = [float(value) for value in header_cell]
            column_content: List[str] = [
                self._normalize_table_value(row[index] if index < len(row) else "")
                for row in data_rows
            ]
            columns.append(
                {
                    "index": index + 1,
                    "header": header_labels[index] if index < len(header_labels) else "",
                    "label": header_labels[index] if index < len(header_labels) else "",
                    "width": round(x1 - x0, 3),
                    "bbox": [
                        round(x0, 3),
                        round(y0, 3),
                        round(x1, 3),
                        round(y1, 3),
                    ],
                    "content": column_content,
                    "content_joined": "\n".join(value for value in column_content if value),
                }
            )

        return columns

    def _normalize_table_value(self, value: Any) -> str:
        if value is None:
            return ""

        return str(value).strip()


class TabularIfcWorkScheduleStrategyCapability(_TabularIfcWorkScheduleSupport, StrategyCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.strategy.tabular_ifc_work_schedule",
        version="1.0.0",
        name="Tabular IfcWorkSchedule arrangement strategy",
        description="Select the tabular arrangement strategy for IfcWorkSchedule imports.",
        author=["TRAE"],
        tags=["project", "import", "strategy", "tabular", "ifcworkschedule"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Tabular IfcWorkSchedule arrangement strategy"

    def description(self, lang: str = "en") -> str:
        return "Select the tabular arrangement strategy for IfcWorkSchedule imports."

    def matches(
        self,
        document_kind: str,
        element_name: str,
        context: CliContextPort,
    ) -> bool:
        return document_kind == "tabular" and element_name.strip().lower() == "ifcworkschedule"

    def priority(
        self,
        document_kind: str,
        element_name: str,
        context: CliContextPort,
    ) -> int:
        return 100

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: ElementImportStepRepository = self._get_step_repository(context)

        extracted_resource = step_repository.reload(ElementImportProcessState.EXTRACTED)
        extracted_content: str = str(extracted_resource.content)
        table_blocks: List[List[str]] = self._collect_table_blocks(extracted_content)
        csv_files: List[Dict[str, Any]] = []
        for index, block in enumerate(table_blocks, start=1):
            rows: List[List[str]] = self._parse_markdown_table(block)
            csv_content: str = self._rows_to_csv(rows)
            csv_files.append(
                {
                    "index": index,
                    "name": f"table_{index:03d}.csv",
                    "content": csv_content,
                    "row_count": len(rows),
                    "column_count": max((len(row) for row in rows), default=0),
                }
            )
        table_columns: Dict[str, Any] = TabularIfcWorkScheduleColumnsQueryCapability().execute(context)

        return {
            "strategy_family": "tabular",
            "element_name": str(context.get_parameter_value("element_name")),
            "arrangement_kind": "grid",
            "grid": None,
            "status": "pending",
            "csv_files": csv_files,
            "table_count": len(csv_files),
            "table_columns": table_columns,
        }
