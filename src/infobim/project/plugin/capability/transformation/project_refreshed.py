from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from ontobdc.container.domain.model.remote import RemoteContainerUrl
from infobim.project.plugin.machine.project_refresh.machine import (
    ProjectRefreshStateTransitionHandler,
)
from infobim.project.plugin.machine.project_refresh.port import (
    ProjectRefreshStateTransitionHandlerPort,
)
from infobim.project.plugin.machine.project_remote.state import ProjectRemoteProcessState


class ProjectRefreshedCapability(TransactionCapability):
    """
    Refreshes the InfoBIM-specific parts of the project the remote
    connection downloaded, by running the same project-refresh machine
    ``project --refresh`` runs.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.project.plugin.capability.transformation.target."
            "project_refreshed"
        ),
        version="1.0.0",
        name="Project Refreshed",
        description=(
            "Refresh the InfoBIM-specific parts of the project the remote "
            "connection downloaded."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "remote", "refresh"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The InfoBIM project of the remote connection was refreshed.",
            },
            "debug_entry": {
                "en": "Refreshing the InfoBIM project of the remote connection.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ProjectRemoteProcessState.PROJECT_REFRESHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ProjectRemoteProcessState.PROJECT_REFRESHED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Any = context.get_parameter_value("container_path")
        if not isinstance(container_path, str) or not container_path.strip():
            url: Any = context.get_parameter_value("remote_url")
            download_dir: Any = context.get_parameter_value("remote_download_dir")
            container_path = str(
                RemoteContainerUrl.destination(url, download_dir).parent
            )
            context.set_parameter_value("container_path", container_path)

        handler: ProjectRefreshStateTransitionHandlerPort = (
            ProjectRefreshStateTransitionHandler(context=context)
        )
        response: CommandResponse = handler.execute()

        return {
            "resulting_state": ProjectRemoteProcessState.PROJECT_REFRESHED,
            "container_path": container_path,
            **(response.content or {}),
        }
