from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import CapabilityExecutor, TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.obdc import StorageObdcRepository
from ontobdc.storage.domain.port.obdc import StorageObdcRemoteModelPort

from ontobdc.container.adapter.remote_file import RemoteFileDownloader
from ontobdc.container.domain.model.remote import RemoteContainerUrl
from ontobdc.container.domain.port.downloader import RemoteFileDownloaderPort

from infobim.ifc.plugin.capability.transformation.ifc_project_ready import (
    IfcProjectReadyCapability,
)
from infobim.project.domain.model.contract import ProjectContract
from infobim.project.plugin.capability.transformation.project_dataset_ready import (
    ProjectDatasetReadyCapability,
)
from infobim.project.plugin.machine.project_remote.state import ProjectRemoteProcessState


class ProjectSetCapability(TransactionCapability):
    """
    Sets the InfoBIM project the remote connection downloaded.

    The reserved ``.__infobim__`` dataset and a default IfcProject are put
    in place directly, by running the same two capabilities a locally
    created project runs; the default IfcProject declaration is then
    replaced by the one the remote itself publishes.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.project.plugin.capability.transformation.target."
            "project_set"
        ),
        version="1.0.0",
        name="Project Set",
        description=(
            "Set the InfoBIM project the remote connection downloaded: the "
            "reserved dataset, and the IfcProject the remote publishes."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "remote", "ifc"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The InfoBIM project of the remote connection is set.",
            },
            "debug_entry": {
                "en": "Setting the InfoBIM project of the remote connection.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ProjectRemoteProcessState.PROJECT_SET.label(lang)

    def description(self, lang: str = "en") -> str:
        return ProjectRemoteProcessState.PROJECT_SET.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        CapabilityExecutor.execute(ProjectDatasetReadyCapability(), context)
        CapabilityExecutor.execute(IfcProjectReadyCapability(), context)

        project_path: Path = self._container_path(context)
        ifc_project_path: Path = (
            project_path
            / ProjectContract.DATASET_NAME
            / ProjectContract.PAYLOAD_DIRECTORY_NAME
            / ProjectContract.TRIPLE_DIRECTORY_NAME
            / ProjectContract.IFC_PROJECT_FILE_NAME
        )
        relative_path: str = str(ifc_project_path.relative_to(project_path))

        address: str = self._first_address(context)
        api_token_value: Any = context.get_parameter_value("remote_api_token")
        api_token: Any = api_token_value if isinstance(api_token_value, str) else None

        if ifc_project_path.exists():
            ifc_project_path.unlink()

        downloader: RemoteFileDownloaderPort = RemoteFileDownloader.for_runtime()
        downloader.download(
            f"{address.rstrip('/')}/{relative_path}", ifc_project_path, api_token
        )

        return {
            "resulting_state": ProjectRemoteProcessState.PROJECT_SET,
            "ifc_project_path": str(ifc_project_path),
        }

    @staticmethod
    def _container_path(context: CliContextPort) -> Path:
        container_path: Any = context.get_parameter_value("container_path")
        if isinstance(container_path, str) and container_path.strip():
            return Path(container_path)

        url: Any = context.get_parameter_value("remote_url")
        download_dir: Any = context.get_parameter_value("remote_download_dir")
        return RemoteContainerUrl.destination(url, download_dir).parent

    @staticmethod
    def _first_address(context: CliContextPort) -> str:
        url_value: Any = context.get_parameter_value("remote_url")
        path: Path = RemoteContainerUrl.destination(
            str(url_value).strip(), context.get_parameter_value("remote_download_dir")
        )
        remote: StorageObdcRemoteModelPort = StorageObdcRepository().read_remote(path)
        addresses: List[str] = list(remote.addresses())
        if not addresses:
            raise ValueError("The remote.ttl publishes no address to download files from.")

        return addresses[0]
