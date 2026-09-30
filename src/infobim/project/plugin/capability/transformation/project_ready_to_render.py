from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.project.domain.model.contract import ProjectContract
from infobim.project.plugin.machine.project_refresh.state import (
    ProjectRefreshProcessState,
)
# from infobim.project.plugin.check.is_project_ready_to_render.hotfix import (
#     main as refresh_project_ready_to_render,
# )


_LINKSET_DIRECTORY_NAME: str = "linkset"
_LINKSET_FILE_SUFFIX: str = ".ttl"


class ProjectReadyToRenderCapability(TransactionCapability):
    """
    Re-validates every DXF-to-DWG project linkset currently declared under
    the project's payload/linkset directory, ensuring each DXF document
    points to its source DWG, carries a globalId_IfcRoot and a
    name_IfcRoot, and is modeled as an ifcOWL IfcDocumentInformation --
    the five conditions that collectively make a project "ready to
    render" by the 3D layer.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.project.plugin.capability.transformation.target."
            "project_ready_to_render"
        ),
        version="1.0.0",
        name="Project Ready To Render",
        description=(
            "Re-validate every DXF/DWG project linkset under the "
            "project's payload/linkset directory against the five "
            "is_drawing_linked_to_project integrity conditions after "
            "the container refresh step."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "drawing", "linkset", "refresh", "render"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Every DXF/DWG project linkset currently declared "
                    "under the project's payload/linkset directory is "
                    "re-validated against the is_drawing_linked_to_project "
                    "integrity conditions."
                ),
            },
            "debug_entry": {
                "en": (
                    "Re-validating per-linkset drawing-to-project "
                    "integrity on every linkset declared under the "
                    "project payload/linkset directory."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Project Ready To Render"

    def description(self, lang: str = "en") -> str:
        return (
            "Re-validates every linkset file under the project's "
            "payload/linkset directory against the drawing-to-project "
            "integrity contract after the container refresh step."
        )

    @staticmethod
    def _linkset_paths(project_path: Path) -> List[Path]:
        linkset_directory: Path = (
            project_path
            / ProjectContract.DATASET_NAME
            / ProjectContract.PAYLOAD_DIRECTORY_NAME
            / _LINKSET_DIRECTORY_NAME
        )
        if not linkset_directory.is_dir():
            return []

        linkset_paths: List[Path] = []
        candidate: Path
        for candidate in linkset_directory.rglob(f"*{_LINKSET_FILE_SUFFIX}"):
            if candidate.is_file():
                linkset_paths.append(candidate.resolve())

        return linkset_paths

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path_value: Any = context.get_parameter_value("container_path")
        if not isinstance(project_path_value, str) or not project_path_value.strip():
            raise ValueError(
                "The project path is missing from the command context."
            )

        project_path: Path = Path(project_path_value).expanduser().resolve()
        exit_code: int = refresh_project_ready_to_render(
            project_path=str(project_path),
            container_path=str(project_path),
            root_path=str(context.root_path),
        )
        if exit_code != 0:
            raise RuntimeError(
                f"Failed to refresh per-linkset drawing-to-project "
                f"integrity for the project at {project_path}."
            )

        linkset_paths: List[Path] = (
            ProjectReadyToRenderCapability._linkset_paths(project_path)
        )

        return {
            "resulting_state": ProjectRefreshProcessState.PROJECT_READY_TO_RENDER,
            "project_path": str(project_path),
            "linkset_count": len(linkset_paths),
            "linksets": [str(path) for path in linkset_paths],
        }
