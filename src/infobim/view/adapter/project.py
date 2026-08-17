from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from infobim.ifc.adapter.class_catalog import IfcClassCatalogRepository
from infobim.project.domain.model.contract import (
    IFC_PROJECT_CLASS_URI,
    PROJECT_DATASET_NAME,
)
from infobim.view.domain.model import (
    IfcClassPresentation,
    InfoBIMProjectPresentation,
)
from ontobdc.context.adapter.dataset_instance import (
    DatasetEntityInstanceRepository,
)
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class InfoBIMProjectPresentationRepository:
    """Read the Project and distributed IFC catalog without owning a renderer."""

    def load(
        self,
        *,
        project_id: str,
        project_path: str,
    ) -> InfoBIMProjectPresentation:
        root = Path(project_path).expanduser().resolve()
        project_dataset = root / PROJECT_DATASET_NAME
        project = self._project_record(project_dataset, project_id)
        project_subject = self._project_subject(project_dataset)

        catalog = IfcClassCatalogRepository(str(root))
        class_catalog = catalog.list_classes()
        classes: List[IfcClassPresentation] = []
        for item in class_catalog.get("classes") or []:
            class_name = str(item.get("class_name") or "").strip()
            if not class_name:
                continue
            element_catalog = catalog.list_elements(class_name)
            classes.append(
                IfcClassPresentation(
                    class_uri=str(item.get("class_uri") or ""),
                    class_name=class_name,
                    element_count=int(
                        element_catalog.get("element_count") or 0
                    ),
                    dataset_count=int(item.get("dataset_count") or 0),
                    datasets=tuple(
                        str(value) for value in item.get("datasets") or []
                    ),
                    elements=tuple(
                        dict(value)
                        for value in element_catalog.get("elements") or []
                        if isinstance(value, dict)
                    ),
                )
            )

        return InfoBIMProjectPresentation(
            project_id=project_id,
            project_path=str(root),
            project_subject=project_subject,
            project=project,
            classes=tuple(classes),
        )

    @staticmethod
    def _project_record(
        dataset_path: Path,
        project_id: str,
    ) -> Dict[str, Any]:
        payload = DatasetEntityInstanceRepository(
            dataset_path=str(dataset_path),
            entity=IFC_PROJECT_CLASS_URI,
        ).list_instances()
        matches = [
            dict(item)
            for item in payload.get("instances") or []
            if isinstance(item, dict)
            and str(
                item.get("GlobalId")
                or item.get("globalId")
                or item.get("global_id")
                or ""
            ).strip()
            == project_id
        ]
        if len(matches) != 1:
            raise ValueError(
                "InfoBIM Project must resolve to exactly one IfcProject "
                f"instance: {project_id}"
            )
        return matches[0]

    @staticmethod
    def _project_subject(dataset_path: Path) -> str:
        graph = Graph()
        graph.parse(
            str(StorageBootstrap.get_dataset_storage_file_path(dataset_path)),
            format="turtle",
        )
        subjects = sorted(
            {
                str(subject)
                for subject in graph.subjects(
                    RDF.type,
                    URIRef(IFC_PROJECT_CLASS_URI),
                )
                if isinstance(subject, URIRef)
            }
        )
        if len(subjects) != 1:
            raise ValueError(
                "Project dataset must declare exactly one IfcProject subject."
            )
        return subjects[0]

