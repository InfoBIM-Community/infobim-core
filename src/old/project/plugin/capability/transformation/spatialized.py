import json
from collections import Counter
from typing import Any, Dict, List, Optional

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from infobim.project.plugin.capability.query_bounding_boxes import PdfBoundingBoxesQueryCapability
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class SpatializedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.spatialized",
        version="1.0.0",
        name="Project element import transformation to Spatialized",
        description="Store page chunks and bounding boxes for the extracted project import source.",
        author=["TRAE"],
        tags=["project", "import", "spatialized", "pdf"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Spatialized"

    def description(self, lang: str = "en") -> str:
        return "Store page chunks and bounding boxes for the extracted project import source."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        PdfBoundingBoxesQueryCapability().execute(context)

        identified_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.IDENTIFIED)
        identified_payload: Dict[str, Any] = json.loads(str(identified_resource.content))
        source_resource = LocalContextFileResource(identified_payload["path"])
        bounding_boxes: object = context.get_parameter_value("resource_bounding_boxes")
        if not isinstance(bounding_boxes, list) or not bounding_boxes:
            raise ValueError("Project import bounding boxes were not materialized.")

        spatial_structure: Dict[str, Any] = self._classify_spatial_structure(list(bounding_boxes))
        spatialized_payload: Dict[str, Any] = {
            "resource": source_resource.to_json(),
            "pages": list(bounding_boxes),
            "spatial_structure": spatial_structure,
        }
        spatialized_path = step_repository.write_text_file(
            state=ElementImportProcessState.SPATIALIZED,
            content=json.dumps(spatialized_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("spatial_structure", spatial_structure)
        context.set_parameter_value("resource", LocalContextFileResource(spatialized_path))
        return {
            "resulting_state": ElementImportProcessState.SPATIALIZED,
            "path": str(spatialized_path),
            "spatial_structure": spatial_structure,
        }

    def _classify_spatial_structure(self, pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not pages:
            return {
                "is_tabular": False,
                "is_large_table": False,
                "has_markdown_table_header": False,
                "largest_table_block_rows": 0,
                "table_line_ratio": 0.0,
                "column_count_mode": 0,
                "pages_with_table_boxes": 0,
                "page_table_ratio": 0.0,
                "max_table_boxes_per_page": 0,
            }

        all_lines: List[str] = []
        table_boxes_per_page: List[int] = []
        for page in pages:
            page_lines: List[str] = [
                line.strip()
                for line in str(page.get("text", "")).splitlines()
                if line.strip()
            ]
            all_lines.extend(page_lines)
            table_boxes_per_page.append(
                sum(
                    1
                    for box in page.get("page_boxes", [])
                    if isinstance(box, dict) and str(box.get("class", "")).strip() == "table"
                )
            )

        table_lines: List[str] = [line for line in all_lines if self._is_table_row(line)]
        table_blocks: List[List[str]] = self._collect_table_blocks(all_lines)
        largest_table_block_rows: int = max((len(block) for block in table_blocks), default=0)
        has_markdown_table_header: bool = any(self._has_markdown_table_header(block) for block in table_blocks)
        column_count_mode: int = self._column_count_mode(table_lines)
        table_line_ratio: float = round((len(table_lines) / len(all_lines)), 4) if all_lines else 0.0
        pages_with_table_boxes: int = sum(1 for count in table_boxes_per_page if count > 0)
        page_table_ratio: float = round(pages_with_table_boxes / len(pages), 4)
        max_table_boxes_per_page: int = max(table_boxes_per_page, default=0)
        is_tabular: bool = (
            has_markdown_table_header
            and largest_table_block_rows >= 3
            and pages_with_table_boxes >= 1
        )
        is_large_table: bool = (
            is_tabular
            and largest_table_block_rows >= 20
            and table_line_ratio >= 0.6
            and page_table_ratio >= 0.5
        )

        return {
            "is_tabular": is_tabular,
            "is_large_table": is_large_table,
            "has_markdown_table_header": has_markdown_table_header,
            "largest_table_block_rows": largest_table_block_rows,
            "table_line_ratio": table_line_ratio,
            "column_count_mode": column_count_mode,
            "pages_with_table_boxes": pages_with_table_boxes,
            "page_table_ratio": page_table_ratio,
            "max_table_boxes_per_page": max_table_boxes_per_page,
        }

    def _collect_table_blocks(self, lines: List[str]) -> List[List[str]]:
        blocks: List[List[str]] = []
        current_block: List[str] = []

        for line in lines:
            if self._is_table_row(line):
                current_block.append(line)
                continue

            if current_block:
                blocks.append(current_block)
                current_block = []

        if current_block:
            blocks.append(current_block)

        return blocks

    def _has_markdown_table_header(self, block: List[str]) -> bool:
        if len(block) < 2:
            return False

        for index in range(len(block) - 1):
            if self._is_header_separator(block[index + 1]):
                return True

        return False

    def _is_table_row(self, line: str) -> bool:
        return line.count("|") >= 2

    def _is_header_separator(self, line: str) -> bool:
        tokens: List[str] = [token.strip() for token in line.strip().strip("|").split("|")]
        if not tokens:
            return False

        return all(token and set(token) <= {"-", ":"} for token in tokens)

    def _column_count_mode(self, table_lines: List[str]) -> int:
        if not table_lines:
            return 0

        counts: Counter[int] = Counter(self._column_count(line) for line in table_lines)
        return counts.most_common(1)[0][0]

    def _column_count(self, line: str) -> int:
        tokens: List[str] = [token for token in line.strip().strip("|").split("|")]
        return len(tokens)
