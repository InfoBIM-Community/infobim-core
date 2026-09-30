from typing import Any, ClassVar, List, Optional, Tuple
from pathlib import Path

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException

from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)

from infobim.project.adapter.contract import ProjectGuard
from infobim.ifc.plugin.machine.geometric_product_create.machine import (
    GeometricProductCreateStateTransitionHandler,
)


class IfcCreateCommand(CliCommandPort, LoggerAwarePort):
    """
    Creates one IFC object in the project's target model, with no geometry.

    What this command owns is the product: the class it is, the title it
    carries, and writing it into the model the parameter strategies
    resolved. Geometry is produced by its own commands and attached by the
    machine that orchestrates them, so an object created here may exist
    for a while without any — which is the point of keeping the two apart.

    Runs the geometric product creation state machine from
    ``GeometricProductCreateStateTransitionHandler``.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_create",
        logical_component="ifc",
        description="Create an IFC object in the project's IFC model.",
        arguments=[
            {
                "accepts": ["--create"],
                "valued": True,
                "parameter": "title",
                "description": "Title of the IFC object to create.",
                "usage": (
                    "infobim ifc --create <title> "
                    "[--ifc-class <IfcClass>] [--ifc-model-path <path>]"
                ),
            },
            {
                "accepts": ["--ifc-class"],
                "valued": True,
                "parameter": "ifc_class",
                "description": (
                    "Concrete IFC class of the object; defaults to "
                    "IfcBuildingElementProxy."
                ),
            },
            {
                "accepts": ["--ifc-model-path"],
                "valued": True,
                "parameter": "ifc_model_path",
                "description": (
                    "IFC model to create the object in; resolved from the "
                    "project when it is not given."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    FLAG: ClassVar[str] = "--create"
    IFC_CLASS_FLAG: ClassVar[str] = "--ifc-class"
    IFC_MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    FLAGS: ClassVar[List[str]] = [
        "--create",
        "--ifc-class",
        "--ifc-model-path",
    ]
    TITLE_KEY: ClassVar[str] = "title"
    IFC_CLASS_KEY: ClassVar[str] = "ifc_class"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the IFC creation command at the CLI routing stage.
        """
        if not args or args[0] != IfcCreateCommand.COMPONENT:
            return False

        return IfcCreateCommand._values(args[1:]) is not None

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
        """
        Check that the arguments name a creation, inside a Project.

        The class and the model are not resolved here. Each is the answer
        to a question of its own — which class the schema declares, which
        model of this project is the target — and each has a parameter
        strategy that already ran by the time this is called. What is left
        for the command is the shape of its own invocation and the Project
        it is invoked in.
        """
        values: Optional[Tuple[str, Optional[str], Optional[str]]] = self._values(
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

        title_value: str = values[0]
        ifc_class_value: Optional[str] = values[1]
        ifc_model_path_value: Optional[str] = values[2]

        self._request.context.set_parameter_value(self.TITLE_KEY, title_value)

        if ifc_class_value is not None:
            self._request.context.set_parameter_value(
                self.IFC_CLASS_KEY,
                ifc_class_value,
            )

        if ifc_model_path_value is not None:
            self._request.context.set_parameter_value(
                self.IFC_MODEL_PATH_KEY,
                ifc_model_path_value,
            )

        return True

    def run(self) -> CommandResponse:
        """
        Drive the IFC geometric product through its creation state machine.

        The container states what it holds, and the machine and everything
        downstream read that statement rather than the disk, so the
        statement is brought up to date first: the model this run resolved
        or created is declared by the manifest hotfix before any state is
        reached, not by this command writing into the crate itself.
        """
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

        handler: GeometricProductCreateStateTransitionHandler = (
            GeometricProductCreateStateTransitionHandler(
                context=self._request.context,
                logger=self._logger,
            )
        )

        return handler.execute()

    @staticmethod
    def _values(
        scoped_args: List[str],
    ) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
        """
        Return the (title, ifc_class, ifc_model_path) these args name.

        Only the title is required; the class falls back to the contract's
        default and the model is resolved from the Project when they are
        not given. Which flag a user writes first is not part of the
        command's meaning, so the three are read in any order, and an
        argument left over means the args name something else — this
        command never guesses what.
        """
        remaining: List[str] = list(scoped_args)
        title: Optional[str] = IfcCreateCommand._extract(
            remaining, IfcCreateCommand.FLAG
        )
        if title is None:
            return None

        ifc_class: Optional[str] = IfcCreateCommand._extract(
            remaining, IfcCreateCommand.IFC_CLASS_FLAG
        )
        ifc_model_path: Optional[str] = IfcCreateCommand._extract(
            remaining, IfcCreateCommand.IFC_MODEL_PATH_FLAG
        )
        if remaining:
            return None

        return title, ifc_class, ifc_model_path

    @staticmethod
    def _extract(remaining: List[str], flag: str) -> Optional[str]:
        """
        Remove and return the value the flag carries, or None when it
        carries none.

        A value is what the user wrote for that flag, not whatever token
        happens to sit after it: another flag of this command found there
        means this one was left without a value, which is one of the three
        cases the argument-matching contract rejects.
        """
        if flag not in remaining:
            return None

        index: int = remaining.index(flag)
        if index + 1 >= len(remaining):
            return None

        value: str = remaining[index + 1]
        if not value.strip() or value in IfcCreateCommand.FLAGS:
            return None

        del remaining[index:index + 2]

        return value.strip()
