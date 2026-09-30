import json
from typing import Any, ClassVar, Dict, List, Optional
from pathlib import Path

from rdflib import Graph

from ontobdc.shared.adapter.etl import EtlEventPayloadKeys
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.dwg_dxf_linkset import DwgDxfLinksetWriter
from infobim.drawing.adapter.transformation_payload import TransformationPayloadPath


class DwgDxfLinksetCapability(TransformationCapability):
    """Return an ISO 21597 version linkset for a DWG/DXF pair."""

    DWG_PATH_KEY: ClassVar[str] = "dwg_path"
    DXF_PATH_KEY: ClassVar[str] = "dxf_path"
    LINKSET_KEY: ClassVar[str] = "linkset"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.drawing.plugin.capability.transformation.dwg_dxf_linkset",
        version="1.0.0",
        name="DWG DXF Linkset",
        description="Build an ISO 21597 Identity linkset for a DWG/DXF pair.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dwg", "dxf", "linkset", "iso21597", "transformation"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                "dwg_path": {"type": "string", "required": True},
                "dxf_path": {"type": "string", "required": True},
            },
        },
        output_schema={
            "properties": {
                EtlEventPayloadKeys.SOURCE_PATH: {"type": "string"},
                "dxf_path": {"type": "string"},
                "linkset": {"type": "array"},
            },
        },
        log_message={
            "info": {
                "en": "The DWG/DXF linkset was built.",
                "pt-br": "O linkset DWG/DXF foi construído.",
            },
            "debug_entry": {
                "en": "Building the ISO 21597 linkset for the provided files.",
                "pt-br": "Construindo o linkset ISO 21597 dos arquivos fornecidos.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Linkset DWG/DXF"
        return "DWG DXF linkset"

    def description(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Constrói o linkset ISO 21597 entre o DWG e sua versão DXF."
        return "Build the ISO 21597 linkset between a DWG and its DXF version."

    def is_satisfied(self, context: CliContextPort) -> bool:
        source_value: Optional[str] = RequiredParameter.optional(
            context, self.DWG_PATH_KEY
        )
        target_value: Optional[str] = RequiredParameter.optional(
            context, self.DXF_PATH_KEY
        )
        if source_value is None or target_value is None:
            return False

        source_path: Path = Path(source_value).expanduser().resolve()
        target_path: Path = Path(target_value).expanduser().resolve()
        return (
            source_path.is_file()
            and source_path.suffix.lower() == ".dwg"
            and target_path.is_file()
            and target_path.suffix.lower() == ".dxf"
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        source_path: Path = Path(
            RequiredParameter.of(context, self.DWG_PATH_KEY)
        ).expanduser().resolve()
        target_path: Path = Path(
            RequiredParameter.of(context, self.DXF_PATH_KEY)
        ).expanduser().resolve()
        if not source_path.is_file() or source_path.suffix.lower() != ".dwg":
            raise ValueError(f"Invalid DWG path: {source_path}")
        if not target_path.is_file() or target_path.suffix.lower() != ".dxf":
            raise ValueError(f"Invalid DXF path: {target_path}")

        source_hash: str = TransformationPayloadPath.identifier_for(source_path)
        graph: Graph = DwgDxfLinksetWriter.graph_for(
            source_hash, source_path, target_path
        )
        payload: Any = json.loads(graph.serialize(format="json-ld"))
        if not isinstance(payload, list):
            raise ValueError("The linkset JSON-LD must be an array of nodes.")
        linkset: List[Dict[str, Any]] = []
        node: Any
        for node in payload:
            if not isinstance(node, dict):
                raise ValueError("Each linkset JSON-LD node must be an object.")
            linkset.append(node)

        return {
            EtlEventPayloadKeys.SOURCE_PATH: str(source_path),
            self.DXF_PATH_KEY: str(target_path),
            self.LINKSET_KEY: linkset,
        }
