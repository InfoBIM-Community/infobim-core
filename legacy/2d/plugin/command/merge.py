from pathlib import Path
import re
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

import ezdxf
from ezdxf import xref
from ezdxf.document import Drawing
from ezdxf.entities import DXFEntity, DXFGraphic, Layer
from ezdxf.xref import ConflictPolicy
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class DxfMergeCommand(CliCommandPort):
    """Merge multiple DXF modelspaces, flattening each source into one layer.

    ``--flatten file`` means that each input file becomes one layer in the
    resulting DXF. Source coordinates are kept unchanged, so files that share
    the same coordinate system are overlaid directly. Source files are never
    modified.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="two_d_merge",
        logical_component="2d",
        description="Merge DXF files, using one output layer per source file.",
        arguments=[
            {
                "accepts": ["--merge"],
                "valued": True,
                "parameter": "merge_paths",
                "description": "Comma-separated DXF files to merge.",
                "usage": (
                    "infobim 2d --merge <file1.dxf,file2.dxf,...> --flatten file"
                ),
            },
            {
                "accepts": ["--flatten"],
                "valued": True,
                "parameter": "flatten_mode",
                "description": (
                    "Flattening granularity. 'file' creates one layer per source file."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "2d"
    MERGE_FLAG: ClassVar[str] = "--merge"
    FLATTEN_FLAG: ClassVar[str] = "--flatten"
    FILE_MODE: ClassVar[str] = "file"
    MERGE_PATHS_KEY: ClassVar[str] = "merge_paths"
    FLATTEN_MODE_KEY: ClassVar[str] = "flatten_mode"
    OUTPUT_NAME: ClassVar[str] = "merged.dxf"
    INVALID_LAYER_CHARACTERS: ClassVar[re.Pattern[str]] = re.compile(
        r'[<>/\\\":;?*|=\x00-\x1f]'
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != DxfMergeCommand.COMPONENT:
            return False
        return DxfMergeCommand._values(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        values: Optional[Tuple[List[str], str]] = self._values(
            self._request.command_args
        )
        if values is None:
            return False

        raw_paths, flatten_mode = values
        if flatten_mode.casefold() != self.FILE_MODE:
            raise CliCommandArgumentException(
                "The only supported --flatten mode is 'file'."
            )

        source_paths: List[Path] = []
        for raw_path in raw_paths:
            source_path: Path = Path(raw_path).expanduser().resolve()
            if not source_path.is_file():
                raise CliCommandArgumentException(
                    f"DXF file not found: {source_path}"
                )
            if source_path.suffix.lower() != ".dxf":
                raise CliCommandArgumentException(f"Not a DXF file: {source_path}")
            source_paths.append(source_path)

        if len(source_paths) < 2:
            raise CliCommandArgumentException(
                "--merge requires at least two DXF files."
            )

        self._request.context.set_parameter_value(
            self.MERGE_PATHS_KEY,
            [str(path) for path in source_paths],
        )
        self._request.context.set_parameter_value(
            self.FLATTEN_MODE_KEY,
            self.FILE_MODE,
        )
        return True

    def run(self) -> CommandResponse:
        merge_paths_value: Any = self._request.context.get_parameter_value(
            self.MERGE_PATHS_KEY
        )
        if not isinstance(merge_paths_value, list) or not merge_paths_value:
            raise CliCommandArgumentException(
                "Required parameter is missing: merge_paths"
            )

        source_paths: List[Path] = [
            Path(str(value)).expanduser().resolve()
            for value in merge_paths_value
        ]
        output_path: Path = self._next_output_path(Path.cwd() / self.OUTPUT_NAME)

        target: Drawing = ezdxf.new("R2018", setup=True)
        used_layer_names: Set[str] = set()
        sources: List[Dict[str, Any]] = []

        for source_path in source_paths:
            try:
                source_document: Drawing = ezdxf.readfile(source_path)
            except (IOError, ezdxf.DXFError) as error:
                raise CliCommandArgumentException(
                    f"Could not read DXF file: {source_path}: {error}"
                ) from error

            target_layer: str = self._unique_layer_name(
                source_path.stem,
                used_layer_names,
            )
            source_layers: List[str] = [
                layer.dxf.name for layer in source_document.layers
            ]
            reassigned: int = self._flatten_document_to_layer(
                source_document,
                target_layer,
            )
            source_modelspace_entities: int = len(source_document.modelspace())

            # NUM_PREFIX keeps unique file-layer names unchanged while safely
            # renaming conflicting dependent resources such as blocks or
            # linetypes from different input files.
            xref.load_modelspace(
                source_document,
                target,
                conflict_policy=ConflictPolicy.NUM_PREFIX,
            )

            sources.append(
                {
                    "source": str(source_path),
                    "layer": target_layer,
                    "source_layers": source_layers,
                    "entities_reassigned": reassigned,
                    "modelspace_entities": source_modelspace_entities,
                }
            )

        target.saveas(output_path)

        saved_document: Drawing = ezdxf.readfile(output_path)
        output_layers: List[str] = [
            layer.dxf.name for layer in saved_document.layers
        ]

        return CommandResponse(
            title="InfoBIM 2D: Merge DXF",
            description=(
                "Merged the DXF files in their original coordinates, "
                "using one layer per source file."
            ),
            content={
                "output": str(output_path),
                "flatten": self.FILE_MODE,
                "sources": sources,
                "output_layers": output_layers,
                "modelspace_entities": len(saved_document.modelspace()),
            },
        )

    @classmethod
    def _values(cls, scoped_args: List[str]) -> Optional[Tuple[List[str], str]]:
        """Parse --merge values and the required literal --flatten file mode.

        Merge paths may be supplied without spaces after commas or as shell
        tokens separated by spaces after commas, for example both of these:

            --merge a.dxf,b.dxf --flatten file
            --merge a.dxf, b.dxf --flatten file
        """
        if cls.MERGE_FLAG not in scoped_args or cls.FLATTEN_FLAG not in scoped_args:
            return None
        if scoped_args.count(cls.MERGE_FLAG) != 1:
            return None
        if scoped_args.count(cls.FLATTEN_FLAG) != 1:
            return None

        merge_index: int = scoped_args.index(cls.MERGE_FLAG)
        flatten_index: int = scoped_args.index(cls.FLATTEN_FLAG)
        if merge_index >= flatten_index:
            return None
        if flatten_index + 1 >= len(scoped_args):
            return None
        if flatten_index + 2 != len(scoped_args):
            return None

        merge_tokens: List[str] = scoped_args[merge_index + 1:flatten_index]
        if not merge_tokens:
            return None

        raw_merge_value: str = " ".join(merge_tokens)
        merge_paths: List[str] = [
            path.strip()
            for path in raw_merge_value.split(",")
            if path.strip()
        ]
        if not merge_paths:
            return None

        flatten_mode: str = str(scoped_args[flatten_index + 1]).strip()
        if not flatten_mode:
            return None

        return merge_paths, flatten_mode

    @classmethod
    def _unique_layer_name(cls, stem: str, used_names: Set[str]) -> str:
        """Return a valid, case-insensitively unique DXF layer name."""
        base: str = cls.INVALID_LAYER_CHARACTERS.sub("_", stem.strip()).strip()
        if not base:
            base = "file"
        base = base[:255]

        candidate: str = base
        index: int = 2
        while candidate.casefold() in used_names:
            suffix: str = f"_{index}"
            candidate = f"{base[:255 - len(suffix)]}{suffix}"
            index += 1

        used_names.add(candidate.casefold())
        return candidate

    @classmethod
    def _flatten_document_to_layer(
        cls,
        document: Drawing,
        target_layer: str,
    ) -> int:
        """Move every layer-aware entity in a source document to one layer.

        entitydb covers modelspace, paperspace and block definitions. Only the
        source modelspace is imported into the merged target, but flattening
        block definitions as well ensures INSERT content belongs to the same
        file layer when its dependencies are transferred.
        """
        if not document.layers.has_entry(target_layer):
            document.layers.new(target_layer)

        reassigned: int = 0
        for entity in document.entitydb.values():
            if not getattr(entity, "is_alive", True):
                continue
            if not isinstance(entity, DXFEntity):
                continue
            if not entity.dxf.is_supported("layer"):
                continue

            original_layer_name: str = str(entity.dxf.get("layer", "0"))
            original_layer: Optional[Layer] = cls._layer(
                document,
                original_layer_name,
            )
            if original_layer is not None and isinstance(entity, DXFGraphic):
                cls._materialize_bylayer(entity, original_layer)

            if original_layer_name.casefold() != target_layer.casefold():
                entity.dxf.layer = target_layer
                reassigned += 1

        return reassigned

    @staticmethod
    def _layer(document: Drawing, name: str) -> Optional[Layer]:
        try:
            return document.layers.get(name)
        except Exception:
            return None

    @staticmethod
    def _materialize_bylayer(entity: DXFGraphic, layer: Layer) -> None:
        """Copy resolvable BYLAYER display properties onto one entity."""
        dxf = entity.dxf

        if dxf.is_supported("color") and dxf.get("color", 256) == 256:
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

        if dxf.is_supported("transparency") and not dxf.hasattr("transparency"):
            transparency: float = float(layer.transparency)
            if transparency > 0.0:
                entity.transparency = transparency

    @staticmethod
    def _next_output_path(preferred: Path) -> Path:
        """Avoid overwriting an earlier merge when no --output flag exists."""
        if not preferred.exists():
            return preferred

        index: int = 2
        while True:
            candidate: Path = preferred.with_name(
                f"{preferred.stem}_{index}{preferred.suffix}"
            )
            if not candidate.exists():
                return candidate
            index += 1
