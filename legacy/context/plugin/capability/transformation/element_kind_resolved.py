from typing import Any, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.context.adapter.taxonomy import (
    PARAMETER_KEY, CONTAINER_PATH_KEY, DXF_PATH_KEY, KIND_STATE, CAPABILITY_PREFIX,
)
from infobim.context.adapter.kind_resolution_event import KindResolutionEvent


class ElementKindResolvedCapability(TransformationCapability):
    """Persist the kind resolved by the parameter strategy for this document."""

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=CAPABILITY_PREFIX + KIND_STATE.strip("_"),
        version="1.0.0", name="Element Kind Resolved",
        description="Persist the resolved element kind for the current document.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "kind", "transformation"],
        input_schema={"properties": {
            PARAMETER_KEY: {"type": "string", "required": True},
            CONTAINER_PATH_KEY: {"type": "string", "required": True},
            DXF_PATH_KEY: {"type": "string", "required": True},
        }},
        output_schema={"properties": {PARAMETER_KEY: {"type": "string"}}},
    )

    def label(self, lang: str = "en") -> str:
        return "Element kind resolved"

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        event: Optional[Dict[str, Any]] = KindResolutionEvent.read(
            context, KIND_STATE, self.METADATA.version, PARAMETER_KEY
        )
        return event is not None and event["output"][PARAMETER_KEY] == (
            KindResolutionEvent.required(context, PARAMETER_KEY)
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        kind: str = KindResolutionEvent.required(context, PARAMETER_KEY)
        output: Dict[str, str] = {PARAMETER_KEY: kind}
        KindResolutionEvent.write(context, KIND_STATE, self.METADATA.version, output)
        return {PARAMETER_KEY: kind}
