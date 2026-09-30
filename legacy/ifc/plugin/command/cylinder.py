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


class IfcCylinderCommand(CliCommandPort, LoggerAwarePort):
    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_cylinder",
        logical_component="ifc",
        description="Create an IFC object with a cylindrical solid geometry.",
        arguments=[
            {
                "accepts": ["--create"],
                "valued": True,
                "parameter": "title",
                "description": "Title of the IFC object to create.",
                "usage": (
                    "infobim ifc --create <title> "
                    "--radius <r> --height <h> "
                    "--direction-x <x> --direction-y <y> --direction-z <z> "
                    "[--ifc-class <IfcClass>] [--ifc-model-path <path>] "
                    "[--x <x>] [--y <y>] [--z <z>]"
                ),
            },
            {
                "accepts": ["--radius"],
                "valued": True,
                "parameter": "radius",
                "description": "Radius of the cylinder's circular profile.",
            },
            {
                "accepts": ["--height"],
                "valued": True,
                "parameter": "height",
                "description": "Height of the cylinder along its own axis.",
            },
            {
                "accepts": ["--direction-x"],
                "valued": True,
                "parameter": "direction_x",
                "description": "X component of the cylinder axis direction.",
            },
            {
                "accepts": ["--direction-y"],
                "valued": True,
                "parameter": "direction_y",
                "description": "Y component of the cylinder axis direction.",
            },
            {
                "accepts": ["--direction-z"],
                "valued": True,
                "parameter": "direction_z",
                "description": "Z component of the cylinder axis direction.",
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
                "description": "Placement X coordinate; origin when not given.",
            },
            {
                "accepts": ["--y"],
                "valued": True,
                "parameter": "y",
                "description": "Placement Y coordinate; origin when not given.",
            },
            {
                "accepts": ["--z"],
                "valued": True,
                "parameter": "z",
                "description": "Placement Z coordinate; origin when not given.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    FLAG: ClassVar[str] = "--create"
    RADIUS_FLAG: ClassVar[str] = "--radius"
    HEIGHT_FLAG: ClassVar[str] = "--height"
    DIRECTION_X_FLAG: ClassVar[str] = "--direction-x"
    DIRECTION_Y_FLAG: ClassVar[str] = "--direction-y"
    DIRECTION_Z_FLAG: ClassVar[str] = "--direction-z"
    IFC_CLASS_FLAG: ClassVar[str] = "--ifc-class"
    IFC_MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    X_FLAG: ClassVar[str] = "--x"
    Y_FLAG: ClassVar[str] = "--y"
    Z_FLAG: ClassVar[str] = "--z"
    FLAGS: ClassVar[List[str]] = [
        FLAG,
        RADIUS_FLAG,
        HEIGHT_FLAG,
        DIRECTION_X_FLAG,
        DIRECTION_Y_FLAG,
        DIRECTION_Z_FLAG,
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
        if not args or args[0] != IfcCylinderCommand.COMPONENT:
            return False
        return IfcCylinderCommand._values(args[1:]) is not None

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
            height_value,
            direction_x_value,
            direction_y_value,
            direction_z_value,
            ifc_class_value,
            ifc_model_path_value,
            x_value,
            y_value,
            z_value,
        ) = values

        radius: float = self._require_positive_float("radius", radius_value)
        height: float = self._require_positive_float("height", height_value)
        direction_x: float = self._require_finite_float(
            "direction_x", direction_x_value
        )
        direction_y: float = self._require_finite_float(
            "direction_y", direction_y_value
        )
        direction_z: float = self._require_finite_float(
            "direction_z", direction_z_value
        )
        if direction_x == 0.0 and direction_y == 0.0 and direction_z == 0.0:
            raise GeometryDefinitionInvalidError(
                "The cylinder direction vector cannot be the zero vector."
            )

        x_numeric: float = (
            self._require_finite_float("x", x_value)
            if x_value is not None
            else 0.0
        )
        y_numeric: float = (
            self._require_finite_float("y", y_value)
            if y_value is not None
            else 0.0
        )
        z_numeric: float = (
            self._require_finite_float("z", z_value)
            if z_value is not None
            else 0.0
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
            kind=GeometryDefinition.CYLINDER_KIND,
            parameters=(
                ("radius", radius),
                ("height", height),
                ("direction_x", direction_x),
                ("direction_y", direction_y),
                ("direction_z", direction_z),
            ),
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
            str,
            str,
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
        title: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.FLAG
        )
        if title is None:
            return None

        radius: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.RADIUS_FLAG
        )
        height: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.HEIGHT_FLAG
        )
        direction_x: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.DIRECTION_X_FLAG
        )
        direction_y: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.DIRECTION_Y_FLAG
        )
        direction_z: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.DIRECTION_Z_FLAG
        )
        if any(
            value is None
            for value in (
                radius,
                height,
                direction_x,
                direction_y,
                direction_z,
            )
        ):
            return None

        ifc_class: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.IFC_CLASS_FLAG
        )
        ifc_model_path: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.IFC_MODEL_PATH_FLAG
        )
        x_value: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.X_FLAG
        )
        y_value: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.Y_FLAG
        )
        z_value: Optional[str] = IfcCylinderCommand._extract(
            remaining, IfcCylinderCommand.Z_FLAG
        )
        if remaining:
            return None

        return (
            title,
            radius,
            height,
            direction_x,
            direction_y,
            direction_z,
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
        if not value.strip() or value in IfcCylinderCommand.FLAGS:
            return None

        del remaining[index:index + 2]
        return value.strip()

    @staticmethod
    def _require_finite_float(key: str, raw: Any) -> float:
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
        return numeric

    @classmethod
    def _require_positive_float(cls, key: str, raw: Any) -> float:
        numeric: float = cls._require_finite_float(key, raw)
        if numeric <= 0.0:
            raise GeometryDefinitionInvalidError(
                f"The {key} value must be positive; got {numeric}."
            )
        return numeric
