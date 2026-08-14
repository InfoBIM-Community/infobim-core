import json
from typing import Any, Dict

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class IdentifiedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.identified",
        version="1.0.0",
        name="Project element import transformation to Identified",
        description="Store the identified import metadata for the selected project element source.",
        author=["TRAE"],
        tags=["project", "import", "identified", "pdf"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Identified"

    def description(self, lang: str = "en") -> str:
        return "Store the identified import metadata for the selected project element source."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: ElementImportStepRepository = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        source_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.UNDEFINED)
        if source_resource.mimetype != "application/pdf":
            raise ValueError(
                f"Project import currently supports only PDF sources. Got '{source_resource.mimetype}'."
            )

        semantic: str = self._resolve_pdf_semantic(source_resource)
        context.set_parameter_value("semantic", semantic)

        identified_payload: Dict[str, Any] = {
            "name": source_resource.name,
            "path": str(source_resource.path),
            "uri": source_resource.path.as_uri(),
            "mimetype": source_resource.mimetype,
            "project_id": context.get_parameter_value("project_id"),
            "element_name": context.get_parameter_value("element_name"),
            "element_uri": context.get_parameter_value("element_uri"),
            "entity_uri": context.get_parameter_value("entity_uri"),
            "import_path": context.get_parameter_value("import_path"),
            "semantic": semantic,
        }
        identified_path = step_repository.write_text_file(
            state=ElementImportProcessState.IDENTIFIED,
            content=json.dumps(identified_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(identified_path))
        return {
            "resulting_state": ElementImportProcessState.IDENTIFIED,
            "path": str(identified_path),
            "semantic": semantic,
        }

    def _resolve_pdf_semantic(self, source_resource: LocalContextFileResource) -> str:
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise ValueError("The 'pymupdf4llm' package is required to identify PDF import semantics.") from exc

        extracted_content: str = str(pymupdf4llm.to_markdown(str(source_resource.path))).strip()
        if extracted_content:
            return "textual_pdf"

        return "ocr_required"
