import json
from copy import deepcopy
from typing import Any, ClassVar, Dict, List, Optional, Tuple
from pathlib import Path

from infobim.drawing.model import IfcxDocument
from infobim.ifc.domain.port.composition import CanonicalIfcxModelPort
from infobim.project.domain.model.contract import ProjectContract


class CanonicalIfcxModel(CanonicalIfcxModelPort):
    """
    The project's own IFCX model, composed from converted IFC elements.

    One model per project, not one file per element: a conversion adds its
    element's contribution to the model the project already has, so the
    elements converted so far stay in one document that can grow. The model
    is addressed by the GlobalId of the project's IfcProject, which is what
    identifies the project itself, and it lives inside the reserved InfoBIM
    dataset — an internal artifact of this pipeline, neither stated in the
    RO-Crate nor read by anything that renders a project.

    Replacement is addressed by the source IFC element. A Writer decides
    what its contribution looks like inside the IFCX document, so the nodes
    a previous conversion of the same element left behind are the ones
    recorded for it, never ones guessed from a node-path convention this
    layer invented.
    """

    DOCUMENT_SEGMENTS: ClassVar[Tuple[str, ...]] = ("document", "ifcx")
    DOCUMENT_SUFFIX: ClassVar[str] = ".ifcx"
    DATA_KEY: ClassVar[str] = "data"
    SCHEMAS_KEY: ClassVar[str] = "schemas"
    IMPORTS_KEY: ClassVar[str] = "imports"
    PATH_KEY: ClassVar[str] = "path"
    URI_KEY: ClassVar[str] = "uri"

    def path(self, project_path: Path, project_global_id: str) -> Path:
        return project_path.joinpath(
            ProjectContract.DATASET_NAME,
            ProjectContract.PAYLOAD_DIRECTORY_NAME,
            *self.DOCUMENT_SEGMENTS,
            f"{project_global_id}{self.DOCUMENT_SUFFIX}",
        )

    def merge(
        self,
        project_path: Path,
        project_global_id: str,
        element_id: str,
        contribution: Dict[str, Any],
        superseded_nodes: Optional[List[str]] = None,
    ) -> List[str]:
        document: Dict[str, Any] = self._load_or_create(
            project_path,
            project_global_id,
        )
        nodes: List[Dict[str, Any]] = self._nodes_of(contribution, element_id)
        contributed: List[str] = [
            str(node[self.PATH_KEY])
            for node in nodes
            if isinstance(node.get(self.PATH_KEY), str)
        ]

        dropped: List[str] = list(superseded_nodes or []) + contributed
        document[self.DATA_KEY] = [
            node
            for node in document[self.DATA_KEY]
            if not (
                isinstance(node, dict)
                and isinstance(node.get(self.PATH_KEY), str)
                and node[self.PATH_KEY] in dropped
            )
        ]
        document[self.DATA_KEY].extend(nodes)

        self._merge_schemas(document, contribution)
        self._merge_imports(document, contribution)
        self._persist(project_path, project_global_id, document)

        return contributed

    @classmethod
    def _nodes_of(
        cls,
        contribution: Dict[str, Any],
        element_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Return the IFCX nodes a Writer contributed for one element.
        """
        if not isinstance(contribution, dict):
            raise ValueError(
                f"The IFCX contribution for {element_id} must be an object."
            )

        nodes: Any = contribution.get(cls.DATA_KEY)
        if not isinstance(nodes, list) or not all(
            isinstance(node, dict) for node in nodes
        ):
            raise ValueError(
                f"The IFCX contribution for {element_id} must carry its nodes "
                f"in a '{cls.DATA_KEY}' array."
            )

        return [deepcopy(node) for node in nodes]

    @classmethod
    def _merge_schemas(
        cls,
        document: Dict[str, Any],
        contribution: Dict[str, Any],
    ) -> None:
        """
        Add the schemas a contribution declares to the canonical model.
        """
        if cls.SCHEMAS_KEY not in contribution:
            return

        schemas: Any = contribution[cls.SCHEMAS_KEY]
        if not isinstance(schemas, dict):
            raise ValueError(
                f"An IFCX contribution's '{cls.SCHEMAS_KEY}' must be an object."
            )

        document[cls.SCHEMAS_KEY].update(deepcopy(schemas))

    @classmethod
    def _merge_imports(
        cls,
        document: Dict[str, Any],
        contribution: Dict[str, Any],
    ) -> None:
        """
        Add the imports a contribution declares, without repeating one.
        """
        if cls.IMPORTS_KEY not in contribution:
            return

        declared: Any = contribution[cls.IMPORTS_KEY]
        if not isinstance(declared, list):
            raise ValueError(
                f"An IFCX contribution's '{cls.IMPORTS_KEY}' must be an array."
            )

        known: List[Any] = [
            entry.get(cls.URI_KEY)
            for entry in document[cls.IMPORTS_KEY]
            if isinstance(entry, dict)
        ]
        entry: Any
        for entry in declared:
            if not isinstance(entry, dict) or cls.URI_KEY not in entry:
                raise ValueError(
                    f"Each IFCX import must be an object carrying a "
                    f"'{cls.URI_KEY}'."
                )

            if entry[cls.URI_KEY] in known:
                continue

            document[cls.IMPORTS_KEY].append(deepcopy(entry))
            known.append(entry[cls.URI_KEY])

    def _load_or_create(
        self,
        project_path: Path,
        project_global_id: str,
    ) -> Dict[str, Any]:
        """
        Return the project's canonical model, creating an empty one if needed.

        The first conversion of a project has no model to merge into, so one
        is created to receive that first contribution.
        """
        document_path: Path = self.path(project_path, project_global_id)
        if not document_path.is_file():
            return IfcxDocument.create(project_global_id, [])

        return IfcxDocument.validate(
            json.loads(document_path.read_text(encoding="utf-8")),
            str(document_path),
        )

    def _persist(
        self,
        project_path: Path,
        project_global_id: str,
        document: Dict[str, Any],
    ) -> Path:
        """
        Write the canonical model atomically, so no reader sees half of it.
        """
        document_path: Path = self.path(project_path, project_global_id)
        document_path.parent.mkdir(parents=True, exist_ok=True)
        serialized: str = json.dumps(document, ensure_ascii=False, indent=2)
        temporary_path: Path = document_path.with_name(
            f".{document_path.name}.tmp"
        )
        temporary_path.write_text(serialized + "\n", encoding="utf-8")
        temporary_path.replace(document_path)

        return document_path
