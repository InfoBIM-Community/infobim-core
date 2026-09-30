import json
from typing import Any, Optional
from pathlib import Path

from rdflib import Graph

from infobim.project.domain.model.contract import ProjectContract


def _ifc_project_path(project_path: Path) -> Path:
    return (
        project_path
        / ProjectContract.DATASET_NAME
        / ProjectContract.PAYLOAD_DIRECTORY_NAME
        / ProjectContract.TRIPLE_DIRECTORY_NAME
        / ProjectContract.IFC_PROJECT_FILE_NAME
    )


def build_ifc_project_jsonld(project_path: Path) -> Any:
    """
    Return the Project's declared IfcProject, serialized as JSON-LD.

    Read fresh from ifc_project.ttl on every call: this is the payload
    the viewer page embeds for the current launch, not something to
    cache across invocations the way the other states in this codebase's
    machines cache a completed, durable step.
    """
    ifc_project_path: Path = _ifc_project_path(project_path)
    if not ifc_project_path.is_file():
        raise ValueError(f"The Project declares no IfcProject: {ifc_project_path}")

    graph: Graph = Graph()
    graph.parse(str(ifc_project_path), format="turtle")
    serialized: str = graph.serialize(format="json-ld")
    return json.loads(serialized)


def main(project_path: Optional[str] = None) -> int:
    if not isinstance(project_path, str) or not project_path.strip():
        return 1

    try:
        build_ifc_project_jsonld(Path(project_path).expanduser().resolve())
    except Exception:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
