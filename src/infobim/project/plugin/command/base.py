from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, RDFS, Namespace

from infobim.project.plugin.check.is_project_ready.check import main as check_project_ready
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import ExceptionCommandResponse, ListCommandResponse
from ontobdc.storage import get_storage_file
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter


_IFCOWL: Namespace = Namespace("http://ifcowl.openbimstandards.org/IFC4#")
_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
_OBDC: Namespace = _ontology_adapter.get_ontology_by_prefix("obdc")


class ProjectBaseCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="project",
        description="List active InfoBIM projects registered in the current storage.",
        usage="infobim project",
        arguments=[],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) == 1 and args[0] == "project"

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return len(self._request.command_args) == 0

    def run(self) -> ListCommandResponse | ExceptionCommandResponse:
        root_path: Path = Path(self._request.context.root_path).expanduser().resolve()
        storage_file: Path = Path(get_storage_file(root_path=str(root_path))).expanduser().resolve()

        if not storage_file.is_file():
            return ExceptionCommandResponse(
                title="Project List",
                description="Could not locate the storage index for the current workspace.",
                content={
                    "root_path": str(root_path),
                    "storage_file": str(storage_file),
                },
            )

        try:
            projects: List[Dict[str, str]] = self._list_projects(storage_file)
        except Exception as error:
            return ExceptionCommandResponse(
                title="Project List",
                description="Failed to list active InfoBIM projects.",
                content={
                    "root_path": str(root_path),
                    "storage_file": str(storage_file),
                    "error": str(error),
                },
            )

        return ListCommandResponse(
            title="Active InfoBIM Projects",
            description=f"Found {len(projects)} active project(s) in the current storage.",
            content=projects,
        )

    def _list_projects(self, storage_file: Path) -> List[Dict[str, str]]:
        storage_graph: Graph = Graph()
        storage_graph.parse(str(storage_file), format="turtle")

        projects: List[Dict[str, str]] = []
        subject: URIRef
        for subject in storage_graph.subjects(RDF.type, _OBDC.DataContainer):
            if not isinstance(subject, URIRef):
                continue

            container_path: Optional[Path] = self._resolve_container_path(storage_graph, subject)
            if container_path is None:
                continue

            if check_project_ready(container_path=str(container_path)) != 0:
                continue

            project_record: Optional[Dict[str, str]] = self._build_project_record(container_path)
            if project_record is None:
                continue

            projects.append(project_record)

        return sorted(
            projects,
            key=lambda project: (
                str(project.get("name", "")).lower(),
                str(project.get("path", "")).lower(),
            ),
        )

    def _resolve_container_path(self, storage_graph: Graph, subject: URIRef) -> Optional[Path]:
        location_values: List[object] = list(storage_graph.objects(subject, PROV.atLocation))
        if len(location_values) != 1:
            return None

        location: object = location_values[0]
        if not isinstance(location, URIRef):
            return None

        parsed = urlparse(str(location))
        if parsed.scheme != "file":
            return None

        return Path(url2pathname(unquote(parsed.path))).expanduser().resolve()

    def _build_project_record(self, container_path: Path) -> Optional[Dict[str, str]]:
        container_name: str = container_path.name.strip() or container_path.as_posix()
        project_file: Path = container_path / ".__ontobdc__" / "__infobim__" / "project.ttl"
        if not project_file.is_file():
            return {
                "project_id": f"urn:infobim:project:{container_name}",
                "name": container_name,
                "path": str(container_path),
            }

        project_graph: Graph = Graph()
        project_graph.parse(str(project_file), format="turtle")

        subjects: List[URIRef] = [
            subject
            for subject in project_graph.subjects(RDF.type, _IFCOWL.IfcProject)
            if isinstance(subject, URIRef)
        ]
        if not subjects:
            return {
                "project_id": f"urn:infobim:project:{container_name}",
                "name": container_name,
                "path": str(container_path),
            }

        project_subject: URIRef = subjects[0]
        project_name: str = container_name
        for predicate in (DCTERMS.title, RDFS.label):
            values: List[str] = [
                str(value).strip()
                for value in project_graph.objects(project_subject, predicate)
                if isinstance(value, Literal) and str(value).strip()
            ]
            if values:
                project_name = values[0]
                break

        return {
            "project_id": str(project_subject),
            "name": project_name,
            "path": str(container_path),
        }
