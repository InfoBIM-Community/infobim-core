from pathlib import Path
from collections.abc import Mapping as MappingABC
from typing import Any, ClassVar, Dict, List, Mapping, Optional

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.hotfix import (
    main as hotfix_container_storage_index_ready,
)

from infobim.project.domain.model.contract import ProjectContract
from infobim.project.plugin.check.is_project_dataset_ready.check import (
    main as check_project_dataset_ready,
)
from infobim.project.plugin.check.is_project_dataset_ready.hotfix import (
    main as hotfix_project_dataset_ready,
)
from ontobdc.container.plugin.command.attach import ContainerAttachCommand


class ProjectAttachCommand(CliCommandPort):
    """
    Attach an imported InfoBIM project through the container attach pipeline.

    A project is an OntoBDC container that carries the reserved InfoBIM
    dataset. Attaching one therefore means attaching the container
    underneath it — but not before refusing anything that does not carry
    the dataset, so an operator who accidentally types the wrong path does
    not end up registering a plain container as a project.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_attach",
        logical_component="project",
        description=(
            "Attach an imported InfoBIM project onto the current storage "
            "root."
        ),
        arguments=[
            {
                "accepts": ["--project-path", "--project"],
                "valued": True,
                "parameter": "project_path",
                "description": (
                    "Filesystem path of the imported InfoBIM project "
                    "container to attach. When omitted, use the current "
                    "working directory as the project target."
                ),
                "type": "Path",
            },
            {
                "accepts": ["--attach"],
                "description": (
                    "Validate the project container's metadata, register "
                    "it in the root storage index and then run the "
                    "project refresh pipeline so datasets, manifests and "
                    "RO-Crate agree with what the container actually "
                    "holds."
                ),
                "valued": True,
                "type": "bool",
            },
        ],
    )

    PROJECT_FLAGS: ClassVar[tuple] = ("--project-path", "--project")
    ATTACH_FLAG: ClassVar[str] = "--attach"
    COMPONENT: ClassVar[str] = "project"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the project attach command at the CLI routing stage.
        """
        if not args or args[0] != ProjectAttachCommand.COMPONENT:
            return False

        attach_seen: bool = False
        project_flag_seen: bool = False
        idx: int = 1
        total: int = len(args)
        while idx < total:
            token: str = args[idx]
            if token == ProjectAttachCommand.ATTACH_FLAG:
                if attach_seen:
                    return False
                attach_seen = True
                idx += 1
                continue
            if token in ProjectAttachCommand.PROJECT_FLAGS:
                if project_flag_seen:
                    return False
                if idx + 1 >= total:
                    return False
                next_token: str = str(args[idx + 1]).strip()
                if not next_token or next_token.startswith("--"):
                    return False
                project_flag_seen = True
                idx += 2
                continue
            return False

        if not attach_seen:
            return False
        expected_tokens_min: int = 1  # project word excluded
        actual_rest: int = total - 1
        if project_flag_seen:
            expected_tokens_min = 3  # project_flag value attach
        if actual_rest < expected_tokens_min:
            return False
        return True

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Validate attach arguments, guard project contract, set context.
        """
        command_args: List[str] = list(self._request.command_args)
        attach_flag_seen: bool = False
        raw_project_path: Optional[str] = None
        idx: int = 0
        total: int = len(command_args)
        while idx < total:
            token: str = command_args[idx]
            if token == self.ATTACH_FLAG:
                if attach_flag_seen:
                    return False
                attach_flag_seen = True
                idx += 1
                continue
            if token in self.PROJECT_FLAGS:
                if idx + 1 >= total:
                    return False
                candidate: Any = command_args[idx + 1]
                if not isinstance(candidate, str) or not candidate.strip():
                    return False
                if raw_project_path is not None:
                    return False
                raw_project_path = candidate.strip()
                idx += 2
                continue
            return False

        if not attach_flag_seen:
            return False
        if raw_project_path is None:
            try:
                raw_project_path = str(Path.cwd().expanduser().resolve())
            except (OSError, RuntimeError, ValueError):
                return False

        resolved_project_path: Path = (
            Path(raw_project_path).expanduser().resolve()
        )
        if not resolved_project_path.is_dir():
            return False
        dataset_path: Path = resolved_project_path / ProjectContract.DATASET_NAME
        if not dataset_path.is_dir():
            raise CliCommandArgumentException(
                f"Directory is not an InfoBIM project: {resolved_project_path}",
                command_args=command_args,
            )
        self._request.context.set_parameter_value(
            "project_path",
            str(resolved_project_path),
        )
        self._request.context.set_parameter_value(
            "container_path",
            str(resolved_project_path),
        )
        return True

    def run(self) -> CommandResponse:
        """
        Drive the container attach pipeline under InfoBIM project guard,
        then reconcile the reserved InfoBIM dataset descriptor so the
        project passes its own readiness checks immediately afterwards.
        """
        target: Any = self._request.context.get_parameter_value(
            "project_path"
        )
        if not isinstance(target, str) or not target.strip():
            target = self._request.context.get_parameter_value(
                "container_path"
            )
        if not isinstance(target, str) or not target.strip():
            raise ValueError(
                "ProjectAttachCommand.run requires project_path or "
                "container_path in context."
            )

        proxy_request: CliCommandRequest = CliCommandRequest(
            logical_component=ContainerAttachCommand.METADATA.logical_component,
            component_action=ContainerAttachCommand.METADATA.id,
            command_args=[
                "--container-path",
                target.strip(),
                "--attach",
            ],
            context=self._request.context,
        )
        proxy: ContainerAttachCommand = ContainerAttachCommand(proxy_request)
        if not proxy.check():
            raise ValueError(
                "The underlying OntoBDC container attach command refused "
                "the resolved project path."
            )

        response: CommandResponse = proxy.run()
        response_content: Any = response.content
        if response_content is None:
            content: Dict[str, Any] = {"project_path": target.strip()}
        elif isinstance(response_content, MappingABC):
            content = {str(key): value for key, value in response_content.items()}
            if "project_path" not in content:
                content["project_path"] = target.strip()
        else:
            raise TypeError(
                "ProjectAttachCommand: ContainerAttachCommand.run() returned "
                "response.content with unexpected type "
                f"{type(response_content).__name__!r}; expected None or a "
                "mapping with command output keys."
            )

        self._ensure_project_dataset_ready(project_path=target.strip())

        title: str = response.title
        if title == "Storage Container Attached":
            title = "InfoBIM Project Attached"

        return CommandResponse(
            title=title,
            description=response.description,
            content=content,
            severity=response.severity,
        )

    @staticmethod
    def _ensure_project_dataset_ready(*, project_path: str) -> None:
        """
        Reconcile the reserved InfoBIM dataset descriptor with the actual
        state left on disk by the container attach pipeline.

        After renaming a project on disk or re-running attach on an
        existing one, the pre-existing dataset.ttl inside the reserved
        .__infobim__ directory can still reference its old location or
        old owning container identifier. Running the project hotfix once
        rewrites those metadata values from the current container.ttl
        and current filesystem layout so the guard and subsequent
        commands (refresh, update, health, inspect, delete) accept it
        as a valid project without further intervention.
        """
        resolved_project_path: Path = Path(project_path).expanduser().resolve()
        root_path_value: str = str(resolved_project_path)
        if check_container_storage_index_ready(
            container_path=str(resolved_project_path),
            root_path=root_path_value,
        ) != 0:
            if hotfix_container_storage_index_ready(
                container_path=str(resolved_project_path),
                root_path=root_path_value,
            ) != 0:
                raise ValueError(
                    "Failed to reconcile the container storage index "
                    "entry with the container graph produced by the "
                    "attach pipeline."
                )
        if check_container_storage_index_ready(
            container_path=str(resolved_project_path),
            root_path=root_path_value,
        ) != 0:
            raise ValueError(
                "The container storage index entry is still "
                "inconsistent after the attach hotfix."
            )
        if check_project_dataset_ready(
            project_path=str(resolved_project_path),
            root_path=root_path_value,
        ) != 0:
            if hotfix_project_dataset_ready(
                project_path=str(resolved_project_path),
                root_path=root_path_value,
            ) != 0:
                raise ValueError(
                    "Failed to reconcile the reserved InfoBIM dataset "
                    "descriptor with the container produced by the "
                    "attach pipeline."
                )
        if check_project_dataset_ready(
            project_path=str(resolved_project_path),
            root_path=root_path_value,
        ) != 0:
            raise ValueError(
                "The reserved InfoBIM dataset descriptor is still "
                "inconsistent after the project attach hotfix."
            )
