from pathlib import Path
from typing import List

from infobim.project.domain.machine.state import ProjectCreateProcessState
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse


class ProjectCreateResponseRenderer:
    """Render the terminal response for the project creation lifecycle."""

    def render(
        self,
        *,
        target_path: Path,
        current_state: ProjectCreateProcessState,
        visited_states: List[str],
    ) -> CommandResponse:
        if current_state == ProjectCreateProcessState.INVALID_PATH:
            return ExceptionCommandResponse(
                title="Invalid InfoBIM Project Path",
                description="The target path is an existing file and cannot become an InfoBIM project.",
                content={
                    "path": str(target_path),
                    "current_state": current_state.value,
                    "visited_states": visited_states,
                },
            )

        return CommandResponse(
            title="InfoBIM Project Created",
            description="The OntoBDC container, reserved .__infobim__ dataset, IfcProject facade, and editable IfcProject instance are ready.",
            content={
                "path": str(target_path),
                "current_state": current_state.value,
                "visited_states": visited_states,
                "project_dataset": str(target_path / ".__infobim__"),
                "exists": target_path.exists(),
            },
        )
