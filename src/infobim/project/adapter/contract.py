from pathlib import Path
from typing import Any, Dict, List, Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.shared.domain.vocabulary import OBDC
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.file import StorageFileLocator
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from infobim.project.domain.model.contract import ProjectContract
from infobim.project.plugin.check.is_project_dataset_ready.check import (
    main as check_project_dataset_ready,
)
from infobim.project.plugin.check.is_project_dataset_ready.hotfix import (
    main as hotfix_project_dataset_ready,
)

class ProjectGuard:
    """
    Tells a container that is an InfoBIM project from one that is not.

    Every project is a container, but a container becomes a project only by
    carrying the reserved InfoBIM dataset. The commands under ``project``
    delegate to the container commands, so without this guard they would act
    on any registered container — including ones the InfoBIM domain knows
    nothing about.
    """

    @staticmethod
    def is_project(project_path: Path, root_path: str) -> bool:
        """
        Report whether the container at the given path is a project.

        Containers that physically carry the reserved dataset directory are
        treated as project candidates: if their dataset descriptor is stale
        (e.g. because the container directory was renamed on disk after the
        last successful attach), the project hotfix is applied before the
        final readiness check.  Containers without the reserved dataset
        directory at all are reported as non-projects without touching disk.
        """
        resolved_project_path: Path = project_path.expanduser().resolve()
        dataset_path: Path = resolved_project_path / ProjectContract.DATASET_NAME
        if not dataset_path.is_dir():
            return False

        project_path_str: str = str(resolved_project_path)
        root_path_str: str = str(Path(root_path).expanduser().resolve())

        if check_project_dataset_ready(
            project_path=project_path_str,
            root_path=root_path_str,
        ) == 0:
            return True

        hotfix_project_dataset_ready(
            project_path=project_path_str,
            root_path=root_path_str,
        )

        return check_project_dataset_ready(
            project_path=project_path_str,
            root_path=root_path_str,
        ) == 0

    @classmethod
    def guard(cls, project_path: Path, root_path: str) -> None:
        """
        Let a project through, and refuse anything else by name.

        Before refusing a candidate that physically carries the reserved
        dataset directory, the dataset descriptor is repaired in place using
        the project hotfix so that common recoverable situations — such as
        the container directory being renamed — do not surface as a generic
        "not a project" error.
        """
        resolved_project_path: Path = project_path.expanduser().resolve()
        dataset_path: Path = resolved_project_path / ProjectContract.DATASET_NAME
        if not dataset_path.is_dir():
            raise CliCommandArgumentException(
                f"{project_path} is a container, not an InfoBIM project: it does "
                f"not carry the reserved {ProjectContract.DATASET_NAME} dataset."
            )

        if cls.is_project(resolved_project_path, root_path):
            return

        raise CliCommandArgumentException(
            f"{project_path} carries the reserved {ProjectContract.DATASET_NAME} "
            f"dataset but its project descriptor could not be reconciled with "
            f"its current location."
        )

    @staticmethod
    def registered_projects(root_path: str) -> List[Dict[str, Optional[str]]]:
        """
        Return the registered containers that are projects, as the index
        describes them.

        Storage index entries whose registered container identifier does not
        match the DCTERMS.identifier written inside the on-disk container
        graph are skipped: they describe a container that used to live at
        that location in a previous attach but was afterwards renamed or
        replaced by a different container graph (different UUID). Keeping
        them in the listing would surface duplicate project rows for the
        same physical directory or stale rows pointing to directories that
        now belong to a different container identity.
        """
        storage_graph: LoadedStorageGraph = LoadedStorageGraph(
            StorageFileLocator.resolve(root_path)
        )
        projects: List[Dict[str, Optional[str]]] = []
        container: Dict[str, Optional[str]]
        for container in storage_graph.storage_graph.list_containers():
            location: Optional[Path] = ProjectGuard._location_of(container)
            if location is None:
                continue
            if not ProjectGuard._container_identity_matches(
                storage_index_container=container,
                container_path=location,
            ):
                continue
            if ProjectGuard.is_project(location, root_path):
                projects.append(container)

        return projects

    @staticmethod
    def _container_identity_matches(
        *,
        storage_index_container: Dict[str, Any],
        container_path: Path,
    ) -> bool:
        """
        Return True when the DCTERMS.identifier declared by the on-disk
        container.ttl graph is the same identifier the storage index uses.
        """
        registered_id: Any = storage_index_container.get("id")
        if not isinstance(registered_id, str) or not registered_id.strip():
            return False

        container_storage_file_path: Path = (
            StorageBootstrap.get_container_storage_file_path(
                container_path.expanduser().resolve(),
            )
        )
        if not container_storage_file_path.is_file():
            return False

        container_graph: Graph = Graph()
        try:
            container_graph.parse(str(container_storage_file_path), format="turtle")
        except Exception:
            return False

        subjects: List[URIRef] = [
            subject
            for subject in container_graph.subjects(RDF.type, OBDC.DataContainer)
            if isinstance(subject, URIRef)
        ]
        if len(subjects) != 1:
            return False

        values: List[object] = list(
            container_graph.objects(subjects[0], DCTERMS.identifier)
        )
        if len(values) != 1:
            return False

        identifier_obj: object = values[0]
        if isinstance(identifier_obj, Literal):
            disk_id: str = str(identifier_obj).strip()
        elif isinstance(identifier_obj, URIRef):
            disk_id = str(identifier_obj).strip()
        else:
            return False

        return disk_id == registered_id.strip()

    @staticmethod
    def location_of(container_id: str, root_path: str) -> Optional[Path]:
        """
        Return the path the index registers for the given container id.
        """
        storage_graph: LoadedStorageGraph = LoadedStorageGraph(
            StorageFileLocator.resolve(root_path)
        )
        container: Dict[str, Optional[str]]
        for container in storage_graph.storage_graph.list_containers():
            registered_id: Optional[str] = container.get("id")
            if not isinstance(registered_id, str):
                continue
            if registered_id.strip() != container_id.strip():
                continue

            return ProjectGuard._location_of(container)

        return None

    @staticmethod
    def _location_of(container: Dict[str, Any]) -> Optional[Path]:
        """
        Return the filesystem path the index records for a container entry.
        """
        location: Any = container.get("location")
        if not isinstance(location, str) or not location.strip():
            return None

        return Path(location).expanduser().resolve()

    @classmethod
    def ifc_project_global_id(cls, project_path: Path) -> Optional[str]:
        """
        Return the GlobalId of the IfcProject the project declares.

        None when the project carries no readable IfcProject — which is what
        a container that is not a project looks like from here, and also
        what a dataset declaring more than one looks like: naming the
        project would mean picking one of them, and the check that reports
        project health refuses that same graph.
        """
        dataset_path: Path = project_path / ProjectContract.DATASET_NAME
        ifc_project_path: Path = (
            dataset_path
            / ProjectContract.PAYLOAD_DIRECTORY_NAME
            / ProjectContract.TRIPLE_DIRECTORY_NAME
            / ProjectContract.IFC_PROJECT_FILE_NAME
        )
        if not ifc_project_path.is_file():
            return None

        graph: Graph = Graph()
        try:
            graph.parse(str(ifc_project_path), format="turtle")
        except Exception:
            return None

        subjects: List[URIRef] = [
            subject
            for subject in graph.subjects(
                RDF.type,
                URIRef(ProjectContract.IFC_PROJECT_CLASS),
            )
            if isinstance(subject, URIRef)
        ]
        if len(subjects) != 1:
            return None

        for value in graph.objects(
            subjects[0],
            URIRef(ProjectContract.IFC_PROJECT_GLOBAL_ID_PROPERTY),
        ):
            global_id: str = str(value).strip()
            if global_id:
                return global_id

        return None
