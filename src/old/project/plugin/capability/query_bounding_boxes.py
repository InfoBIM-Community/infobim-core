import json
from typing import Any, Dict, List, Optional

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import QueryCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class PdfBoundingBoxesQueryCapability(QueryCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.query.bounding_boxes",
        version="1.0.0",
        name="Project element import PDF bounding boxes",
        description="Read page chunks and bounding boxes from the identified project import source.",
        author=["TRAE"],
        tags=["project", "import", "bounding-boxes", "pdf"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import PDF bounding boxes"

    def description(self, lang: str = "en") -> str:
        return "Read page chunks and bounding boxes from the identified project import source."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise ValueError("The 'pymupdf4llm' package is required to identify project import bounding boxes.") from exc

        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        identified_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.IDENTIFIED)
        identified_payload: Dict[str, Any] = json.loads(str(identified_resource.content))
        source_resource = LocalContextFileResource(identified_payload["path"])

        bounding_boxes: List[Dict[str, Any]] = pymupdf4llm.to_markdown(
            str(source_resource.path),
            page_chunks=True,
            extract_words=True,
        )
        if not bounding_boxes:
            raise ValueError(f"Could not identify bounding boxes from '{source_resource.path}'.")

        context.set_parameter_value("resource_bounding_boxes", bounding_boxes)
        return {
            "path": str(source_resource.path),
            "pages": len(bounding_boxes),
        }
