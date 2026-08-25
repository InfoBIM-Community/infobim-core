from pathlib import Path
from typing import Any, Dict

from infobim.project.domain.model.contract import IFCOWL_NS, IFC_PROJECT_CLASS_URI, IFC_PROJECT_FACADE_URI, IFC_PROJECT_FIELDS, INFOBIM_NS, PROJECT_DATASET_NAME
from infobim.project.plugin.capability.base import ProjectTransactionCapability
from infobim.project.plugin.check.is_ifc_project_facade_ready import evaluate
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class IfcProjectFacadeReadyCapability(ProjectTransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.ifc_project_facade_ready",
        version="1.0.0",
        name="IfcProject Facade Ready",
        description="Materialize the InfoBIM facade that projects IfcProject fields directly onto ifcOWL properties.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "ifc", "facade"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "IFC project facade was constructed from the IFC file header, "
                    "project entity, and declared units ready for consumption by "
                    "downstream InfoBIM steps."
                ),
            },
            "debug_entry": {
                "en": (
                    "Constructing the IFC project facade from the IFC file "
                    "header, project entity, and declared units."
                ),
            },
        },
    )

    def is_satisfied(self, context: CliContextPort) -> bool:
        return evaluate(container_path=str(context.get_parameter_value("container_path")))

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve()
        dataset_path = container_path / PROJECT_DATASET_NAME
        linkset_dir = StorageBootstrap.get_ontobdc_directory(dataset_path) / "linkset"
        linkset_dir.mkdir(parents=True, exist_ok=True)
        facade_path = linkset_dir / "facade.ttl"

        field_blocks = []
        for index, (identifier, property_name) in enumerate(IFC_PROJECT_FIELDS, start=1):
            field_uri = f"{INFOBIM_NS}IfcProjectFacadeField{index}"
            field_blocks.append(
                f"<{field_uri}>\n"
                f"    <http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#identifier> \"{identifier}\" ;\n"
                f"    <{INFOBIM_NS}defaultProperty> <{IFCOWL_NS}{property_name}> .\n"
            )

        field_links = " ;\n".join(
            f"    <http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#hasFacadeField> <{INFOBIM_NS}IfcProjectFacadeField{index}>"
            for index, _ in enumerate(IFC_PROJECT_FIELDS, start=1)
        )

        ttl = (
            f"<{IFC_PROJECT_CLASS_URI}>\n"
            f"    <http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#hasDataEntityFacade> <{IFC_PROJECT_FACADE_URI}> .\n\n"
            f"<{IFC_PROJECT_FACADE_URI}>\n{field_links} .\n\n"
            + "\n".join(field_blocks)
        )
        facade_path.write_text(ttl, encoding="utf-8")

        if not self.is_satisfied(context):
            raise ValueError("IfcProject facade was materialized but did not satisfy the facade contract.")
        return {"facade_path": str(facade_path), "satisfied": True}
