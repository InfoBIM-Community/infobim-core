import math
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type
from pathlib import Path

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

from infobim.ifc.adapter.geometry_state import GeometricProductState
from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.dict.domain.model.definition import DictionaryEntry
from infobim.dict.domain.port.machine import (
    DictionaryEntityCreateProcessStatePort,
    DictionaryEntityCreateStateEvaluatorPort,
    DictionaryEntityCreateStateTransitionHandlerPort,
)
from infobim.dict.plugin.machine.dictionary_entity_create.state import (
    DictionaryEntityContextKeys,
    DictionaryEntityCreateProcessState,
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
from infobim.ifc.plugin.check.is_spatial_structure_valid.check import (
    main as check_spatial_structure_valid,
)
from infobim.ifc.plugin.check.is_geometric_representation_context_ready.check import (
    main as check_geometric_representation_context_ready,
)
from infobim.ifc.plugin.check.is_shape_representation_context_valid.check import (
    main as check_shape_representation_context_valid,
)


class DictionaryEntityCreateStateEvaluatorAdapter(
    DictionaryEntityCreateStateEvaluatorPort
):
    """
    Read the run and report the furthest dictionary state reached.

    The model's health is read the way every IFC flow of this codebase
    reads it: by the standalone checks that own each concern, none of
    which calls another. Nothing about a dictionary is asked of them —
    a model is healthy or not regardless of what is about to be applied
    to one of its elements.

    Everything after that is a fact of this run. Where the element goes,
    what was downloaded and what was understood of it are answers this
    invocation produced, so they are read from the invocation itself: the
    entry is read back as the file this run wrote, and the definitions as
    the object this run bound, which the context keeps in memory and never
    writes to ``context.ttl``. A process that starts again therefore
    downloads and reads again, which is what these states mean.
    """

    POSITION_AXES: ClassVar[Tuple[str, ...]] = ("x", "y", "z")

    def evaluate(
        self,
        context: CliContextPort,
    ) -> DictionaryEntityCreateProcessStatePort:
        project_path: Optional[Path] = self._path(
            context,
            DictionaryEntityContextKeys.CONTAINER_PATH_KEY,
        )
        model_path: Optional[Path] = self._path(
            context,
            DictionaryEntityContextKeys.IFC_MODEL_PATH_KEY,
        )
        if project_path is None or model_path is None:
            return DictionaryEntityCreateProcessState.UNDEFINED

        project_path_value: str = str(project_path)
        model_path_value: str = str(model_path)
        reached_state: DictionaryEntityCreateProcessStatePort = (
            DictionaryEntityCreateProcessState.UNDEFINED
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

        reached_state = DictionaryEntityCreateProcessState.IFC_MODEL_HEALTHY

        if not self._is_position_defined(context):
            return reached_state

        reached_state = DictionaryEntityCreateProcessState.POSITION_DEFINED

        if not self._is_element_identified(context):
            return reached_state

        reached_state = DictionaryEntityCreateProcessState.ELEMENT_IDENTIFIED

        if not self._is_entry_downloaded(context):
            return reached_state

        reached_state = DictionaryEntityCreateProcessState.DICTIONARY_ENTRY_DOWNLOADED

        if not self._is_definition_read(context):
            return reached_state

        reached_state = DictionaryEntityCreateProcessState.ENTITY_DEFINITION_READ

        if not self._is_geometry_defined(context):
            return reached_state

        reached_state = DictionaryEntityCreateProcessState.GEOMETRY_DEFINED

        if not self._is_geometry_created(context):
            return reached_state

        reached_state = DictionaryEntityCreateProcessState.GEOMETRY_CREATED

        if not self._is_bound(
            context,
            DictionaryEntityContextKeys.SHAPE_REPRESENTATION_KEY,
        ):
            return reached_state

        reached_state = DictionaryEntityCreateProcessState.SHAPE_REPRESENTATION_CREATED

        if not self._is_bound(
            context,
            DictionaryEntityContextKeys.GEOMETRIC_PRODUCT_KEY,
        ):
            return reached_state

        reached_state = DictionaryEntityCreateProcessState.GEOMETRIC_PRODUCT_CREATED

        if not self._is_bound(
            context,
            DictionaryEntityContextKeys.FEDERATED_PRODUCT_KEY,
        ):
            return reached_state

        return DictionaryEntityCreateProcessState.GEOMETRIC_PRODUCT_FEDERATED

    @classmethod
    def _is_position_defined(cls, context: CliContextPort) -> bool:
        """
        Report whether this run has defined where the element goes.
        """
        position: Any = context.get_parameter_value(
            DictionaryEntityContextKeys.POSITION_KEY
        )
        if not isinstance(position, dict):
            return False

        axis: str
        for axis in cls.POSITION_AXES:
            if axis not in position:
                return False

            coordinate: Any = position[axis]
            if not isinstance(coordinate, float) or not math.isfinite(coordinate):
                return False

        return True

    @staticmethod
    def _is_element_identified(context: CliContextPort) -> bool:
        """
        Report whether this run knows which element it is defining.
        """
        element_global_id: Any = context.get_parameter_value(
            DictionaryEntityContextKeys.ELEMENT_GLOBAL_ID_KEY
        )

        return isinstance(element_global_id, str) and bool(
            element_global_id.strip()
        )

    @staticmethod
    def _is_entry_downloaded(context: CliContextPort) -> bool:
        """
        Report whether the entry this run downloaded is on disk.

        The path alone is not the state: the state is the document, and a
        path to a file that is not there says only that some run once
        wrote one down.
        """
        stored: Any = context.get_parameter_value(
            DictionaryEntityContextKeys.DICTIONARY_ENTRY_PATH_KEY
        )
        if not isinstance(stored, str) or not stored.strip():
            return False

        return Path(stored.strip()).is_file()

    @staticmethod
    def _is_definition_read(context: CliContextPort) -> bool:
        """
        Report whether this run understood what the entry declares.
        """
        entry: Any = context.get_parameter_value(
            DictionaryEntityContextKeys.DICTIONARY_DEFINITION_KEY
        )

        return isinstance(entry, DictionaryEntry) and bool(entry.definitions)

    @staticmethod
    def _is_geometry_defined(context: CliContextPort) -> bool:
        """
        Report whether this run has a shape to create.

        What counts is a definition the geometry responsibilities can
        dispatch on, which is what the state binds: a kind they answer
        for, carrying named parameters. Reading it back through the model
        that owns that contract keeps this from having a second opinion
        about what a defined shape is.
        """
        value: Any = context.get_parameter_value(
            DictionaryEntityContextKeys.GEOMETRY_KEY
        )
        if isinstance(value, GeometryDefinition):
            return True
        if not isinstance(value, dict):
            return False

        return GeometryDefinition.from_dict(value) is not None

    @classmethod
    def _is_geometry_created(cls, context: CliContextPort) -> bool:
        """
        Report whether a concrete IFC representation item exists.

        The capability that creates it leaves both a reference to the
        item and the elements it wrote; either one says an item was
        created.
        """
        if cls._is_bound(context, DictionaryEntityContextKeys.GEOMETRY_ITEM_KEY):
            return True

        elements: Any = context.get_parameter_value(
            DictionaryEntityContextKeys.STEP_ELEMENTS_KEY
        )

        return isinstance(elements, (list, tuple)) and any(
            isinstance(reference, str) and reference.strip()
            for reference in elements
        )

    @staticmethod
    def _is_bound(context: CliContextPort, key: str) -> bool:
        """
        Report whether this run left a reference under the given key.
        """
        value: Any = context.get_parameter_value(key)

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


class DictionaryEntityCreateStateTransitionHandler(
    DictionaryEntityCreateStateTransitionHandlerPort
):
    """
    Drives one element's dictionary definition through its own machine.

    Each transition is one capability, resolved by the id the state
    declares and executed through the capability executor. Two of those
    ids belong to the IFC domain and are reused as they are: a healthy
    target model and a position stated by this run are the same facts here
    as they are when a geometric product is created, and restating them
    under new ids would be two implementations of one concern drifting
    apart. The dictionary's own states are the ones this domain owns.
    """

    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim", "ontobdc")

    RUN_LOCAL_KEYS: ClassVar[Tuple[str, ...]] = (
        DictionaryEntityContextKeys.ELEMENT_GLOBAL_ID_KEY,
        DictionaryEntityContextKeys.DICTIONARY_ENTRY_PATH_KEY,
        DictionaryEntityContextKeys.DICTIONARY_DEFINITION_KEY,
        DictionaryEntityContextKeys.GEOMETRY_KEY,
        DictionaryEntityContextKeys.GEOMETRY_ITEM_KEY,
        DictionaryEntityContextKeys.STEP_ELEMENTS_KEY,
        DictionaryEntityContextKeys.SHAPE_REPRESENTATION_KEY,
        DictionaryEntityContextKeys.GEOMETRIC_PRODUCT_KEY,
        DictionaryEntityContextKeys.FEDERATED_PRODUCT_KEY,
    )

    STATECHART_PACKAGE: ClassVar[str] = (
        "infobim.dict.plugin.machine.dictionary_entity_create"
    )
    STATECHART_FILE: ClassVar[str] = "standard_dictionary_entity_create.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "DictionaryEntityCreateProcessStatePort"

    CAPABILITY_IDS: ClassVar[Dict[DictionaryEntityCreateProcessStatePort, str]] = {
        DictionaryEntityCreateProcessState.IFC_MODEL_HEALTHY: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "ifc_model_healthy"
        ),
        DictionaryEntityCreateProcessState.POSITION_DEFINED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "position_defined"
        ),
        DictionaryEntityCreateProcessState.ELEMENT_IDENTIFIED: (
            "org.infobim.dict.plugin.capability.transformation.target."
            "element_identified"
        ),
        DictionaryEntityCreateProcessState.DICTIONARY_ENTRY_DOWNLOADED: (
            "org.infobim.dict.plugin.capability.transformation.target."
            "dictionary_entry_downloaded"
        ),
        DictionaryEntityCreateProcessState.ENTITY_DEFINITION_READ: (
            "org.infobim.dict.plugin.capability.transformation.target."
            "entity_definition_read"
        ),
        DictionaryEntityCreateProcessState.GEOMETRY_DEFINED: (
            "org.infobim.dict.plugin.capability.transformation.target."
            "geometry_defined"
        ),
        DictionaryEntityCreateProcessState.GEOMETRY_CREATED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometry_created"
        ),
        DictionaryEntityCreateProcessState.SHAPE_REPRESENTATION_CREATED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "shape_representation_created"
        ),
        DictionaryEntityCreateProcessState.GEOMETRIC_PRODUCT_CREATED: (
            "org.infobim.dict.plugin.capability.transformation.target."
            "dictionary_product_created"
        ),
        DictionaryEntityCreateProcessState.GEOMETRIC_PRODUCT_FEDERATED: (
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
            str(
                context.get_parameter_value(
                    DictionaryEntityContextKeys.CONTAINER_PATH_KEY
                )
            )
        ).expanduser().resolve()
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: DictionaryEntityCreateStateEvaluatorPort = (
            DictionaryEntityCreateStateEvaluatorAdapter()
        )
        self._active_state: Optional[DictionaryEntityCreateProcessStatePort] = None
        self._observed_state: Optional[DictionaryEntityCreateProcessStatePort] = None
        self._state_names: Optional[List[str]] = None

    @property
    def current_state(self) -> DictionaryEntityCreateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> DictionaryEntityCreateProcessStatePort:
        """
        The state this definition is in, read once per machine step.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(
        self,
        to_state: DictionaryEntityCreateProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: DictionaryEntityCreateProcessStatePort,
    ) -> None:
        if self._is_reached(to_state):
            return

        self._logger.log_info(
            f"Dictionary entity create transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability_id: Optional[str] = self.CAPABILITY_IDS.get(to_state)
        if capability_id is None:
            raise ValueError(
                f"Dictionary entity create capability id not declared for "
                f"state: {to_state.value}"
            )

        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"Dictionary entity create capability not found for state: "
                f"{to_state.value} (id: {capability_id})"
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
        from_state: DictionaryEntityCreateProcessStatePort,
        to_state: DictionaryEntityCreateProcessStatePort,
    ) -> bool:
        """
        Report whether the transition's target state has been reached.
        """
        if from_state == to_state:
            return False

        return self._is_reached(to_state)

    def execute(self) -> CommandResponse:
        self._forget_run_local_references()
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=DictionaryEntityCreateProcessState,
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
        Leave the element's geometry state filed under the element.

        A product is assembled under the title it was asked for, because
        that is what names its directory while it is being assembled, and
        once the machine has run the identity is what the state belongs
        to. This is the last thing the machine does, after every state
        and before the response, exactly as the IFC creation flow files
        its own — the two write into the same place and a state filed one
        way by one of them and another way by the other would be two
        answers to the same question.
        """
        global_id: Any = self._context.get_parameter_value(
            DictionaryEntityContextKeys.GEOMETRIC_PRODUCT_KEY
        )
        if not isinstance(global_id, str) or not global_id.strip():
            return

        title: Any = self._context.get_parameter_value(
            DictionaryEntityContextKeys.TITLE_KEY
        )
        if not isinstance(title, str) or not title.strip():
            return

        GeometricProductState.identified_as(
            self._container_path,
            title,
            global_id.strip(),
        )

    def bind_active_state(
        self,
        state: DictionaryEntityCreateProcessStatePort,
    ) -> None:
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
        Drop what an earlier process said it downloaded and understood.

        The CLI context outlives a command and writes strings to
        ``context.ttl``, so the entry path of an earlier run is still
        sitting there when the next one starts. Without this, defining an
        element from a different URI would report the download as already
        done and apply the previous dictionary's definitions under the new
        URI's name.
        """
        key: str
        for key in self.RUN_LOCAL_KEYS:
            self._context.delete_parameter(key)

    def _is_reached(self, to_state: DictionaryEntityCreateProcessStatePort) -> bool:
        """
        Report whether the observed state is the target one or past it.

        The order is the statechart's own chain, read from the chart
        rather than restated here, so a state added to the machine is
        ordered by the same file that declares the transition to it.
        """
        state_names: List[str] = self._state_sequence()
        observed_name: str = self.observed_state.value.strip("_")
        target_name: str = to_state.value.strip("_")
        if observed_name not in state_names:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the "
                f"dictionary entity create statechart."
            )

        if target_name not in state_names:
            raise ValueError(
                f"Target state '{target_name}' is absent from the dictionary "
                f"entity create statechart."
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
                    "The dictionary entity create statechart must be a mapping."
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
        """
        Return what this run defined, and for which element.
        """
        entry: Any = self._context.get_parameter_value(
            DictionaryEntityContextKeys.DICTIONARY_DEFINITION_KEY
        )
        definitions: List[Dict[str, Any]] = (
            [definition.to_dict() for definition in entry.definitions]
            if isinstance(entry, DictionaryEntry)
            else []
        )

        return CommandResponse(
            title="InfoBIM Dictionary Entity",
            description=(
                "The element the dictionary defines ran through its creation "
                "state machine."
            ),
            content={
                "container_path": str(self._container_path),
                "element_global_id": self._stated(
                    DictionaryEntityContextKeys.ELEMENT_GLOBAL_ID_KEY
                ),
                "title": self._stated(DictionaryEntityContextKeys.TITLE_KEY),
                "kind": self._optional(
                    DictionaryEntityContextKeys.KIND_KEY
                ),
                "aeco_class_uri": self._optional(
                    DictionaryEntityContextKeys.AECO_CLASS_URI_KEY
                ),
                "dictionary_uri": self._stated(
                    DictionaryEntityContextKeys.DICTIONARY_URI_KEY
                ),
                "position": self._context.get_parameter_value(
                    DictionaryEntityContextKeys.POSITION_KEY
                ),
                "definitions": definitions,
                "geometric_product": self._optional(
                    DictionaryEntityContextKeys.GEOMETRIC_PRODUCT_KEY
                ),
                "federated_product": self._optional(
                    DictionaryEntityContextKeys.FEDERATED_PRODUCT_KEY
                ),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )

    def _optional(self, key: str) -> Optional[str]:
        """
        Return what the run stated under a key, or ``None`` for nothing.

        The namespace is the one value of this report that a run may
        legitimately not have: it is what a prefix expanded to, and an
        entry named in full expanded from no prefix.
        """
        value: Any = self._context.get_parameter_value(key)

        return value if isinstance(value, str) and value.strip() else None

    def _stated(self, key: str) -> str:
        """
        Return what the run stated under a key, as the string it is.
        """
        value: Any = self._context.get_parameter_value(key)
        if not isinstance(value, str):
            raise ValueError(
                f"The dictionary run states no '{key}', so it cannot be "
                f"reported."
            )

        return value
