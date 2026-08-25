from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from rdflib import Graph, URIRef

from infobim.project.domain.model.contract import IFCOWL_NS
from ontobdc.context.adapter.dataset_instance import DatasetEntityInstanceRepository
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


_HAS_DATA_ENTITY_FACADE = URIRef(
    "http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#hasDataEntityFacade"
)


class IfcClassCatalogRepository:
    """Discover IFC classes and their instances exposed by Project dataset facades."""

    def __init__(self, project_path: str) -> None:
        self._project_path = Path(project_path).expanduser().resolve()

    def list_classes(self) -> Dict[str, Any]:
        aggregates: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "class_uri": "",
                "class_name": "",
                "element_count": 0,
                "dataset_count": 0,
                "datasets": [],
            }
        )

        for dataset_path in self._dataset_paths():
            for class_uri in self._dataset_ifc_classes(dataset_path):
                try:
                    payload = DatasetEntityInstanceRepository(
                        dataset_path=str(dataset_path),
                        entity=class_uri,
                    ).list_instances()
                    element_count = int(payload.get("instance_count") or 0)
                except Exception:
                    element_count = 0

                aggregate = aggregates[class_uri]
                aggregate["class_uri"] = class_uri
                aggregate["class_name"] = self._local_name(class_uri)
                aggregate["element_count"] += element_count
                aggregate["dataset_count"] += 1
                aggregate["datasets"].append(str(dataset_path))

        classes: List[Dict[str, Any]] = sorted(
            aggregates.values(),
            key=lambda item: str(item["class_name"]).lower(),
        )
        return {
            "project_path": str(self._project_path),
            "class_count": len(classes),
            "element_count": sum(int(item["element_count"]) for item in classes),
            "classes": classes,
        }

    def list_elements(self, class_name: str) -> Dict[str, Any]:
        """List deduplicated instances of one IFC class across all Project datasets."""
        requested = str(class_name or "").strip()
        if not requested:
            raise ValueError("IFC class name cannot be empty.")

        matched_class_uri: Optional[str] = None
        matching_datasets: List[Path] = []
        for dataset_path in self._dataset_paths():
            for class_uri in self._dataset_ifc_classes(dataset_path):
                if self._matches_class(requested, class_uri):
                    if matched_class_uri is None:
                        matched_class_uri = class_uri
                    matching_datasets.append(dataset_path)
                    break

        if matched_class_uri is None:
            return {
                "project_path": str(self._project_path),
                "class_name": requested,
                "class_uri": None,
                "dataset_count": 0,
                "datasets": [],
                "element_count": 0,
                "elements": [],
            }

        elements_by_key: Dict[str, Dict[str, Any]] = {}
        for dataset_path in matching_datasets:
            try:
                payload = DatasetEntityInstanceRepository(
                    dataset_path=str(dataset_path),
                    entity=matched_class_uri,
                ).list_instances()
            except Exception:
                continue

            for index, raw_element in enumerate(payload.get("instances") or []):
                if not isinstance(raw_element, dict):
                    continue
                element = dict(raw_element)
                key = self._element_key(element, dataset_path, index)
                if key not in elements_by_key:
                    element["datasets"] = [str(dataset_path)]
                    elements_by_key[key] = element
                else:
                    datasets = elements_by_key[key].setdefault("datasets", [])
                    if str(dataset_path) not in datasets:
                        datasets.append(str(dataset_path))

        elements = list(elements_by_key.values())
        elements.sort(key=self._element_sort_key)
        return {
            "project_path": str(self._project_path),
            "class_name": self._local_name(matched_class_uri),
            "class_uri": matched_class_uri,
            "dataset_count": len(matching_datasets),
            "datasets": [str(path) for path in matching_datasets],
            "element_count": len(elements),
            "elements": elements,
        }

    def get_element(self, global_id: str) -> Dict[str, Any]:
        """Resolve one IFC element by GlobalId across all Project datasets."""
        requested = str(global_id or "").strip()
        if not requested:
            raise ValueError("IFC element GlobalId cannot be empty.")

        matches: List[Dict[str, Any]] = []
        for dataset_path in self._dataset_paths():
            for class_uri in self._dataset_ifc_classes(dataset_path):
                try:
                    payload = DatasetEntityInstanceRepository(
                        dataset_path=str(dataset_path),
                        entity=class_uri,
                    ).list_instances()
                except Exception:
                    continue

                for raw_element in payload.get("instances") or []:
                    if not isinstance(raw_element, dict):
                        continue
                    element_global_id = self._global_id(raw_element)
                    if element_global_id != requested:
                        continue
                    matches.append(
                        {
                            "class_uri": class_uri,
                            "class_name": self._local_name(class_uri),
                            "dataset": str(dataset_path),
                            "element": dict(raw_element),
                        }
                    )

        if not matches:
            return {
                "project_path": str(self._project_path),
                "global_id": requested,
                "found": False,
                "class_uri": None,
                "class_name": None,
                "dataset_count": 0,
                "datasets": [],
                "element": None,
            }

        class_uris = {str(match["class_uri"]) for match in matches}
        if len(class_uris) > 1:
            raise ValueError(
                "IFC element GlobalId resolves to more than one IFC class: "
                f"{requested}"
            )

        datasets = sorted({str(match["dataset"]) for match in matches})
        first = matches[0]
        merged_element = dict(first["element"])
        merged_element["datasets"] = datasets
        return {
            "project_path": str(self._project_path),
            "global_id": requested,
            "found": True,
            "class_uri": str(first["class_uri"]),
            "class_name": str(first["class_name"]),
            "dataset_count": len(datasets),
            "datasets": datasets,
            "element": merged_element,
        }

    def _dataset_paths(self) -> List[Path]:
        if not self._project_path.is_dir():
            return []
        return sorted(
            path
            for path in self._project_path.iterdir()
            if path.is_dir()
            and (StorageBootstrap.get_ontobdc_directory(path) / "linkset" / "facade.ttl").is_file()
        )

    def _dataset_ifc_classes(self, dataset_path: Path) -> List[str]:
        facade_path = StorageBootstrap.get_ontobdc_directory(dataset_path) / "linkset" / "facade.ttl"
        if not facade_path.is_file():
            return []

        graph = Graph()
        try:
            graph.parse(str(facade_path), format="turtle")
        except Exception:
            return []

        return sorted(
            {
                str(subject)
                for subject in graph.subjects(_HAS_DATA_ENTITY_FACADE, None)
                if isinstance(subject, URIRef) and str(subject).startswith(IFCOWL_NS)
            }
        )

    @classmethod
    def _matches_class(cls, requested: str, class_uri: str) -> bool:
        normalized = requested.strip().lower()
        return normalized in {
            class_uri.lower(),
            cls._local_name(class_uri).lower(),
        }

    @staticmethod
    def _global_id(element: Dict[str, Any]) -> Optional[str]:
        for field_name in (
            "GlobalId",
            "globalId",
            "global_id",
            "globalid",
        ):
            value = str(element.get(field_name) or "").strip()
            if value:
                return value
        return None

    @classmethod
    def _element_key(cls, element: Dict[str, Any], dataset_path: Path, index: int) -> str:
        global_id = cls._global_id(element)
        if global_id:
            return f"identity:{global_id}"
        for field_name in ("URI", "uri", "id", "Id"):
            value = str(element.get(field_name) or "").strip()
            if value:
                return f"identity:{value}"
        return f"row:{dataset_path}:{index}:{repr(sorted(element.items()))}"

    @staticmethod
    def _element_sort_key(element: Dict[str, Any]) -> str:
        for field_name in ("Name", "name", "GlobalId", "globalId", "global_id"):
            value = str(element.get(field_name) or "").strip()
            if value:
                return value.lower()
        return repr(sorted(element.items())).lower()

    @staticmethod
    def _local_name(uri: str) -> str:
        value = str(uri).rstrip("/#")
        if "#" in value:
            return value.rsplit("#", 1)[-1]
        return value.rsplit("/", 1)[-1]
