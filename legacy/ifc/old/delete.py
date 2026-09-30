from pathlib import Path
from typing import Any, ClassVar, List, Optional, Tuple

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)

from infobim.ifc.plugin.machine.geometric_product_delete.machine import (
    GeometricProductDeleteStateTransitionHandler,
)
from infobim.project.adapter.contract import ProjectGuard


class IfcDeleteCommand(CliCommandPort, LoggerAwarePort):
    """
    Removes one IFC geometric product from the project's federated model.

    Removal is addressed by GlobalId rather than by title, because two
    distinct runs can name a product the same and two products never share
    a GlobalId. What gets removed is the element under the identity the
    user gave, plus every entity only that element owned — its
    representation, the geometry items wrapped by that representation,
    and its local placement. The project's own representation contexts,
    the spatial structure, and the placement chain above the product are
    all preserved.

    After defederation the assembled state directory that produced the
    product is also removed, so a later recreate under the same
    GlobalId does not find stale STEP fragments left behind.

    Runs through the deletion state machine of
    ``GeometricProductDeleteStateTransitionHandler``.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_delete",
        logical_component="ifc",
        description=(
            "Delete an IFC geometric product (by GlobalId) from the "
            "project's IFC model."
        ),
        arguments=[
            {
                "accepts": ["--delete"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "GlobalId of the IFC element to delete."
                ),
                "usage": (
                    "infobim ifc --delete <global_id> "
                    "[--ifc-model-path <path>]"
                ),
            },
            {
                "accepts": ["--ifc-model-path"],
                "valued": True,
                "parameter": "ifc_model_path",
                "description": (
                    "IFC model to remove the element from; resolved "
                    "from the project when it is not given."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    FLAG: ClassVar[str] = "--delete"
    IFC_MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    FLAGS: ClassVar[List[str]] = [
        FLAG,
        IFC_MODEL_PATH_FLAG,
    ]
    GLOBAL_ID_KEY: ClassVar[str] = "global_id"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != IfcDeleteCommand.COMPONENT:
            return False

        return IfcDeleteCommand._values(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Any = None

    @property
    def log_strategy(self) -> Any:
        return self._log_strategy

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        values: Optional[Tuple[str, Optional[str]]] = self._values(
            self._request.command_args
        )
        if values is None:
            return False

        container_value: Any = self._request.context.get_parameter_value(
            self.CONTAINER_PATH_KEY
        )
        if not isinstance(container_value, str) or not container_value.strip():
            raise CliCommandArgumentException(
                "No InfoBIM Project was resolved. Run this command inside one."
            )

        container_path: Path = Path(container_value).expanduser().resolve()
        ProjectGuard.guard(container_path, self._request.context.root_path)

        global_id_value, ifc_model_path_value = values

        self._request.context.set_parameter_value(
            self.GLOBAL_ID_KEY, global_id_value
        )
        if ifc_model_path_value is not None:
            self._request.context.set_parameter_value(
                self.IFC_MODEL_PATH_KEY,
                ifc_model_path_value,
            )

        return True

    def run(self) -> CommandResponse:
        container_path: Path = Path(
            str(self._request.context.get_parameter_value(self.CONTAINER_PATH_KEY))
        ).expanduser().resolve()
        root_path: str = self._request.context.root_path
        if hotfix_container_manifest_synced(
            container_path=str(container_path),
            root_path=str(root_path),
        ) != 0:
            raise CliCommandArgumentException(
                f"The RO-Crate of the project at {container_path} could not "
                f"be brought up to date, so what the project holds is not "
                f"stated."
            )

        handler: GeometricProductDeleteStateTransitionHandler = (
            GeometricProductDeleteStateTransitionHandler(
                context=self._request.context,
                logger=self._logger,
            )
        )
        return handler.execute()

    @staticmethod
    def _values(
        scoped_args: List[str],
    ) -> Optional[Tuple[str, Optional[str]]]:
        remaining: List[str] = list(scoped_args)
        global_id: Optional[str] = IfcDeleteCommand._extract(
            remaining, IfcDeleteCommand.FLAG
        )
        if global_id is None:
            return None

        ifc_model_path: Optional[str] = IfcDeleteCommand._extract(
            remaining, IfcDeleteCommand.IFC_MODEL_PATH_FLAG
        )
        if remaining:
            return None

        return global_id, ifc_model_path

    @staticmethod
    def _extract(remaining: List[str], flag: str) -> Optional[str]:
        if flag not in remaining:
            return None

        index: int = remaining.index(flag)
        if index + 1 >= len(remaining):
            return None

        value: str = remaining[index + 1]
        if not value.strip() or value in IfcDeleteCommand.FLAGS:
            return None

        del remaining[index:index + 2]
        return value.strip()
