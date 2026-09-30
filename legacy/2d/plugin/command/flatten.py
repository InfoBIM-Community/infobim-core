from pathlib import Path
import re
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union

import ezdxf
from ezdxf.document import Drawing
from ezdxf.entities import DXFEntity, DXFGraphic, Layer
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


ColorSpec = Union[int, Tuple[int, int, int]]


class DxfFlattenCommand(CliCommandPort):
    """Flatten every DXF entity onto layer 0 and write a new DXF file.

    The source file is never modified. Without ``--color``, basic BYLAYER
    display properties are materialized before the layer assignment changes so
    the drawing keeps its original appearance as closely as possible.

    With ``--color``, every graphical entity is normalized to BYLAYER color and
    the requested color is assigned to layer 0. Other resolvable BYLAYER
    properties (linetype, lineweight and transparency) are still materialized.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="two_d_flatten",
        logical_component="2d",
        description="Flatten all DXF entities onto layer 0.",
        arguments=[
            {
                "accepts": ["--flatten"],
                "valued": True,
                "parameter": "dxf_path",
                "description": "Path to the DXF file to flatten.",
                "usage": (
                    "infobim 2d --flatten <path/to/file.dxf> "
                    "[--color <ACI|#RRGGBB>]"
                ),
            },
            {
                "accepts": ["--color"],
                "valued": True,
                "parameter": "color",
                "description": (
                    "Optional output layer color as ACI 1-255 or #RRGGBB."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "2d"
    FLATTEN_FLAG: ClassVar[str] = "--flatten"
    COLOR_FLAG: ClassVar[str] = "--color"
    TARGET_LAYER: ClassVar[str] = "0"
    DXF_PATH_KEY: ClassVar[str] = "dxf_path"
    COLOR_KEY: ClassVar[str] = "color"
    HEX_COLOR: ClassVar[re.Pattern[str]] = re.compile(r"^#?([0-9A-Fa-f]{6})$")

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != DxfFlattenCommand.COMPONENT:
            return False
        return DxfFlattenCommand._values(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        values: Optional[Tuple[str, Optional[str]]] = self._values(
            self._request.command_args
        )
        if values is None:
            return False

        raw_path, raw_color = values
        source_path: Path = Path(raw_path).expanduser().resolve()
        if not source_path.is_file():
            raise CliCommandArgumentException(f"DXF file not found: {source_path}")
        if source_path.suffix.lower() != ".dxf":
            raise CliCommandArgumentException(f"Not a DXF file: {source_path}")

        if raw_color is not None:
            self._parse_color(raw_color)

        self._request.context.set_parameter_value(
            self.DXF_PATH_KEY,
            str(source_path),
        )
        if raw_color is not None:
            self._request.context.set_parameter_value(self.COLOR_KEY, raw_color)
        else:
            self._request.context.delete_parameter(self.COLOR_KEY)
        return True

    def run(self) -> CommandResponse:
        source_value: Any = self._request.context.get_parameter_value(
            self.DXF_PATH_KEY
        )
        if not isinstance(source_value, str) or not source_value.strip():
            raise CliCommandArgumentException("Required parameter is missing: dxf_path")

        raw_color_value: Any = self._request.context.get_parameter_value(self.COLOR_KEY)
        raw_color: Optional[str] = (
            str(raw_color_value).strip()
            if raw_color_value is not None and str(raw_color_value).strip()
            else None
        )
        color: Optional[ColorSpec] = (
            self._parse_color(raw_color) if raw_color is not None else None
        )

        source_path: Path = Path(source_value).expanduser().resolve()
        output_path: Path = source_path.with_name(
            f"{source_path.stem}.flattened{source_path.suffix}"
        )

        try:
            document: Drawing = ezdxf.readfile(source_path)
        except (IOError, ezdxf.DXFError) as error:
            raise CliCommandArgumentException(
                f"Could not read DXF file: {source_path}: {error}"
            ) from error

        target_layer: Layer = document.layers.get(self.TARGET_LAYER)
        if color is not None:
            self._apply_layer_color(target_layer, color)

        source_layers: List[str] = [layer.dxf.name for layer in document.layers]
        reassigned: int = 0
        recolored: int = 0

        # entitydb covers modelspace, paperspace and entities owned by block
        # definitions. This makes the operation document-wide without
        # exploding INSERT entities.
        for entity in document.entitydb.values():
            if not getattr(entity, "is_alive", True):
                continue
            if not isinstance(entity, DXFEntity):
                continue
            if not entity.dxf.is_supported("layer"):
                continue

            original_layer_name: str = str(entity.dxf.get("layer", self.TARGET_LAYER))
            original_layer: Optional[Layer] = self._layer(document, original_layer_name)
            if original_layer is not None and isinstance(entity, DXFGraphic):
                self._materialize_bylayer(
                    entity,
                    original_layer,
                    preserve_color=color is None,
                )

            if original_layer_name.casefold() != self.TARGET_LAYER.casefold():
                entity.dxf.layer = self.TARGET_LAYER
                reassigned += 1

            if color is not None and isinstance(entity, DXFGraphic):
                if self._set_entity_color_bylayer(entity):
                    recolored += 1

        removed_layers: List[str] = []
        retained_layers: List[str] = []
        for layer in list(document.layers):
            layer_name: str = layer.dxf.name
            if layer_name.casefold() == self.TARGET_LAYER.casefold():
                continue
            try:
                document.layers.remove(layer_name)
                removed_layers.append(layer_name)
            except Exception:
                # A valid DXF may still contain a non-entity reference to a
                # layer table entry. Retain that empty definition rather than
                # risk corrupting the output document.
                retained_layers.append(layer_name)

        document.saveas(output_path)

        # Some DXF/system conventions can cause an empty system layer such as
        # Defpoints to be present again after serialization. Report the actual
        # final layer table instead of implying that layer 0 is the only table
        # record in every valid output file.
        saved_document: Drawing = ezdxf.readfile(output_path)
        output_layers: List[str] = [layer.dxf.name for layer in saved_document.layers]

        return CommandResponse(
            title="InfoBIM 2D: Flatten DXF",
            description=(
                "Flattened all DXF entities onto layer 0"
                + (" and applied the requested layer color." if color is not None else ".")
            ),
            content={
                "source": str(source_path),
                "output": str(output_path),
                "target_layer": self.TARGET_LAYER,
                "color": raw_color,
                "source_layers": source_layers,
                "output_layers": output_layers,
                "entities_reassigned": reassigned,
                "entities_recolored_bylayer": recolored,
                "layer_definitions_removed": removed_layers,
                "layer_definitions_retained": retained_layers,
            },
        )

    @classmethod
    def _values(cls, scoped_args: List[str]) -> Optional[Tuple[str, Optional[str]]]:
        """Parse --flatten <path> with an optional --color <value>."""
        remaining: List[str] = list(scoped_args)
        if remaining.count(cls.FLATTEN_FLAG) != 1:
            return None

        flatten_index: int = remaining.index(cls.FLATTEN_FLAG)
        if flatten_index + 1 >= len(remaining):
            return None
        raw_path: str = str(remaining[flatten_index + 1]).strip()
        if not raw_path or raw_path.startswith("--"):
            return None
        del remaining[flatten_index:flatten_index + 2]

        raw_color: Optional[str] = None
        if cls.COLOR_FLAG in remaining:
            if remaining.count(cls.COLOR_FLAG) != 1:
                return None
            color_index: int = remaining.index(cls.COLOR_FLAG)
            if color_index + 1 >= len(remaining):
                return None
            raw_color = str(remaining[color_index + 1]).strip()
            if not raw_color or raw_color.startswith("--"):
                return None
            del remaining[color_index:color_index + 2]

        if remaining:
            return None

        return raw_path, raw_color

    @classmethod
    def _parse_color(cls, raw_color: str) -> ColorSpec:
        value: str = raw_color.strip()
        if value.isdigit():
            aci: int = int(value)
            if 1 <= aci <= 255:
                return aci
            raise CliCommandArgumentException(
                f"Invalid ACI color: {value}. Expected an integer from 1 to 255."
            )

        match: Optional[re.Match[str]] = cls.HEX_COLOR.match(value)
        if match is not None:
            hex_value: str = match.group(1)
            return (
                int(hex_value[0:2], 16),
                int(hex_value[2:4], 16),
                int(hex_value[4:6], 16),
            )

        raise CliCommandArgumentException(
            f"Invalid color: {value}. Use ACI 1-255 or #RRGGBB."
        )

    @staticmethod
    def _apply_layer_color(layer: Layer, color: ColorSpec) -> None:
        if isinstance(color, int):
            layer.color = color
            if layer.dxf.hasattr("true_color"):
                layer.dxf.discard("true_color")
            return

        layer.rgb = color

    @staticmethod
    def _set_entity_color_bylayer(entity: DXFGraphic) -> bool:
        changed: bool = False
        dxf = entity.dxf
        if dxf.is_supported("color"):
            if dxf.get("color", 256) != 256:
                changed = True
            dxf.color = 256
        if dxf.is_supported("true_color") and dxf.hasattr("true_color"):
            dxf.discard("true_color")
            changed = True
        return changed

    @staticmethod
    def _layer(document: Drawing, name: str) -> Optional[Layer]:
        try:
            return document.layers.get(name)
        except Exception:
            return None

    @staticmethod
    def _materialize_bylayer(
        entity: DXFGraphic,
        layer: Layer,
        preserve_color: bool = True,
    ) -> None:
        """Copy resolvable BYLAYER display properties onto one entity."""
        dxf = entity.dxf

        if preserve_color and dxf.is_supported("color") and dxf.get("color", 256) == 256:
            if dxf.is_supported("true_color") and layer.rgb is not None:
                entity.rgb = layer.rgb
            else:
                dxf.color = layer.color

        if dxf.is_supported("linetype"):
            linetype: str = str(dxf.get("linetype", "BYLAYER"))
            if linetype.upper() == "BYLAYER":
                dxf.linetype = str(layer.dxf.get("linetype", "CONTINUOUS"))

        if dxf.is_supported("lineweight") and dxf.get("lineweight", -1) == -1:
            dxf.lineweight = int(layer.dxf.get("lineweight", -3))

        # Absence of an entity transparency value means BYLAYER in normal DXF
        # output. Do not overwrite an explicit transparency or BYBLOCK value.
        if dxf.is_supported("transparency") and not dxf.hasattr("transparency"):
            transparency: float = float(layer.transparency)
            if transparency > 0.0:
                entity.transparency = transparency
