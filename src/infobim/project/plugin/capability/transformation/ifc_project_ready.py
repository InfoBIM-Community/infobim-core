import uuid
from pathlib import Path
from typing import Any, Dict, List

from infobim.project.domain.model.contract import IFC_PROJECT_CLASS_URI, IFC_PROJECT_FACADE_URI, IFC_PROJECT_FIELDS, PROJECT_DATASET_NAME, PROJECT_WORKBOOK_NAME, PROJECT_WORKSHEET_NAME
from infobim.project.plugin.capability.base import ProjectTransactionCapability
from infobim.project.plugin.check.is_ifc_project_ready import evaluate
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.entity_workbook import EntityWorkbookAdapter, EntityWorkbookField
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap, StorageNamespaceBootstrap
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF


StorageNamespaceBootstrap.initialize()
_OBDC = StorageNamespaceBootstrap.OBDC


class IfcProjectReadyCapability(ProjectTransactionCapability):
    _IFC64 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.ifc_project_ready",
        version="1.0.0",
        name="IfcProject Ready",
        description="Create the single editable IfcProject instance and its XLSX/Data Package representation inside .__infobim__.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "ifc", "xlsx"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Editable IfcProject instance and its XLSX and Data Package "
                    "representations were created inside the reserved project "
                    "dataset."
                ),
            },
            "debug_entry": {
                "en": (
                    "Creating or validating the editable IfcProject instance "
                    "and its XLSX and Data Package representations inside the "
                    "reserved project dataset."
                ),
            },
        },
    )

    def is_satisfied(self, context: CliContextPort) -> bool:
        return evaluate(container_path=str(context.get_parameter_value("container_path")))

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve()
        dataset_path = container_path / PROJECT_DATASET_NAME
        dataset_metadata_path = StorageBootstrap.get_dataset_storage_file_path(dataset_path)
        if not dataset_metadata_path.is_file():
            raise ValueError(f"Project dataset metadata does not exist: {dataset_metadata_path}")

        graph = Graph()
        graph.parse(str(dataset_metadata_path), format="turtle")
        dataset_subjects = [subject for subject in graph.subjects(RDF.type, _OBDC.EntityDataset) if isinstance(subject, URIRef)]
        if len(dataset_subjects) != 1:
            raise ValueError("Project dataset must declare exactly one obdc:EntityDataset.")
        dataset_subject = dataset_subjects[0]

        existing_entities = [value for value in graph.objects(dataset_subject, _OBDC.hasDataEntity) if isinstance(value, URIRef)]
        entity_subject = existing_entities[0] if existing_entities else URIRef(f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, str(container_path))}")

        graph.add((dataset_subject, _OBDC.hasDataEntity, entity_subject))
        graph.add((entity_subject, RDF.type, _OBDC.DataEntity))
        graph.add((entity_subject, RDF.type, URIRef(IFC_PROJECT_CLASS_URI)))
        graph.set((entity_subject, DCTERMS.conformsTo, URIRef(IFC_PROJECT_FACADE_URI)))
        graph.set((entity_subject, DCTERMS.title, Literal(container_path.name)))
        graph.serialize(destination=str(dataset_metadata_path), format="turtle")

        project_global_id = self._new_ifc_global_id()
        fields: List[EntityWorkbookField] = [EntityWorkbookField(name=identifier) for identifier, _ in IFC_PROJECT_FIELDS]
        output_dir = dataset_path / "payload" / "document"
        datapackage_path = StorageBootstrap.get_ontobdc_directory(dataset_path) / "datapackage.json"
        artifact = EntityWorkbookAdapter().generate(
            output_dir=output_dir,
            workbook_name=PROJECT_WORKBOOK_NAME,
            worksheet_name=PROJECT_WORKSHEET_NAME,
            fields=fields,
            records=[{
                "GlobalId": project_global_id,
                "Name": container_path.name,
                "Description": "",
                "LongName": "",
                "Phase": "",
            }],
            datapackage_path=datapackage_path,
            package_name="infobim_project",
            resource_name="ifc_project",
            primary_key=["GlobalId"],
            entity_uri=IFC_PROJECT_CLASS_URI,
            entity_identifier="IfcProject",
            facade_uri=IFC_PROJECT_FACADE_URI,
            instance_uri_template="urn:ifc:IfcProject/{GlobalId}",
        )

        if not self.is_satisfied(context):
            raise ValueError("IfcProject artifacts were created but the IfcProject state was not satisfied.")
        return {
            "dataset_path": str(dataset_path),
            "entity_subject": str(entity_subject),
            "workbook_path": str(artifact.workbook_path),
            "datapackage_path": str(artifact.datapackage_path),
            "satisfied": True,
        }

    @staticmethod
    def _new_ifc_global_id() -> str:
        return IfcProjectReadyCapability._compress_ifc_guid(uuid.uuid4())

    @classmethod
    def _compress_ifc_guid(cls, value: uuid.UUID) -> str:
        """Compress a UUID with the buildingSMART IFC base-64 convention."""
        raw = value.bytes
        result = cls._encode_ifc64(raw[0], 2)
        for offset in range(1, 16, 3):
            result += cls._encode_ifc64(
                int.from_bytes(raw[offset : offset + 3], "big"),
                4,
            )
        return result

    @classmethod
    def _encode_ifc64(cls, number: int, length: int) -> str:
        characters = ["0"] * length
        value = number
        for index in range(length - 1, -1, -1):
            characters[index] = cls._IFC64[value % 64]
            value //= 64
        if value:
            raise ValueError("Value does not fit in requested IFC base64 length.")
        return "".join(characters)
