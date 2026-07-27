import json
from typing import Any, Dict, Optional

from infobim.project.adapter.repository import ElementImportStepRepository
from infobim.project.domain.machine.import_state import ElementImportProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.repository import LocalContextFileResource
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class LocalizedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.localized",
        version="1.0.0",
        name="Project element import transformation to Localized",
        description="Detect the language of the extracted project import document.",
        author=["TRAE"],
        tags=["project", "import", "localized", "language"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Localized"

    def description(self, lang: str = "en") -> str:
        return "Detect the language of the extracted project import document."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import langid
        except ImportError as exc:
            raise ValueError("The 'langid' package is required to detect project import document language.") from exc

        step_repository: Optional[ElementImportStepRepository] = context.get_parameter_value("element_import_step_repository")
        if not isinstance(step_repository, ElementImportStepRepository):
            step_repository = ElementImportStepRepository(
                container_path=str(context.get_parameter_value("container_path")),
                source_path=str(context.get_parameter_value("import_path")),
                element_name=str(context.get_parameter_value("element_name")),
            )
            context.set_parameter_value("element_import_step_repository", step_repository)

        extracted_resource: LocalContextFileResource = step_repository.reload(ElementImportProcessState.EXTRACTED)
        extracted_content: str = str(extracted_resource.content).strip()
        if not extracted_content:
            raise ValueError(f"The extracted artifact '{extracted_resource.path}' is empty.")

        language_code, language_score = langid.classify(extracted_content)
        localized_payload: Dict[str, Any] = {
            "resource": extracted_resource.to_json(),
            "language": {
                "code": language_code,
                "score": float(language_score),
            },
        }
        localized_path = step_repository.write_text_file(
            state=ElementImportProcessState.LOCALIZED,
            content=json.dumps(localized_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("document_language_code", language_code)
        context.set_parameter_value("document_language_score", float(language_score))
        context.set_parameter_value("resource", LocalContextFileResource(localized_path))
        return {
            "resulting_state": ElementImportProcessState.LOCALIZED,
            "path": str(localized_path),
        }
