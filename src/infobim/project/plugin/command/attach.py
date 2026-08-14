from pathlib import Path
from typing import List

from infobim.project.domain.model.contract import PROJECT_DATASET_NAME
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class ProjectAttachCommand(CliCommandPort):
    """Attach an imported InfoBIM Project through the OntoBDC container lifecycle."""

    METADATA = CliCommandMetadata(
        id="project_attach",
        logical_component="project",
        description="Attach an imported InfoBIM Project to the current OntoBDC storage root.",
        arguments=[
            {
                "accepts": ["--project-path"],
                "valued": True,
                "description": "Filesystem path of the imported InfoBIM Project.",
                "usage": "infobim project --project-path <path> --attach",
            },
            {
                "accepts": ["--attach"],
                "description": "Attach the imported InfoBIM Project.",
                "usage": "infobim project --project-path <path> --attach",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 4
            and args[0] == "project"
            and args[1] == "--project-path"
            and bool(str(args[2]).strip())
            and args[3] == "--attach"
        )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args = list(self._request.command_args)
        if not (len(args) == 3 and args[0] == "--project-path" and args[2] == "--attach"):
            return False
        target = Path(str(args[1])).expanduser().resolve()
        if not target.is_dir():
            return False
        if not (target / PROJECT_DATASET_NAME).is_dir():
            raise ValueError(f"Not an InfoBIM Project: missing {PROJECT_DATASET_NAME} in {target}")
        self._request.context.set_parameter_value("project_path", str(target))
        return True

    def run(self) -> CommandResponse:
        # Imported here, not at module level -- see the identical note in
        # context/plugin/command/entity.py (CommandLoader discovery would
        # otherwise see this as a second candidate for InfoBIM's own
        # "project" domain).
        from ontobdc.storage.plugin.command.container.attach import StorageAttachCommand

        target = str(self._request.context.get_parameter_value("project_path") or "")
        proxy_request = CliCommandRequest(
            logical_component="storage",
            component_action=StorageAttachCommand.METADATA.id,
            command_args=["--container-path", target, "--attach"],
            context=self._request.context,
        )
        proxy = StorageAttachCommand(proxy_request)
        if not proxy.check():
            raise ValueError("Underlying OntoBDC attach command rejected the resolved path.")

        response = proxy.run()
        if response.title == "Storage Container Attached":
            response.title = "InfoBIM Project Attached"
        return response
