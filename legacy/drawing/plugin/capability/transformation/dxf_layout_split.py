from typing import Any, ClassVar, Dict
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.dxf_layout_split import DxfLayoutSplitter
from infobim.drawing.adapter.transformation_payload import TransformationPayloadPath


class DxfLayoutSplitCapability(TransactionCapability):
    """
    Splits a DXF into one document per layout: Model, and each prancha.

    The split itself, including the block-reference expansion and the
    destination path, lives in DxfLayoutSplitter; this capability only
    adapts that transformation to the capability contract and supplies the
    identifier the split output is filed under -- the source DWG's own
    content hash, not a fresh hash of the intermediate DXF.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    DWG_PATH_KEY: ClassVar[str] = "dwg_path"
    DXF_PATH_KEY: ClassVar[str] = "dxf_path"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.drawing.plugin.capability.transformation.dxf_layout_split",
        version="1.0.0",
        name="DXF Layout Split",
        description=(
            "Split a DXF into one document per layout, filed under its "
            "source DWG's content hash."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "layout", "transformation"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                },
                "dwg_path": {
                    "type": "string",
                    "required": True,
                },
                "dxf_path": {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "layouts": {"type": "object"},
            },
            "required": ["layouts"],
        },
    )

    def label(self, lang: str = "en") -> str:
        return "DXF Layout Split"

    def description(self, lang: str = "en") -> str:
        return "Splits a DXF into one document per layout."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Split the DXF named by the context into one document per layout.
        """
        container_value: Any = context.get_parameter_value(
            self.CONTAINER_PATH_KEY
        )
        if not isinstance(container_value, str) or not container_value.strip():
            raise ValueError(
                "The container path is missing from the command context."
            )

        dwg_value: Any = context.get_parameter_value(self.DWG_PATH_KEY)
        if not isinstance(dwg_value, str) or not dwg_value.strip():
            raise ValueError(
                "The DWG source path is missing from the command context."
            )

        dxf_value: Any = context.get_parameter_value(self.DXF_PATH_KEY)
        if not isinstance(dxf_value, str) or not dxf_value.strip():
            raise ValueError(
                "The DXF path is missing from the command context."
            )

        container_path: Path = Path(container_value).expanduser().resolve()
        dwg_path: Path = Path(dwg_value).expanduser().resolve()
        dxf_path: Path = Path(dxf_value).expanduser().resolve()

        identifier: str = TransformationPayloadPath.identifier_for(dwg_path)
        layouts: Dict[str, Path] = DxfLayoutSplitter.split(
            container_path, dxf_path, identifier
        )

        return {"layouts": {name: str(path) for name, path in layouts.items()}}
