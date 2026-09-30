import math
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type

import yaml

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.adapter.geometry_state import GeometricProductState
from infobim.ifc.domain.port.machine import (
    GeometricProductCreateProcessStatePort,
    GeometricProductCreateStateEvaluatorPort,
    GeometricProductCreateStateTransitionHandlerPort,
)
from infobim.ifc.plugin.check.is_geometric_representation_context_ready.check import (
    main as check_geometric_representation_context_ready,
)
from infobim.ifc.plugin.check.is_ifc_model_healthy.check import (
    main as check_ifc_model_healthy,
)
from infobim.ifc.plugin.check.is_ifc_project_synced.check import (
    main as check_ifc_project_synced,
)
from infobim.ifc.plugin.check.is_object_placement_valid.check import (
    main as check_object_placement_valid,
)
from infobim.ifc.plugin.check.is_shape_representation_context_valid.check import (
    main as check_shape_representation_context_valid,
)
from infobim.ifc.plugin.check.is_spatial_structure_valid.check import (
    main as check_spatial_structure_valid,
)
from infobim.ifc.plugin.check.is_unit_defined.check import (
    main as check_unit_defined,
)
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)


class GeometricProductCreateStateEvaluatorAdapter(
    GeometricProductCreateStateEvaluatorPort
):
    """
    Read the target and report the furthest geometric-product state reached.

    This follows the same evaluator pattern as the project/container machines:
    start at the last known state, run the standalone checks that define the
    next state, advance only when all of them hold, and stop at the first state
    whose contract is not satisfied.

    IFC_MODEL_HEALTHY is a composite state, but its concerns remain separate:
    target usability/schema agreement, IfcProject synchronization, geometric
    representation context, spatial structure, object placement and existing
    shape-representation context integrity are each read by their own
    standalone check. No check calls another check.

    UNIT_DEFINED is then read by its own standalone check.

    POSITION_DEFINED is read differently, and it has to be: it is a fact
    of this run rather than of the model, so no file states it and no
    standalone check could. It is read from the run itself — the position
    object bound in the context, which the context keeps in memory and
    never writes to context.ttl — so a process that starts again finds it
    undefined and defines it again. Later run-local states are not
    guessed here until their contracts are implemented.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    POSITION_KEY: ClassVar[str] = "position"
    POSITION_AXES: ClassVar[Tuple[str, ...]] = ("x", "y", "z")
    GEOMETRY_KEY: ClassVar[str] = "geometry"
    KIND_KEY: ClassVar[str] = "kind"
    PARAMETERS_KEY: ClassVar[str] = "parameters"
    GEOMETRY_ITEM_KEY: ClassVar[str] = "geometry_item"
    STEP_ELEMENTS_KEY: ClassVar[str] = "step_elements"
    SHAPE_REPRESENTATION_KEY: ClassVar[str] = "shape_representation"
    GEOMETRIC_PRODUCT_KEY: ClassVar[str] = "geometric_product"
    FEDERATED_PRODUCT_KEY: ClassVar[str] = "federated_product"

    SUPPORTED_GEOMETRY_KINDS: ClassVar[set] = {"box", "cylinder", "sphere"}

    def evaluate(
        self,
        context: CliContextPort,
    ) -> GeometricProductCreateProcessStatePort:
        project_path: Optional[Path] = self._path(context, self.CONTAINER_PATH_KEY)
        model_path: Optional[Path] = self._path(context, self.IFC_MODEL_PATH_KEY)
        if project_path is None or model_path is None:
            return GeometricProductCreateProcessState.UNDEFINED

        project_path_value: str = str(project_path)
        model_path_value: str = str(model_path)
        reached_state: GeometricProductCreateProcessStatePort = (
            GeometricProductCreateProcessState.UNDEFINED
        )

        model_health_checks = (
            check_ifc_model_healthy,
            check_ifc_project_synced,
            check_geometric_representation_context_ready,
            check_spatial_structure_valid,
            check_object_placement_valid,
            check_shape_representation_context_valid,
        )
        for check in model_health_checks:
            if check(
                project_path=project_path_value,
                ifc_model_path=model_path_value,
            ) != 0:
                return reached_state

        reached_state = GeometricProductCreateProcessState.IFC_MODEL_HEALTHY

        if check_unit_defined(
            project_path=project_path_value,
            ifc_model_path=model_path_value,
        ) != 0:
            return reached_state

        reached_state = GeometricProductCreateProcessState.UNIT_DEFINED

        if not self._is_position_defined(context):
            return reached_state

        reached_state = GeometricProductCreateProcessState.POSITION_DEFINED

        if not self._is_geometry_defined(context):
            return reached_state

        reached_state = GeometricProductCreateProcessState.GEOMETRY_DEFINED

        if not self._is_geometry_created(context):
            return reached_state

        reached_state = GeometricProductCreateProcessState.GEOMETRY_CREATED

        if not self._is_shape_representation_created(context):
            return reached_state

        reached_state = GeometricProductCreateProcessState.SHAPE_REPRESENTATION_CREATED

        if not self._is_geometric_product_created(context):
            return reached_state

        reached_state = GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_CREATED

        if not self._is_geometric_product_federated(context):
            return reached_state

        return GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_FEDERATED

    @classmethod
    def _is_position_defined(cls, context: CliContextPort) -> bool:
        """
        Report whether this run has defined the position.

        POSITION_DEFINED is a fact of the run, so there is no file for a
        standalone check to read: the position is an object bound in the
        context, which the context keeps in process memory and never
        writes to context.ttl. A process that starts again therefore
        finds it undefined and defines it again, which is exactly what
        the state means.
        """
        position: Any = context.get_parameter_value(cls.POSITION_KEY)
        if not isinstance(position, dict):
            return False

        for axis in cls.POSITION_AXES:
            if axis not in position:
                return False

            coordinate: Any = position[axis]
            if not isinstance(coordinate, float) or not math.isfinite(coordinate):
                return False

        return True

    @classmethod
    def _is_geometry_defined(cls, context: CliContextPort) -> bool:
        """
        Report whether this run has produced a valid GeometryDefinition.

        GEOMETRY_DEFINED, like POSITION_DEFINED, is a fact of the run.
        The geometry command produces either a live GeometryDefinition
        instance or its dict-serialized equivalent under the geometry
        key, and the capability for this state then serializes it.
        """
        if not context.has_parameter(cls.GEOMETRY_KEY):
            return False

        value: Any = context.get_parameter_value(cls.GEOMETRY_KEY)
        if isinstance(value, GeometryDefinition):
            kind: str = value.kind
            parameters: Any = value.parameters
        elif isinstance(value, dict):
            kind = value.get(cls.KIND_KEY)
            parameters = value.get(cls.PARAMETERS_KEY)
        else:
            return False

        if not isinstance(kind, str) or kind not in cls.SUPPORTED_GEOMETRY_KINDS:
            return False
        if not isinstance(parameters, (list, tuple)):
            return False
        for pair in parameters:
            if (
                not isinstance(pair, (list, tuple))
                or len(pair) != 2
                or not isinstance(pair[0], str)
            ):
                return False
        return True

    @classmethod
    def _is_geometry_created(cls, context: CliContextPort) -> bool:
        """
        Report whether a concrete IFC geometry representation item exists.

        This reads it from the run-local context: ``GEOMETRY_CREATED`` is
        conceptually a fact of the model (the file on disk owns an
        ``IfcBlock``, ``IfcCylinder`` or similar), but checking the file
        contents every step duplicates work the capability already did.
        The capability writes both a specific geometry_item reference and
        the list of step_elements it produced; either one is enough to
        report that an item was created.
        """
        if context.has_parameter(cls.GEOMETRY_ITEM_KEY):
            geometry_item: Any = context.get_parameter_value(cls.GEOMETRY_ITEM_KEY)
            if isinstance(geometry_item, str) and geometry_item.strip():
                return True
        if context.has_parameter(cls.STEP_ELEMENTS_KEY):
            step_elements: Any = context.get_parameter_value(cls.STEP_ELEMENTS_KEY)
            if isinstance(step_elements, (list, tuple)) and any(
                isinstance(ref, str) and ref.strip() for ref in step_elements
            ):
                return True
        return False

    @classmethod
    def _is_shape_representation_created(cls, context: CliContextPort) -> bool:
        """
        Report whether an ``IfcShapeRepresentation`` wraps the geometry.

        As with the step before, the capability produces a concrete
        reference under the ``shape_representation`` key on success, so
        the evaluator reads that reference rather than scanning the file.
        """
        if not context.has_parameter(cls.SHAPE_REPRESENTATION_KEY):
            return False
        value: Any = context.get_parameter_value(cls.SHAPE_REPRESENTATION_KEY)
        return isinstance(value, str) and value.strip()

    @classmethod
    def _is_geometric_product_created(cls, context: CliContextPort) -> bool:
        """
        Report whether the product this run assembles exists.

        The capability binds the GlobalId of the element it created, and
        that identity is what the state means: the product the title
        names exists, carrying the representation created before it.
        """
        if not context.has_parameter(cls.GEOMETRIC_PRODUCT_KEY):
            return False

        value: Any = context.get_parameter_value(cls.GEOMETRIC_PRODUCT_KEY)

        return isinstance(value, str) and bool(value.strip())

    @classmethod
    def _is_geometric_product_federated(cls, context: CliContextPort) -> bool:
        """
        Report whether the product this run assembled is in the model.

        The capability binds the identity it federated, and that is what
        the state means: the model the project publishes carries this
        run's product. A run that starts again federates its own product
        again, because what it assembled is not what the last run did.
        """
        if not context.has_parameter(cls.FEDERATED_PRODUCT_KEY):
            return False

        value: Any = context.get_parameter_value(cls.FEDERATED_PRODUCT_KEY)

        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def _path(context: CliContextPort, key: str) -> Optional[Path]:
        """
        Return the path bound under the given key, or None when none is.
        """
        value: Any = context.get_parameter_value(key)
        if not isinstance(value, str) or not value.strip():
            return None

        return Path(value).expanduser().resolve()


class GeometricProductCreateStateTransitionHandler(
    GeometricProductCreateStateTransitionHandlerPort
):
    """
    Drives one geometric product through its own machine.

    Each transition is one capability, resolved by the id the state
    declares and executed through the capability executor. The handler
    sequences them and nothing else: no capability here reaches for
    another, and no IFC decision is taken outside the capability that owns
    the state it brings about.

    Target states' capabilities are resolved by id through CapabilityLoader,
    never by importing a concrete capability class: that import would tie
    this machine to one particular implementation of the state instead of
    whichever capability declares that id.
    """

    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim", "ontobdc")

    TITLE_KEY: ClassVar[str] = "title"
    GEOMETRIC_PRODUCT_KEY: ClassVar[str] = "geometric_product"

    RUN_LOCAL_KEYS: ClassVar[Tuple[str, ...]] = (
        "geometry_item",
        "step_elements",
        "shape_representation",
        "geometric_product",
        "federated_product",
    )

    STATECHART_PACKAGE: ClassVar[str] = (
        "infobim.ifc.plugin.machine.geometric_product_create"
    )
    STATECHART_FILE: ClassVar[str] = "standard_geometric_product_create.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "GeometricProductCreateProcessStatePort"

    CAPABILITY_IDS: ClassVar[Dict[GeometricProductCreateProcessStatePort, str]] = {
        GeometricProductCreateProcessState.IFC_MODEL_HEALTHY: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "ifc_model_healthy"
        ),
        GeometricProductCreateProcessState.UNIT_DEFINED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "unit_defined"
        ),
        GeometricProductCreateProcessState.POSITION_DEFINED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "position_defined"
        ),
        GeometricProductCreateProcessState.GEOMETRY_DEFINED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometry_defined"
        ),
        GeometricProductCreateProcessState.GEOMETRY_CREATED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometry_created"
        ),
        GeometricProductCreateProcessState.SHAPE_REPRESENTATION_CREATED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "shape_representation_created"
        ),
        GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_CREATED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometric_product_created"
        ),
        GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_FEDERATED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometric_product_federated"
        ),
    }

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._container_path: Path = Path(
            str(context.get_parameter_value("container_path"))
        ).expanduser().resolve()
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: GeometricProductCreateStateEvaluatorPort = (
            GeometricProductCreateStateEvaluatorAdapter()
        )
        self._active_state: Optional[GeometricProductCreateProcessStatePort] = None
        self._observed_state: Optional[GeometricProductCreateProcessStatePort] = None
        self._state_names: Optional[List[str]] = None

    @property
    def current_state(self) -> GeometricProductCreateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> GeometricProductCreateProcessStatePort:
        """
        The state the geometric product creation is in, read once per
        machine step.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(
        self,
        to_state: GeometricProductCreateProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: GeometricProductCreateProcessStatePort,
    ) -> None:
        if self._is_reached(to_state):
            return

        self._logger.log_info(
            f"IFC geometric product create transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability_id: Optional[str] = self.CAPABILITY_IDS.get(to_state)
        if capability_id is None:
            raise ValueError(
                f"IFC geometric product create capability id not declared "
                f"for state: {to_state.value}"
            )

        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"IFC geometric product create capability not found for "
                f"state: {to_state.value} (id: {capability_id})"
            )

        capability: CapabilityPort = capability_type()
        try:
            CapabilityExecutor.execute(
                capability,
                self._context,
                StrategyParamResolver(
                    ResolverLoader(root_packages=self.CAPABILITY_ROOT_PACKAGES)
                ),
            )
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: GeometricProductCreateProcessStatePort,
        to_state: GeometricProductCreateProcessStatePort,
    ) -> bool:
        """
        Report whether the transition's target state has been reached.

        Reached, not read back exactly. The evaluator answers with the
        furthest state whose fact already holds, and that can legitimately
        be further along than the transition just taken: the geometry of a
        run is defined by the command before the machine starts, so the
        moment the position is defined the reading jumps to
        GEOMETRY_DEFINED. Demanding equality would call that a failed
        transition, which is how creating a box with a position reported a
        postcondition error on a state it had in fact just reached.
        """
        if from_state == to_state:
            return False

        return self._is_reached(to_state)

    def execute(self) -> CommandResponse:
        self._forget_run_local_references()
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=GeometricProductCreateProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._statechart_file_path(),
        )
        visited_states: List[str] = worker.work()
        self._file_state_by_identity()

        return self._final_response(visited_states)

    def _file_state_by_identity(self) -> None:
        """
        Leave the product's state filed under the product, not its title.

        A product is assembled under the title it was asked for, because
        while it is being assembled that is all it has. Once the machine
        has run it has an identity, and the identity is what the state
        belongs to: a title can be given to another product tomorrow, and
        the state of one is never the state of the other.

        This is the last thing the machine does, after every state and
        before the response, so nothing in the run has to know that the
        directory it wrote into is not the directory it ends up in. A run
        that produced no product leaves its state where it is — there is
        no identity yet to file it under.
        """
        global_id: Any = self._context.get_parameter_value(
            self.GEOMETRIC_PRODUCT_KEY
        )
        if not isinstance(global_id, str) or not global_id.strip():
            return

        title: Any = self._context.get_parameter_value(self.TITLE_KEY)
        if not isinstance(title, str) or not title.strip():
            return

        GeometricProductState.identified_as(
            self._container_path,
            title,
            global_id.strip(),
        )

    def bind_active_state(self, state: GeometricProductCreateProcessStatePort) -> None:
        self._active_state = state
        self._forget_observed_state()

    @classmethod
    def statechart_path(cls) -> Path:
        """
        Return the statechart this machine runs.
        """
        return StatechartLocator.locate(
            cls.STATECHART_PACKAGE,
            cls.STATECHART_FILE,
        )

    def _forget_observed_state(self) -> None:
        """
        Drop the reading, so the next one goes back to its source.
        """
        self._observed_state = None

    def _forget_run_local_references(self) -> None:
        """
        Drop what an earlier process said about entities it created.

        The references the later states leave — the representation item,
        the elements written with it, the shape representation — name
        entities of one run's product. The CLI context outlives a
        command and writes strings to context.ttl, so without this a
        second run would read the first run's item, report the state as
        already reached, and wrap a block created for another product.
        The position and the geometry of this run are not touched: the
        first is defined inside this machine, and the second is what the
        command handed it before the machine started.
        """
        for key in self.RUN_LOCAL_KEYS:
            self._context.delete_parameter(key)

    def _is_reached(self, to_state: GeometricProductCreateProcessStatePort) -> bool:
        """
        Report whether the observed state is the target one or past it.

        The order is the statechart's own chain, read from the chart
        rather than restated here, so a state added to the machine is
        ordered by the same file that declares the transition to it. A
        state the chart does not carry is an error rather than a state
        nothing compares with.
        """
        state_names: List[str] = self._state_sequence()
        observed_name: str = self.observed_state.value.strip("_")
        target_name: str = to_state.value.strip("_")
        if observed_name not in state_names:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the "
                f"geometric product create statechart."
            )

        if target_name not in state_names:
            raise ValueError(
                f"Target state '{target_name}' is absent from the geometric "
                f"product create statechart."
            )

        return state_names.index(observed_name) >= state_names.index(target_name)

    def _state_sequence(self) -> List[str]:
        """
        Return the state names the statechart declares, in transition order.
        """
        if self._state_names is None:
            statechart_data: Any = yaml.safe_load(
                self._statechart_file_path().read_text(encoding="utf-8")
            ) or {}
            if not isinstance(statechart_data, dict):
                raise TypeError(
                    "The geometric product create statechart must be a mapping."
                )

            self._state_names = StateWorkerAdapter.compute_state_sequence(
                statechart_data
            )

        return self._state_names

    def _statechart_file_path(self) -> Path:
        return StatechartLocator.locate(
            self.STATECHART_PACKAGE,
            self.STATECHART_FILE,
        )

    def _final_response(self, visited_states: List[str]) -> CommandResponse:
        title_value: Any = self._context.get_parameter_value("title")
        title: str = str(title_value) if title_value is not None else ""

        return CommandResponse(
            title="IFC Geometric Product Created",
            description=(
                "The IFC geometric product ran through its creation state "
                "machine."
            ),
            content={
                "container_path": str(self._container_path),
                "title": title,
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )
