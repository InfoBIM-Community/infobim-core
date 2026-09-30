from typing import Any, ClassVar, Dict, Optional
from importlib import import_module

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.context.adapter.taxonomy import CAPABILITY_PREFIX, MACHINE_PACKAGE, PIPE_RADIUS_KEY
from infobim.context.adapter.kind_resolution_event import KindResolutionEvent

DxfVectorProcessState: Any = import_module(MACHINE_PACKAGE + ".state").DxfVectorProcessState


class PipeRadiusDefinedCapability(TransformationCapability):
    """Bind the pipe radius this run creates its IfcPipeSegments with.

    A fixed 40 mm default until a real radius source (an ontology
    parameter, a CLI flag) is wired in -- deliberately explicit, not a
    silent fallback: this state exists precisely to make the default
    visible and persisted, not to hide it inside the creation capability.
    """

    STATE: ClassVar[str] = DxfVectorProcessState.PIPE_RADIUS_DEFINED.value
    OUTPUT_KEY: ClassVar[str] = PIPE_RADIUS_KEY
    DEFAULT_RADIUS_METERS: ClassVar[float] = 0.04  # 40 mm

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=CAPABILITY_PREFIX + STATE.strip("_"),
        version="1.0.0", name="Pipe Radius Defined",
        description="Bind the default pipe radius (40 mm) for this run.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "vector", "pipe"],
        output_schema={"properties": {OUTPUT_KEY: {"type": "number"}}},
    )

    def label(self, lang: str = "en") -> str:
        return "Pipe radius defined"

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        event: Optional[Dict[str, Any]] = KindResolutionEvent.read(
            context, self.STATE, self.METADATA.version, self.OUTPUT_KEY
        )
        if event is None:
            return False
        radius: Any = event["output"][self.OUTPUT_KEY]
        if not isinstance(radius, (int, float)) or radius <= 0:
            raise ValueError(f"ETL output {self.OUTPUT_KEY} must be a positive number.")
        context.set_parameter_value(self.OUTPUT_KEY, float(radius))
        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        context.set_parameter_value(self.OUTPUT_KEY, self.DEFAULT_RADIUS_METERS)
        output: Dict[str, Any] = {self.OUTPUT_KEY: self.DEFAULT_RADIUS_METERS}
        KindResolutionEvent.write(context, self.STATE, self.METADATA.version, output)
        return output
