

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF

from infobim.context.ontology import EntityContextContract, InfoBIMOntologyAdapter
from infobim.context.workbook import (
    EntityContextWorkbookAdapter,
    EntityContextWorkbookArtifact,
)
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.bootstrap import (
    get_dataset_storage_file_path,
    get_ontobdc_directory,
)
from ontobdc.storage.adapter.machine import DatasetCreateStateTransitionHandler


OBDC = Namespace("http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#")


@dataclass(frozen=True)
class EntityContextCreateResult:
    project_id: str
    container_path: Path
    dataset_path: Path
    entity_uri: str
    entity_subject: str
    workbook: EntityContextWorkbookArtifact

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "container_path": str(self.container_path),
            "dataset_path": str(self.dataset_path),
            "entity_uri": self.entity_uri,
            "entity_subject": self.entity_subject,
            "workbook_path": str(self.workbook.workbook_path),
            "worksheets": list(self.workbook.worksheets),
            "global_id": self.workbook.root_global_id,
            "datapackage_path": str(self.workbook.datapackage_path),
        }


class ContextEntityCreateService:
    """Create an ontology-declared root entity and related context."""

    def __init__(
        self,
        *,
        ontology: InfoBIMOntologyAdapter | None = None,
        workbook: EntityContextWorkbookAdapter | None = None,
    ) -> None:
        self._ontology = ontology or InfoBIMOntologyAdapter()
        self._workbook = workbook or EntityContextWorkbookAdapter()

    def create(
        self,
        *,
        project_id: str,
        project_path: str,
        container_id: str,
        entity: str,
        instance_name: str,
        context: CliContextPort,
    ) -> EntityContextCreateResult:
        root = Path(project_path).expanduser().resolve()
        if not project_id or not root.is_dir() or not container_id:
            raise ValueError("A resolved InfoBIM Project is required.")
        if not entity.strip() or not instance_name.strip():
            raise ValueError("--entity and --create require values.")

        contract = self._ontology.resolve_entity_context(entity)
        dataset_path = self._new_dataset_path(
            root, contract.root.entity_name, instance_name
        )
        self._create_dataset(dataset_path, root, container_id, context)
        workbook = self._workbook.generate(
            dataset_path=dataset_path,
            contract=contract,
            instance_name=instance_name,
        )
        entity_subject = self._register_root_entity(
            dataset_path,
            contract,
            workbook.root_global_id,
            instance_name,
        )
        self._materialize_contract(dataset_path)
        return EntityContextCreateResult(
            project_id=project_id,
            container_path=root,
            dataset_path=dataset_path,
            entity_uri=contract.root.entity_uri,
            entity_subject=entity_subject,
            workbook=workbook,
        )

    @staticmethod
    def _create_dataset(
        dataset_path: Path,
        container_path: Path,
        container_id: str,
        context: CliContextPort,
    ) -> None:
        context.set_parameter_value("container_path", str(container_path))
        context.set_parameter_value("container_id", container_id)
        context.set_parameter_value("dataset_path", str(dataset_path))
        DatasetCreateStateTransitionHandler(context=context).execute()

    @staticmethod
    def _register_root_entity(
        dataset_path: Path,
        contract: EntityContextContract,
        global_id: str,
        instance_name: str,
    ) -> str:
        dataset_file = get_dataset_storage_file_path(dataset_path)
        graph = Graph()
        graph.parse(str(dataset_file), format="turtle")
        datasets: List[URIRef] = [
            subject
            for subject in graph.subjects(RDF.type, OBDC.EntityDataset)
            if isinstance(subject, URIRef)
        ]
        if len(datasets) != 1:
            raise ValueError(f"Dataset metadata is invalid: {dataset_file}")
        dataset = datasets[0]
        for stale in list(graph.objects(dataset, OBDC.hasDataEntity)):
            graph.remove((dataset, OBDC.hasDataEntity, stale))

        entity = URIRef(f"{dataset}/{global_id}")
        entity_type = URIRef(contract.root.entity_uri)
        graph.add((dataset, OBDC.hasDataEntity, entity))
        graph.add((entity, RDF.type, OBDC.DataEntity))
        graph.add((entity, RDF.type, entity_type))
        graph.add((entity, DCTERMS.identifier, Literal(global_id)))
        graph.add((entity, DCTERMS.title, Literal(instance_name)))
        graph.add((entity, DCTERMS.conformsTo, URIRef(contract.root.facade_uri)))
        graph.add((entity_type, RDF.type, OBDC.SurfaceableEntity))
        graph.serialize(destination=str(dataset_file), format="turtle")
        return str(entity)

    def _materialize_contract(self, dataset_path: Path) -> None:
        linkset = get_ontobdc_directory(dataset_path) / "linkset"
        linkset.mkdir(parents=True, exist_ok=True)
        for filename in ("ns.ttl", "view.ttl"):
            (linkset / filename).write_text(
                self._ontology.ontology_text(filename),
                encoding="utf-8",
            )

    @classmethod
    def _new_dataset_path(
        cls,
        root: Path,
        entity_name: str,
        instance_name: str,
    ) -> Path:
        slug = f"{cls._slug(entity_name)}-{cls._slug(instance_name)}"
        candidate = root / slug
        suffix = 2
        while candidate.exists():
            candidate = root / f"{slug}-{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
