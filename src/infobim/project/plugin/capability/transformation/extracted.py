import json
from typing import Any, Dict, Optional

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class ExtractedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.extracted",
        version="1.0.0",
        name="Project element import transformation to Extracted",
        description="Extract markdown content from the identified project import source.",
        author=["TRAE"],
        tags=["project", "import", "extracted", "pdf"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Extracted"

    def description(self, lang: str = "en") -> str:
        return "Extract markdown content from the identified project import source."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise ValueError("The 'pymupdf4llm' package is required to extract project import PDF sources.") from exc

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
        if source_resource.mimetype != "application/pdf":
            raise ValueError(
                f"Project import currently supports only PDF sources. Got '{source_resource.mimetype}'."
            )

        extracted_content: str = str(pymupdf4llm.to_markdown(str(source_resource.path))).strip()
        if not extracted_content:
            raise ValueError(f"Could not extract markdown content from '{source_resource.path}'.")

        extracted_path = step_repository.write_text_file(
            state=ElementImportProcessState.EXTRACTED,
            content=extracted_content,
            file_type="md",
        )
        context.set_parameter_value("resource", LocalContextFileResource(extracted_path))
        return {
            "resulting_state": ElementImportProcessState.EXTRACTED,
            "path": str(extracted_path),
        }
