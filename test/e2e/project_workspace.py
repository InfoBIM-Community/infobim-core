"""On-disk project fixtures, independent of the project-create command."""

import json
from typing import Any, Callable, Dict, List, Set, Tuple
from pathlib import Path
from dataclasses import dataclass

from rdflib import Graph, URIRef

from infobim.project.domain.model.contract import ProjectContract
from test.e2e.cli_process_runner import (
    CliInvocationResult,
    InfobimCliProcessRunner,
    OntobdcCliProcessRunner,
)
from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
    main as prepare_metadata,
)
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as prepare_manifest,
)
from ontobdc.container.plugin.check.is_container_datapackage_updated.hotfix import (
    main as prepare_datapackage,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.hotfix import (
    main as prepare_storage_index,
)
from infobim.project.plugin.check.is_project_dataset_ready.hotfix import (
    main as prepare_project_dataset,
)
from infobim.project.plugin.check.is_ifc_project_ready.hotfix import (
    main as prepare_ifc_project,
)
from infobim.project.plugin.check.is_ifc_project_schema_ready.hotfix import (
    main as prepare_ifc_project_schema,
)


@dataclass(frozen=True)
class ProjectE2eWorkspace:
    root: Path
    project: Path
    identifier: str

    @classmethod
    def create(
        cls, root: Path, name: str = "project-under-test"
    ) -> "ProjectE2eWorkspace":
        root = root.resolve()
        ontobdc_runner: OntobdcCliProcessRunner = OntobdcCliProcessRunner(root)
        initialized: CliInvocationResult = ontobdc_runner.run("init")
        assert initialized.exit_code == 0, initialized.stdout + initialized.stderr
        project: Path = root / name
        project.mkdir()
        container_repairs: Tuple[Callable[..., int], ...] = (
            prepare_metadata,
            prepare_storage_index,
            prepare_datapackage,
            prepare_manifest,
        )
        repair: Callable[..., int]
        for repair in container_repairs:
            assert repair(container_path=str(project), root_path=str(root)) == 0, (
                repair.__module__
            )
        assert (
            prepare_project_dataset(
                project_path=str(project),
                root_path=str(root),
            )
            == 0
        ), "prepare_project_dataset"
        assert prepare_ifc_project(project_path=str(project)) == 0, "prepare_ifc_project"
        assert (
            prepare_ifc_project_schema(project_path=str(project)) == 0
        ), "prepare_ifc_project_schema"
        infobim_runner: InfobimCliProcessRunner = InfobimCliProcessRunner(root)
        listing: CliInvocationResult = infobim_runner.run("project", "--list")
        assert listing.exit_code == 0, listing.stdout + listing.stderr
        projects: List[Dict[str, Any]] = listing.json["content"]["projects"]
        matches: List[Dict[str, Any]] = [
            entry
            for entry in projects
            if Path(entry["location"]).resolve() == project
        ]
        assert len(matches) == 1, projects
        identifier: Any = matches[0]["id"]
        assert isinstance(identifier, str) and identifier.startswith("urn:uuid:")
        # `project --create` ends with the same refresh `project --refresh`
        # runs, so a fixture project goes through it too.
        refreshed: CliInvocationResult = infobim_runner.run(
            "project", "--global-id", identifier, "--refresh"
        )
        assert refreshed.exit_code == 0, refreshed.stdout + refreshed.stderr
        assert refreshed.json["title"] == "InfoBIM Project Refreshed", refreshed.stdout
        assert refreshed.json["content"]["current_state"] == "__project_ready_to_render__"
        return cls(root=root, project=project, identifier=identifier)

    def runner(self) -> InfobimCliProcessRunner:
        return InfobimCliProcessRunner(self.project)

    def snapshot(self) -> Dict[str, bytes]:
        files: Dict[str, bytes] = {}
        path: Path
        for path in self.project.rglob("*"):
            if path.is_file():
                files[path.relative_to(self.project).as_posix()] = path.read_bytes()
        return files

    def manifest_files(self) -> Set[str]:
        manifest: Dict[str, Any] = json.loads(
            (self.project / ".__ontobdc__" / "ro-crate-metadata.json").read_text(
                encoding="utf-8"
            )
        )
        nodes: List[Dict[str, Any]] = manifest["@graph"]
        return {node["@id"] for node in nodes if node.get("@type") == "File"}

    def selector(self, kind: str) -> str:
        if kind == "id":
            return self.identifier
        if kind == "path":
            return str(self.project)
        raise ValueError(f"Unknown fixture selector: {kind}")

    def global_id(self) -> str:
        graph: Graph = Graph().parse(
            self.project / ".__infobim__" / "payload" / "triple" / "ifc_project.ttl",
            format="turtle",
        )
        identifiers: List[str] = [
            str(value)
            for value in graph.objects(
                None, URIRef(ProjectContract.IFC_PROJECT_GLOBAL_ID_PROPERTY)
            )
        ]
        assert len(identifiers) == 1, identifiers
        return identifiers[0]
