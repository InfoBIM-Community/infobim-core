from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.element import IfcElementEntity
from infobim.project.plugin.machine.ifc_element_list.state import IfcElementListProcessState


class IfcElementsReadCapability(TransactionCapability):
    """
    Reads every IfcElement of the IFC models of the project, one dataset-like
    entry per model, in the shape the container entity listing answers.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.project.plugin.capability.transformation.target."
            "ifc_elements_read"
        ),
        version="1.0.0",
        name="IFC Elements Read",
        description="Read the IfcElement instances of the IFC models of the project.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "ifc", "entity", "list"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The IFC elements of the project were read."},
            "debug_entry": {"en": "Reading the IFC elements of the project."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return IfcElementListProcessState.IFC_ELEMENTS_READ.label(lang)

    def description(self, lang: str = "en") -> str:
        return IfcElementListProcessState.IFC_ELEMENTS_READ.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import ifcopenshell
        except ImportError as error:
            raise RuntimeError("Reading IFC models needs ifcopenshell, which is not installed here.") from error

        project_path: Path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve()
        datasets: List[Dict[str, Any]] = []
        model_path: str
        for model_path in context.get_parameter_value("ifc_model_paths") or []:
            model: Any = ifcopenshell.open(model_path)
            datasets.append(IfcElementEntity.dataset(project_path, Path(model_path), model, model.by_type("IfcElement")))
        context.set_parameter_value("ifc_element_datasets", datasets)

        return {
            "resulting_state": IfcElementListProcessState.IFC_ELEMENTS_READ,
            "ifc_element_datasets": datasets,
        }
