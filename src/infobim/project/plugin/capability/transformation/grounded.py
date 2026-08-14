import csv
import io
import json
import re
from typing import Any, Dict, List, Optional

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class GroundedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.grounded",
        version="1.0.0",
        name="Project element import transformation to Grounded",
        description="Materialize PDF-grounded cells and reconciliation data for the arranged project import tables.",
        author=["TRAE"],
        tags=["project", "import", "grounded", "pdf", "table"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Grounded"

    def description(self, lang: str = "en") -> str:
        return "Materialize PDF-grounded cells and reconciliation data for the arranged project import tables."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import fitz
        except ImportError as exc:
            raise ValueError("The 'pymupdf' package is required to ground table cells in the PDF.") from exc

        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        identified_payload: Dict[str, Any] = self._load_json(step_repository, ElementImportProcessState.IDENTIFIED)
        arranged_payload: Dict[str, Any] = self._load_json(step_repository, ElementImportProcessState.ARRANGED)
        source_path: str = str(identified_payload.get("path", "")).strip()
        if not source_path:
            raise ValueError("The identified project import artifact does not contain the source PDF path.")

        strategy_result: Dict[str, Any] = dict(arranged_payload.get("strategy_result", {}))
        csv_files: List[Dict[str, Any]] = list(strategy_result.get("csv_files", []))
        table_columns_payload: Dict[str, Any] = dict(strategy_result.get("table_columns", {}))
        arranged_tables: List[Dict[str, Any]] = list(table_columns_payload.get("tables", []))

        grounded_tables: List[Dict[str, Any]] = []
        reconciliation: List[Dict[str, Any]] = []
        global_table_index: int = 0
        with fitz.open(source_path) as document:
            for page_index, page in enumerate(document, start=1):
                for table_index, table in enumerate(page.find_tables().tables, start=1):
                    global_table_index += 1
                    extracted_rows: List[List[Any]] = list(table.extract())
                    header_row_index: int = self._resolve_header_row_index(extracted_rows)
                    if header_row_index < 0 or header_row_index >= len(table.rows):
                        continue

                    header_cells: List[Any] = list(table.rows[header_row_index].cells)
                    headers: List[str] = [
                        self._normalize_cell_value(value)
                        for value in extracted_rows[header_row_index]
                    ]
                    data_rows: List[List[Any]] = extracted_rows[header_row_index + 1 :]
                    grounded_columns: List[Dict[str, Any]] = self._build_columns(headers, header_cells)
                    grounded_rows: List[Dict[str, Any]] = self._build_rows(
                        headers=headers,
                        data_rows=data_rows,
                        table_rows=list(table.rows[header_row_index + 1 :]),
                    )

                    grounded_table: Dict[str, Any] = {
                        "global_table_index": global_table_index,
                        "page_number": page_index,
                        "table_index": table_index,
                        "table_bbox": [round(float(value), 3) for value in table.bbox],
                        "header_row_index": header_row_index,
                        "column_count": len(grounded_columns),
                        "row_count": len(grounded_rows),
                        "headers": grounded_columns,
                        "rows": grounded_rows,
                        "source": "fitz.find_tables",
                    }
                    grounded_tables.append(grounded_table)

                    arranged_table: Optional[Dict[str, Any]] = self._find_arranged_table(
                        arranged_tables=arranged_tables,
                        page_number=page_index,
                        table_index=table_index,
                    )
                    logical_csv: Optional[Dict[str, Any]] = (
                        csv_files[global_table_index - 1]
                        if len(csv_files) >= global_table_index
                        else None
                    )
                    reconciliation.append(
                        self._build_reconciliation_entry(
                            grounded_table=grounded_table,
                            arranged_table=arranged_table,
                            logical_csv=logical_csv,
                        )
                    )

        if not grounded_tables:
            raise ValueError("No grounded tables could be materialized from the source PDF.")

        summary: Dict[str, Any] = {
            "table_count": len(grounded_tables),
            "arranged_table_matches": sum(1 for item in reconciliation if item["arranged_table_present"]),
            "csv_table_matches": sum(1 for item in reconciliation if item["csv_table_present"]),
            "geometry_matches": sum(1 for item in reconciliation if item["geometry_headers_match"]),
            "logical_row_matches": sum(1 for item in reconciliation if item["logical_row_match_count"] == item["logical_row_count"]),
        }

        grounded_payload: Dict[str, Any] = {
            "document_kind": arranged_payload.get("document_kind"),
            "resource": arranged_payload.get("resource", {}),
            "selected_strategy": arranged_payload.get("selected_strategy", {}),
            "spatial_structure": arranged_payload.get("spatial_structure", {}),
            "strategy_result": strategy_result,
            "grounded_tables": grounded_tables,
            "reconciliation": reconciliation,
            "summary": summary,
        }
        grounded_path = step_repository.write_text_file(
            state=ElementImportProcessState.GROUNDED,
            content=json.dumps(grounded_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(grounded_path))
        context.set_parameter_value("grounded_summary", summary)
        return {
            "resulting_state": ElementImportProcessState.GROUNDED,
            "path": str(grounded_path),
            "table_count": len(grounded_tables),
        }

    def _load_json(self, step_repository: ElementImportStepRepository, state: ElementImportProcessState) -> Dict[str, Any]:
        resource: LocalContextFileResource = step_repository.reload(state)
        return json.loads(str(resource.content))

    def _resolve_header_row_index(self, rows: List[List[Any]]) -> int:
        for index, row in enumerate(rows):
            if len([value for value in row if self._normalize_cell_value(value)]) >= 2:
                return index

        return -1

    def _build_columns(self, headers: List[str], header_cells: List[Any]) -> List[Dict[str, Any]]:
        columns: List[Dict[str, Any]] = []
        for index, header_cell in enumerate(header_cells):
            if not header_cell:
                continue

            x0, y0, x1, y1 = [float(value) for value in header_cell]
            columns.append(
                {
                    "column_index": index + 1,
                    "header": headers[index] if index < len(headers) else "",
                    "width": round(x1 - x0, 3),
                    "bbox": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
                }
            )

        return columns

    def _build_rows(
        self,
        headers: List[str],
        data_rows: List[List[Any]],
        table_rows: List[Any],
    ) -> List[Dict[str, Any]]:
        grounded_rows: List[Dict[str, Any]] = []
        for row_index, values in enumerate(data_rows, start=1):
            cells_geometry: List[Any] = list(table_rows[row_index - 1].cells) if len(table_rows) >= row_index else []
            cells: List[Dict[str, Any]] = []
            for column_index, value in enumerate(values, start=1):
                bbox_values: Any = cells_geometry[column_index - 1] if len(cells_geometry) >= column_index else None
                bbox: Optional[List[float]] = None
                if bbox_values:
                    bbox = [round(float(item), 3) for item in bbox_values]

                normalized_text: str = self._normalize_cell_value(value)
                cells.append(
                    {
                        "row_index": row_index,
                        "column_index": column_index,
                        "header": headers[column_index - 1] if len(headers) >= column_index else "",
                        "text": normalized_text,
                        "text_normalized": self._normalize_signature(normalized_text),
                        "bbox": bbox,
                    }
                )

            grounded_rows.append(
                {
                    "row_index": row_index,
                    "cells": cells,
                    "row_text": " ".join(cell["text"] for cell in cells if cell["text"]),
                    "row_text_normalized": self._normalize_signature(
                        " ".join(cell["text"] for cell in cells if cell["text"])
                    ),
                }
            )

        return grounded_rows

    def _find_arranged_table(
        self,
        arranged_tables: List[Dict[str, Any]],
        page_number: int,
        table_index: int,
    ) -> Optional[Dict[str, Any]]:
        for table in arranged_tables:
            if int(table.get("page_number", 0) or 0) == page_number and int(table.get("table_index", 0) or 0) == table_index:
                return table

        return None

    def _build_reconciliation_entry(
        self,
        grounded_table: Dict[str, Any],
        arranged_table: Optional[Dict[str, Any]],
        logical_csv: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        arranged_headers: List[str] = []
        if arranged_table is not None:
            arranged_headers = [
                str(column.get("header", "")).strip()
                for column in list(arranged_table.get("columns", []))
            ]

        grounded_headers: List[str] = [
            str(column.get("header", "")).strip()
            for column in list(grounded_table.get("headers", []))
        ]
        geometry_headers_match: bool = arranged_headers == grounded_headers if arranged_headers else False

        logical_rows: List[List[str]] = self._parse_csv_rows(logical_csv.get("content", "")) if logical_csv else []
        logical_header: List[str] = logical_rows[0] if logical_rows else []
        logical_data_rows: List[List[str]] = logical_rows[1:] if len(logical_rows) > 1 else []
        grounded_row_signatures: List[str] = [
            str(row.get("row_text_normalized", ""))
            for row in list(grounded_table.get("rows", []))
        ]
        logical_row_signatures: List[str] = [
            self._normalize_signature(" ".join(str(cell).strip() for cell in row if str(cell).strip()))
            for row in logical_data_rows
        ]
        logical_row_match_count: int = sum(
            1
            for grounded_signature, logical_signature in zip(grounded_row_signatures, logical_row_signatures)
            if grounded_signature == logical_signature
        )

        return {
            "page_number": grounded_table.get("page_number"),
            "table_index": grounded_table.get("table_index"),
            "arranged_table_present": arranged_table is not None,
            "csv_table_present": logical_csv is not None,
            "geometry_headers_match": geometry_headers_match,
            "grounded_header_count": len(grounded_headers),
            "arranged_header_count": len(arranged_headers),
            "logical_header_count": len(logical_header),
            "logical_row_count": len(logical_data_rows),
            "grounded_row_count": int(grounded_table.get("row_count", 0) or 0),
            "logical_row_match_count": logical_row_match_count,
            "grounded_headers": grounded_headers,
            "arranged_headers": arranged_headers,
            "logical_headers": [self._normalize_cell_value(value) for value in logical_header],
        }

    def _parse_csv_rows(self, content: str) -> List[List[str]]:
        if not content.strip():
            return []

        buffer = io.StringIO(content)
        return [list(row) for row in csv.reader(buffer, delimiter=";")]

    def _normalize_cell_value(self, value: Any) -> str:
        if value is None:
            return ""

        return str(value).strip()

    def _normalize_signature(self, value: str) -> str:
        normalized: str = value.replace("\n", " ").strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized
