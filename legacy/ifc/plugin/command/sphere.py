from math import isfinite
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

from infobim.ifc.domain.exception.creation import GeometryDefinitionInvalidError
from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.plugin.machine.geometric_product_create.machine import (
    GeometricProductCreateStateTransitionHandler,
)
from infobim.project.adapter.contract import ProjectGuard


class IfcSphereCommand(CliCommandPort, LoggerAwarePort):
    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_sphere",
        logical_component="ifc",
        description="Create an IFC object with a spherical solid geometry.",
        arguments=[
            {
                "accepts": ["--create"],
                "valued": True,
                "parameter": "title",
                "description": "Title of the IFC object to create.",
                "usage": (
                    "infobim ifc --create <title> --radius <r> "
                    "[--ifc-class <IfcClass>] [--ifc-model-path <path>] "
                    "[--x <x>] [--y <y>] [--z <z>]"
                ),
            },
            {
                "accepts": ["--radius"],
                "valued": True,
                "parameter": "radius",
                "description": "Radius of the sphere.",
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
            {
                "accepts": ["--x"],
                "valued": True,
                "parameter": "x",
                "description": "Sphere-center X coordinate; origin when not given.",
            },
            {
                "accepts": ["--y"],
                "valued": True,
                "parameter": "y",
                "description": "Sphere-center Y coordinate; origin when not given.",
            },
            {
                "accepts": ["--z"],
                "valued": True,
                "parameter": "z",
                "description": "Sphere-center Z coordinate; origin when not given.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    FLAG: ClassVar[str] = "--create"
    RADIUS_FLAG: ClassVar[str] = "--radius"
    IFC_CLASS_FLAG: ClassVar[str] = "--ifc-class"
    IFC_MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    X_FLAG: ClassVar[str] = "--x"
    Y_FLAG: ClassVar[str] = "--y"
    Z_FLAG: ClassVar[str] = "--z"
    FLAGS: ClassVar[List[str]] = [
        FLAG,
        RADIUS_FLAG,
        IFC_CLASS_FLAG,
        IFC_MODEL_PATH_FLAG,
        X_FLAG,
        Y_FLAG,
        Z_FLAG,
    ]

    TITLE_KEY: ClassVar[str] = "title"
    IFC_CLASS_KEY: ClassVar[str] = "ifc_class"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    GEOMETRY_KEY: ClassVar[str] = "geometry"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != IfcSphereCommand.COMPONENT:
            return False
        return IfcSphereCommand._values(args[1:]) is not None

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
        values = self._values(self._request.command_args)
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

        (
            title_value,
            radius_value,
            ifc_class_value,
            ifc_model_path_value,
            x_value,
            y_value,
            z_value,
        ) = values

        radius: float = self._require_float("radius", radius_value, positive=True)
        x_numeric: float = (
            self._require_float("x", x_value) if x_value is not None else 0.0
        )
        y_numeric: float = (
            self._require_float("y", y_value) if y_value is not None else 0.0
        )
        z_numeric: float = (
            self._require_float("z", z_value) if z_value is not None else 0.0
        )

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

        self._request.context.set_parameter_value("x", x_numeric)
        self._request.context.set_parameter_value("y", y_numeric)
        self._request.context.set_parameter_value("z", z_numeric)

        geometry = GeometryDefinition(
            kind=GeometryDefinition.SPHERE_KIND,
            parameters=(("radius", radius),),
        )
        self._request.context.set_parameter_value(self.GEOMETRY_KEY, geometry)
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

        handler = GeometricProductCreateStateTransitionHandler(
            context=self._request.context,
            logger=self._logger,
        )
        return handler.execute()

    @staticmethod
    def _values(
        scoped_args: List[str],
    ) -> Optional[
        Tuple[
            str,
            str,
            Optional[str],
            Optional[str],
            Optional[str],
            Optional[str],
            Optional[str],
        ]
    ]:
        remaining: List[str] = list(scoped_args)
        title: Optional[str] = IfcSphereCommand._extract(
            remaining, IfcSphereCommand.FLAG
        )
        if title is None:
            return None

        radius: Optional[str] = IfcSphereCommand._extract(
            remaining, IfcSphereCommand.RADIUS_FLAG
        )
        if radius is None:
            return None

        ifc_class: Optional[str] = IfcSphereCommand._extract(
            remaining, IfcSphereCommand.IFC_CLASS_FLAG
        )
        ifc_model_path: Optional[str] = IfcSphereCommand._extract(
            remaining, IfcSphereCommand.IFC_MODEL_PATH_FLAG
        )
        x_value: Optional[str] = IfcSphereCommand._extract(
            remaining, IfcSphereCommand.X_FLAG
        )
        y_value: Optional[str] = IfcSphereCommand._extract(
            remaining, IfcSphereCommand.Y_FLAG
        )
        z_value: Optional[str] = IfcSphereCommand._extract(
            remaining, IfcSphereCommand.Z_FLAG
        )
        if remaining:
            return None

        return (
            title,
            radius,
            ifc_class,
            ifc_model_path,
            x_value,
            y_value,
            z_value,
        )

    @staticmethod
    def _extract(remaining: List[str], flag: str) -> Optional[str]:
        if flag not in remaining:
            return None

        index: int = remaining.index(flag)
        if index + 1 >= len(remaining):
            return None

        value: str = remaining[index + 1]
        if not value.strip() or value in IfcSphereCommand.FLAGS:
            return None

        del remaining[index:index + 2]
        return value.strip()

    @staticmethod
    def _require_float(key: str, raw: Any, positive: bool = False) -> float:
        if isinstance(raw, bool):
            raise CliCommandArgumentException(
                f"The {key} value {raw!r} is a boolean, not a number."
            )
        if isinstance(raw, (int, float)):
            numeric: float = float(raw)
        elif isinstance(raw, str) and raw.strip():
            try:
                numeric = float(raw.strip())
            except ValueError as error:
                raise CliCommandArgumentException(
                    f"The {key} value {raw!r} does not read as a number."
                ) from error
        else:
            raise CliCommandArgumentException(
                f"The {key} value {raw!r} is not a number."
            )

        if not isfinite(numeric):
            raise GeometryDefinitionInvalidError(
                f"The {key} value must be finite; got {numeric}."
            )
        if positive and numeric <= 0.0:
            raise GeometryDefinitionInvalidError(
                f"The {key} value must be positive; got {numeric}."
            )
        return numeric
