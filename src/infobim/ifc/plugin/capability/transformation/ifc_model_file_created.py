from typing import Any, ClassVar, Dict, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.model import IfcModelBootstrap
from infobim.ifc.domain.port.model import IfcModelBootstrapPort
from infobim.ifc.domain.exception.creation import IfcModelNotUsableError


class IfcModelFileCreatedCapability(TransactionCapability):
    """
    Write the basic IFC model file of a project at the path the run names.

    The file carries the project's own IfcProject under the schema the
    project declares, and nothing else. A file already at that path is the
    state being reached, never something to overwrite.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "ifc_model_file_created"
        ),
        version="0.1.0",
        name="IFC Model File Created",
        description=(
            "Write the basic IFC model file of the project, carrying its "
            "IfcProject, at the path the run names."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "model", "create"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {"type": "string", "required": True},
                "ifc_model_path": {"type": "string", "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_model_path": {"type": "string"},
            },
        },
        log_message={
            "info": {"en": "The IFC model file of the project was written."},
            "debug_entry": {"en": "Writing the IFC model file of the project."},
        },
    )

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"

    def __init__(self, bootstrap: Optional[IfcModelBootstrapPort] = None) -> None:
        self._bootstrap: IfcModelBootstrapPort = bootstrap or IfcModelBootstrap()

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        model_path: Optional[str] = RequiredParameter.optional(
            context, self.IFC_MODEL_PATH_KEY
        )
        return model_path is not None and Path(model_path).expanduser().is_file()

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
        model_path: Path = Path(
            RequiredParameter.of(context, self.IFC_MODEL_PATH_KEY)
        ).expanduser().resolve()
        if model_path.exists():
            raise IfcModelNotUsableError(
                f"Something is already at {model_path}, so no IFC model is "
                "written over it."
            )
        if not model_path.is_relative_to(project_path):
            raise IfcModelNotUsableError(
                f"The IFC model at {model_path} would be outside the project "
                f"at {project_path}."
            )

        self._bootstrap.create(project_path, model_path)

        return {self.IFC_MODEL_PATH_KEY: str(model_path)}
