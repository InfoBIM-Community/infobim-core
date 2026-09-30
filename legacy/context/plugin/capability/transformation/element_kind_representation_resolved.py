from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.context.adapter.taxonomy import (
    PARAMETER_KEY, REPRESENTATION_PARAMETER_KEY, CONTAINER_PATH_KEY, DXF_PATH_KEY,
    REPRESENTATION_STATE, CAPABILITY_PREFIX,
)
from infobim.context.adapter.kind_representation import OntologyKindRepresentationResolver
from infobim.context.adapter.kind_resolution_event import KindResolutionEvent
from infobim.context.domain.port.kind_representation import KindRepresentationResolverPort


class ElementKindRepresentationResolvedCapability(TransformationCapability):
    """Own representation evidence and restore only validated output into run context."""

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=CAPABILITY_PREFIX + REPRESENTATION_STATE.strip("_"),
        version="1.2.0", name="Element Representation Resolved",
        description="Resolve and persist the ontology representation for a document kind.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "kind", "representation", "transformation"],
        input_schema={"properties": {
            PARAMETER_KEY: {"type": "string", "required": True},
            CONTAINER_PATH_KEY: {"type": "string", "required": True},
            DXF_PATH_KEY: {"type": "string", "required": True},
        }},
        output_schema={"properties": {
            REPRESENTATION_PARAMETER_KEY: {"type": "array"},
        }},
    )

    def __init__(self, resolver: Optional[KindRepresentationResolverPort] = None) -> None:
        self._resolver: KindRepresentationResolverPort = (
            OntologyKindRepresentationResolver() if resolver is None else resolver
        )

    def label(self, lang: str = "en") -> str:
        return "Element representation resolved"

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        event: Optional[Dict[str, Any]] = KindResolutionEvent.read(
            context, REPRESENTATION_STATE, self.METADATA.version, REPRESENTATION_PARAMETER_KEY
        )
        if event is None:
            context.delete_parameter(REPRESENTATION_PARAMETER_KEY)
            return False
        representation_json_ld: Any = event["output"][REPRESENTATION_PARAMETER_KEY]
        if not isinstance(representation_json_ld, list) or not representation_json_ld:
            raise ValueError(
                f"ETL output {REPRESENTATION_PARAMETER_KEY} must be a non-empty JSON-LD node array."
            )
        context.set_parameter_value(REPRESENTATION_PARAMETER_KEY, representation_json_ld)
        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        kind: str = KindResolutionEvent.required(context, PARAMETER_KEY)
        representation: str = self._resolver.resolve(kind)
        representation_json_ld: List[Dict[str, Any]] = self._resolver.describe(representation)
        output: Dict[str, Any] = {REPRESENTATION_PARAMETER_KEY: representation_json_ld}
        KindResolutionEvent.write(context, REPRESENTATION_STATE, self.METADATA.version, output)
        context.set_parameter_value(REPRESENTATION_PARAMETER_KEY, representation_json_ld)
        return output
