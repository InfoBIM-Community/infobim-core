from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.models import IfcProjectModels
from infobim.project.plugin.machine.ifc_element_list.state import IfcElementListProcessState


class IfcModelsFoundCapability(TransactionCapability):
    """
    Finds the IFC models the project holds, as its RO-Crate declares them.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.project.plugin.capability.transformation.target."
            "ifc_models_found"
        ),
        version="1.0.0",
        name="IFC Models Found",
        description="Find the IFC models the RO-Crate of the project declares.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "ifc", "entity", "list"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The IFC models of the project were found."},
            "debug_entry": {"en": "Finding the IFC models of the project."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return IfcElementListProcessState.IFC_MODELS_FOUND.label(lang)

    def description(self, lang: str = "en") -> str:
        return IfcElementListProcessState.IFC_MODELS_FOUND.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path: Path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve()
        paths: List[Path] = sorted(IfcProjectModels.paths(project_path) or [])
        context.set_parameter_value("ifc_model_paths", [str(path) for path in paths])

        return {
            "resulting_state": IfcElementListProcessState.IFC_MODELS_FOUND,
            "ifc_model_paths": [str(path) for path in paths],
        }
