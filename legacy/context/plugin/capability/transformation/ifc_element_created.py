from math import sqrt
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple
from pathlib import Path
from importlib import import_module

from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor, TransformationCapability
from ontobdc.shared.adapter.chain_worker import ChainOfResponsibilityWorkerAdapter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)

from infobim.ifc.domain.port.product import IfcProductCreateResponsibilityPort
from infobim.context.adapter.taxonomy import (
    CAPABILITY_PREFIX, CONTAINER_PATH_KEY, DXF_PATH_KEY, MACHINE_PACKAGE,
    REPRESENTATION_PARAMETER_KEY, REPRESENTATION_STATE,
)
from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.plugin.parameter.ifc_model_path import IfcModelPathStrategy
from infobim.context.adapter.kind_resolution_event import KindResolutionEvent
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)
from infobim.ifc.plugin.machine.geometric_product_create.machine import (
    GeometricProductCreateStateTransitionHandler,
)
from infobim.ifc.plugin.capability.transformation.geometric_product_created import (
    GeometricProductCreatedCapability,
)
from infobim.context.plugin.capability.transformation.element_kind_representation_resolved import (
    ElementKindRepresentationResolvedCapability,
)

DxfVectorProcessState: Any = import_module(MACHINE_PACKAGE + ".state").DxfVectorProcessState


class IfcElementCreatedCapability(TransformationCapability):
    """Create one IfcPipeSegment per consecutive pair of captured trace points.

    The IFC class to create is read from the representation event's own
    JSON-LD: whichever ``rdfs:subClassOf`` target names an IFC4 class
    decides it, and a chain of ``IfcProductCreateResponsibilityPort``
    capabilities -- today only ``IfcPipeSegmentElementCreationCapability``
    -- answers for it, exactly as ``GeometricProductCreatedCapability``
    already dispatches for the standalone `ifc box/cylinder/sphere`
    commands. Each segment's own geometry, position, product-creation and
    federation states are driven the same way that machine drives them,
    reusing its capability ids one state at a time, since this run knows
    the class up front and does not go through --ifc-class.
    """

    STATE: ClassVar[str] = DxfVectorProcessState.IFC_ELEMENT_CREATED.value
    OUTPUT_KEY: ClassVar[str] = "ifc_elements"
    TITLE_KEY: ClassVar[str] = "title"
    GEOMETRY_KEY: ClassVar[str] = "geometry"
    ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim", "ontobdc")
    ZERO_LENGTH_TOLERANCE: ClassVar[float] = 1e-9

    IFC4_NAMESPACE: ClassVar[str] = (
        "https://standards.buildingsmart.org/IFC/DEV/IFC4/FINAL/OWL#"
    )
    SUBCLASS_OF_PREDICATE: ClassVar[str] = (
        "http://www.w3.org/2000/01/rdf-schema#subClassOf"
    )

    GEOMETRY_STATE_ORDER: ClassVar[Tuple[Any, ...]] = (
        GeometricProductCreateProcessState.IFC_MODEL_HEALTHY,
        GeometricProductCreateProcessState.UNIT_DEFINED,
        GeometricProductCreateProcessState.POSITION_DEFINED,
        GeometricProductCreateProcessState.GEOMETRY_DEFINED,
        GeometricProductCreateProcessState.GEOMETRY_CREATED,
        GeometricProductCreateProcessState.SHAPE_REPRESENTATION_CREATED,
    )

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=CAPABILITY_PREFIX + STATE.strip("_"),
        version="1.0.0", name="Ifc Element Created",
        description=(
            "Create one IfcPipeSegment per consecutive pair of captured "
            "trace points, sized by the confirmed work plane and radius."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "vector", "ifc", "pipe-segment"],
        output_schema={"properties": {OUTPUT_KEY: {"type": "array"}}},
    )

    def label(self, lang: str = "en") -> str:
        return "Ifc element created"

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        event: Optional[Dict[str, Any]] = KindResolutionEvent.read(
            context, self.STATE, self.METADATA.version, self.OUTPUT_KEY
        )
        if event is None:
            return False
        global_ids: Any = event["output"][self.OUTPUT_KEY]
        if not isinstance(global_ids, list) or not global_ids:
            raise ValueError(
                f"ETL output {self.OUTPUT_KEY} must be a non-empty list of GlobalIds."
            )
        context.set_parameter_value(self.OUTPUT_KEY, global_ids)
        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = self._container_path(context)
        IfcModelPathStrategy().execute(context)
        if hotfix_container_manifest_synced(
            container_path=str(container_path),
            root_path=str(context.root_path),
        ) != 0:
            raise IfcCreationError(
                f"The RO-Crate of the project at {container_path} could not "
                f"be brought up to date, so what the project holds is not "
                f"stated."
            )

        ifc_class: str = self._ifc_class_from_representation(context)
        points: List[Tuple[float, float]] = self._trace_points(context)
        z: float = self._required_number(context, "z", "The work plane")
        radius: float = self._required_number(context, "radius", "The pipe radius")
        dxf_stem: str = Path(
            str(context.get_parameter_value(DXF_PATH_KEY))
        ).stem

        global_ids: List[str] = []
        index: int
        start: Tuple[float, float]
        end: Tuple[float, float]
        for index, (start, end) in enumerate(zip(points, points[1:]), start=1):
            title: str = f"{dxf_stem}_pipe_segment_{index}"
            direction: Tuple[float, float, float]
            height: float
            direction, height = self._direction_and_height(start, end, index)

            self._clear_run_local_state(context)
            context.set_parameter_value(self.TITLE_KEY, title)
            context.set_parameter_value("x", start[0])
            context.set_parameter_value("y", start[1])
            context.set_parameter_value("z", z)
            context.set_parameter_value(
                self.GEOMETRY_KEY,
                GeometryDefinition(
                    kind=GeometryDefinition.CYLINDER_KIND,
                    parameters=(
                        ("radius", radius),
                        ("height", height),
                        ("direction_x", direction[0]),
                        ("direction_y", direction[1]),
                        ("direction_z", direction[2]),
                    ),
                ),
            )

            self._drive_geometry_states(context)
            global_id: str = self._create_product(context, ifc_class)
            self._federate_product(context)
            global_ids.append(global_id)

        output: Dict[str, Any] = {self.OUTPUT_KEY: global_ids}
        KindResolutionEvent.write(context, self.STATE, self.METADATA.version, output)
        return output

    @classmethod
    def _ifc_class_from_representation(cls, context: CliContextPort) -> str:
        event: Optional[Dict[str, Any]] = KindResolutionEvent.read(
            context,
            REPRESENTATION_STATE,
            ElementKindRepresentationResolvedCapability.METADATA.version,
            REPRESENTATION_PARAMETER_KEY,
        )
        if event is None:
            raise IfcCreationError(
                "The element representation has not been resolved for this "
                "document, so no IFC class is declared to create."
            )

        nodes: Any = event["output"][REPRESENTATION_PARAMETER_KEY]
        classes: Set[str] = set()
        node: Any
        for node in nodes:
            if not isinstance(node, dict):
                continue
            reference: Any
            for reference in node.get(cls.SUBCLASS_OF_PREDICATE, []):
                identifier: Any = (
                    reference.get("@id") if isinstance(reference, dict) else None
                )
                if isinstance(identifier, str) and identifier.startswith(
                    cls.IFC4_NAMESPACE
                ):
                    classes.add(identifier[len(cls.IFC4_NAMESPACE):])

        if not classes:
            raise IfcCreationError(
                "The element representation declares no IFC4 class to create."
            )
        if len(classes) != 1:
            raise IfcCreationError(
                "The element representation declares more than one IFC4 "
                f"class: {sorted(classes)}."
            )
        return next(iter(classes))

    @classmethod
    def _trace_points(cls, context: CliContextPort) -> List[Tuple[float, float]]:
        raw_points: Any = context.get_parameter_value("vector_trace")
        if not isinstance(raw_points, list) or len(raw_points) < 2:
            raise IfcCreationError("No captured vector trace is available.")
        return [(float(point[0]), float(point[1])) for point in raw_points]

    @staticmethod
    def _required_number(context: CliContextPort, key: str, subject: str) -> float:
        value: Any = context.get_parameter_value(key)
        if not isinstance(value, (int, float)):
            raise IfcCreationError(f"{subject} is not defined for this run.")
        return float(value)

    @classmethod
    def _direction_and_height(
        cls,
        start: Tuple[float, float],
        end: Tuple[float, float],
        index: int,
    ) -> Tuple[Tuple[float, float, float], float]:
        delta_x: float = end[0] - start[0]
        delta_y: float = end[1] - start[1]
        height: float = sqrt(delta_x * delta_x + delta_y * delta_y)
        if height <= cls.ZERO_LENGTH_TOLERANCE:
            raise IfcCreationError(
                f"Segment {index} of the captured trace has zero length."
            )
        return (delta_x / height, delta_y / height, 0.0), height

    @classmethod
    def _drive_geometry_states(cls, context: CliContextPort) -> None:
        state: Any
        for state in cls.GEOMETRY_STATE_ORDER:
            capability_id: Optional[str] = (
                GeometricProductCreateStateTransitionHandler.CAPABILITY_IDS.get(state)
            )
            if capability_id is None:
                raise IfcCreationError(
                    f"Geometric product create capability id not declared for "
                    f"state: {state.value}"
                )
            cls._run_capability(context, capability_id)

    @classmethod
    def _create_product(cls, context: CliContextPort, ifc_class: str) -> str:
        worker: ChainOfResponsibilityWorkerAdapter = ChainOfResponsibilityWorkerAdapter(
            support=IfcProductCreateResponsibilityPort,
            context=context,
            logger=None,
            statechart_file_path=GeometricProductCreatedCapability.statechart_path(),
            root_packages=cls.ROOT_PACKAGES,
            extra_data={GeometricProductCreatedCapability.IFC_CLASS_KEY: ifc_class},
        )
        results: Dict[str, Dict[str, Any]] = worker.work()
        if not results:
            raise IfcCreationError(
                f"No creation capability answers for the IFC class "
                f"'{ifc_class}', so the product it names cannot be created."
            )

        global_id: Any = context.get_parameter_value(
            GeometricProductCreatedCapability.GEOMETRIC_PRODUCT_KEY
        )
        if not isinstance(global_id, str) or not global_id.strip():
            raise IfcCreationError(
                f"The capability that created the product as '{ifc_class}' "
                f"left no identity for it."
            )
        return global_id.strip()

    @classmethod
    def _federate_product(cls, context: CliContextPort) -> None:
        capability_id: Optional[str] = (
            GeometricProductCreateStateTransitionHandler.CAPABILITY_IDS.get(
                GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_FEDERATED
            )
        )
        if capability_id is None:
            raise IfcCreationError(
                "Geometric product create capability id not declared for "
                "state: geometric_product_federated"
            )
        cls._run_capability(context, capability_id)

    @classmethod
    def _run_capability(cls, context: CliContextPort, capability_id: str) -> None:
        capability_type: Any = CapabilityLoader(
            root_packages=cls.ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise IfcCreationError(
                f"Geometric product create capability not found: {capability_id}"
            )
        CapabilityExecutor.execute(
            capability_type(),
            context,
            StrategyParamResolver(ResolverLoader(root_packages=cls.ROOT_PACKAGES)),
        )

    @classmethod
    def _clear_run_local_state(cls, context: CliContextPort) -> None:
        key: str
        for key in GeometricProductCreateStateTransitionHandler.RUN_LOCAL_KEYS:
            context.delete_parameter(key)

    @staticmethod
    def _container_path(context: CliContextPort) -> Path:
        value: Any = context.get_parameter_value(CONTAINER_PATH_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The InfoBIM project is missing from the command context, so "
                "the product has nowhere to be created."
            )
        return Path(value).expanduser().resolve()
