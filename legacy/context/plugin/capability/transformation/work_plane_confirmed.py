from typing import Any, ClassVar, Dict, Optional, Tuple
from importlib import import_module

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.facade.adapter.logger import ActiveLogRepositoryBroker
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.context.adapter.taxonomy import CAPABILITY_PREFIX, MACHINE_PACKAGE, WORK_PLANE_Z_KEY
from infobim.context.adapter.kind_resolution_event import KindResolutionEvent

DxfVectorProcessState: Any = import_module(MACHINE_PACKAGE + ".state").DxfVectorProcessState


class WorkPlaneConfirmedCapability(TransformationCapability):
    """Confirm the constant-axis work plane supplied for this run.

    Only --z is implemented: a real number confirms the plane at that
    value; a --z that is missing or does not parse as one logs an INFO
    notice and falls back to the default 40 mm plane instead of failing
    the run. --x and --y are accepted by the command but raise explicitly
    here, since building the work plane from a constant X or Y is not
    implemented yet.

    Axis presence is read from ``context.raw_args`` (this invocation's own
    argv), not from a persisted or previously-set context parameter --
    otherwise a --z left over from an earlier, separate invocation would
    keep silently overriding an --x or --y given this run.
    """

    STATE: ClassVar[str] = DxfVectorProcessState.WORK_PLANE_CONFIRMED.value
    OUTPUT_KEY: ClassVar[str] = WORK_PLANE_Z_KEY
    Z_FLAG: ClassVar[str] = "--z"
    UNIMPLEMENTED_FLAGS: ClassVar[Tuple[str, ...]] = ("--x", "--y")
    DEFAULT_Z_METERS: ClassVar[float] = 0.04  # 40 mm

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=CAPABILITY_PREFIX + STATE.strip("_"),
        version="1.0.0", name="Work Plane Confirmed",
        description="Confirm the constant Z work plane supplied for this run.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "vector", "work-plane"],
        input_schema={"properties": {
            OUTPUT_KEY: {"type": "string", "required": False},
        }},
        output_schema={"properties": {OUTPUT_KEY: {"type": "number"}}},
    )

    def label(self, lang: str = "en") -> str:
        return "Work plane confirmed"

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        self._reject_unimplemented_axes(context)
        required_z: float = self._required_z(context)
        event: Optional[Dict[str, Any]] = KindResolutionEvent.read(
            context, self.STATE, self.METADATA.version, self.OUTPUT_KEY
        )
        return event is not None and event["output"][self.OUTPUT_KEY] == required_z

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        self._reject_unimplemented_axes(context)
        z: float = self._required_z(context)
        context.set_parameter_value(self.OUTPUT_KEY, z)
        output: Dict[str, Any] = {self.OUTPUT_KEY: z}
        KindResolutionEvent.write(context, self.STATE, self.METADATA.version, output)
        return output

    @classmethod
    def _required_z(cls, context: CliContextPort) -> float:
        raw: Any = context.get_parameter_value(cls.OUTPUT_KEY)
        # execute() re-sets this same key to an already-parsed float, so a
        # later re-evaluation of this same state (the sequence is walked
        # from the start on every observed_state refresh) must accept that
        # too, not just the raw --z string this run started with.
        if isinstance(raw, (int, float)):
            return float(raw)
        if not isinstance(raw, str) or not raw.strip():
            cls._log_default_used("--z was not given")
            return cls.DEFAULT_Z_METERS
        try:
            return float(raw.strip())
        except ValueError:
            cls._log_default_used(f"--z {raw!r} does not read as a real number")
            return cls.DEFAULT_Z_METERS

    @classmethod
    def _log_default_used(cls, reason: str) -> None:
        repository: Any = ActiveLogRepositoryBroker.instance().get()
        if repository is None:
            return
        repository.log_info(
            f"{reason}; using the default work plane Z of "
            f"{cls.DEFAULT_Z_METERS} m."
        )

    @classmethod
    def _reject_unimplemented_axes(cls, context: CliContextPort) -> None:
        if cls.Z_FLAG in context.raw_args:
            return
        flag: str
        for flag in cls.UNIMPLEMENTED_FLAGS:
            if flag in context.raw_args:
                raise NotImplementedError(
                    f"{flag} work plane is not implemented yet."
                )
