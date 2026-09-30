from typing import Any, ClassVar, Dict, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.crate import ContainerRoCrate
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)

from infobim.ifc.domain.exception.creation import IfcModelNotResolvedError


class IfcModelDeclaredCapability(TransactionCapability):
    """
    Declare the project's IFC model file in the project's RO-Crate.

    What a project holds is what its RO-Crate declares, so a model file the
    crate does not state is not yet a model other steps may write into. The
    container's manifest hotfix brings the crate in line with the files the
    project holds.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "ifc_model_declared"
        ),
        version="0.1.0",
        name="IFC Model Declared",
        description=(
            "Declare the IFC model file of the project in the project's "
            "RO-Crate."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "model", "ro-crate"],
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
            "info": {"en": "The IFC model is declared by the project."},
            "debug_entry": {"en": "Declaring the IFC model in the project."},
        },
    )

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        project_value: Optional[str] = RequiredParameter.optional(
            context, self.CONTAINER_PATH_KEY
        )
        model_value: Optional[str] = RequiredParameter.optional(
            context, self.IFC_MODEL_PATH_KEY
        )
        if project_value is None or model_value is None:
            return False

        return self._declared(
            Path(project_value).expanduser().resolve(),
            Path(model_value).expanduser().resolve(),
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
        model_path: Path = Path(
            RequiredParameter.of(context, self.IFC_MODEL_PATH_KEY)
        ).expanduser().resolve()

        exit_code: int = hotfix_container_manifest_synced(
            container_path=str(project_path),
            root_path=str(context.root_path),
        )
        if exit_code != 0 or not self._declared(project_path, model_path):
            raise IfcModelNotResolvedError(
                f"The IFC model at {model_path} could not be declared in the "
                f"RO-Crate of the project at {project_path}."
            )

        return {self.IFC_MODEL_PATH_KEY: str(model_path)}

    @staticmethod
    def _declared(project_path: Path, model_path: Path) -> bool:
        if not model_path.is_file() or not model_path.is_relative_to(project_path):
            return False

        return model_path.relative_to(project_path).as_posix() in set(
            ContainerRoCrate.file_paths(project_path)
        )
