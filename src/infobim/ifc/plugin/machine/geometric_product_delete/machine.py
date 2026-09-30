import shutil
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

from infobim.ifc.adapter.geometry_state import GeometricProductState
from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.plugin.machine.geometric_product_delete.port import (
    GeometricProductDeleteProcessStatePort,
    GeometricProductDeleteStateEvaluatorPort,
    GeometricProductDeleteStateTransitionHandlerPort,
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
from infobim.ifc.plugin.machine.geometric_product_delete.state import (
    GeometricProductDeleteProcessState,
)


class GeometricProductDeleteStateEvaluatorAdapter(
    GeometricProductDeleteStateEvaluatorPort
):
    """
    Read the target and report the furthest deletion state reached.

    Follows the same evaluator pattern as the creation and project
    machines: start at the last known state, run the standalone checks
    that define the next state, advance only when all of them hold, and
    stop at the first state whose contract is not satisfied.

    ``GLOBAL_ID_KNOWN`` is a fact of the run rather than of the model —
    it is the GlobalId the command was given, validated only for shape
    and presence. ``GLOBAL_ID_PRESENT`` is then a fact of the model:
    that identifier names a product the federated model carries.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    GLOBAL_ID_KEY: ClassVar[str] = "global_id"
    DEFEDERATED_KEY: ClassVar[str] = "defederated"
    STATE_CLEANED_KEY: ClassVar[str] = "state_cleaned_up"

    def evaluate(
        self,
        context: CliContextPort,
    ) -> GeometricProductDeleteProcessStatePort:
        project_path: Optional[Path] = self._path(context, self.CONTAINER_PATH_KEY)
        model_path: Optional[Path] = self._path(context, self.IFC_MODEL_PATH_KEY)
        if project_path is None or model_path is None:
            return GeometricProductDeleteProcessState.UNDEFINED

        project_path_value: str = str(project_path)
        model_path_value: str = str(model_path)
        reached_state: GeometricProductDeleteProcessStatePort = (
            GeometricProductDeleteProcessState.UNDEFINED
        )

        model_health_checks = (
            check_ifc_model_healthy,
            check_ifc_project_synced,
            check_geometric_representation_context_ready,
            check_spatial_structure_valid,
            check_object_placement_valid,
            check_shape_representation_context_valid,
            check_unit_defined,
        )
        for check in model_health_checks:
            if check(
                project_path=project_path_value,
                ifc_model_path=model_path_value,
            ) != 0:
                return reached_state

        reached_state = GeometricProductDeleteProcessState.IFC_MODEL_HEALTHY

        if not self._is_global_id_known(context):
            return reached_state

        reached_state = GeometricProductDeleteProcessState.GLOBAL_ID_KNOWN

        is_present: bool = self._is_global_id_present(context, model_path)
        is_defederated: bool = self._is_defederated_marker_true(context)

        if is_defederated or not is_present:
            if is_defederated:
                reached_state = (
                    GeometricProductDeleteProcessState.GEOMETRIC_PRODUCT_DEFEDERATED
                )
            else:
                return reached_state
        else:
            reached_state = GeometricProductDeleteProcessState.GLOBAL_ID_PRESENT

        if reached_state == GeometricProductDeleteProcessState.GLOBAL_ID_PRESENT:
            if (
                self._is_defederated_marker_true(context)
                or not self._is_global_id_present(context, model_path)
            ):
                reached_state = (
                    GeometricProductDeleteProcessState.GEOMETRIC_PRODUCT_DEFEDERATED
                )
            else:
                return reached_state

        if self._is_state_cleaned_up(context, project_path, model_path):
            return GeometricProductDeleteProcessState.STATE_CLEANED_UP

        return reached_state

    @classmethod
    def _is_global_id_known(cls, context: CliContextPort) -> bool:
        value: Any = context.get_parameter_value(cls.GLOBAL_ID_KEY)
        if not isinstance(value, str):
            return False

        identifier: str = value.strip()
        if not identifier:
            return False

        return True

    @classmethod
    def _is_global_id_present(
        cls,
        context: CliContextPort,
        model_path: Path,
    ) -> bool:
        import ifcopenshell

        global_id_value: Any = context.get_parameter_value(cls.GLOBAL_ID_KEY)
        if not isinstance(global_id_value, str) or not global_id_value.strip():
            return False

        identifier: str = global_id_value.strip()
        try:
            model: Any = ifcopenshell.open(str(model_path))
            model.by_guid(identifier)
        except Exception:
            return False

        return True

    @classmethod
    def _is_defederated_marker_true(cls, context: CliContextPort) -> bool:
        value: Any = context.get_parameter_value(cls.DEFEDERATED_KEY)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "sim"}
        return False

    @classmethod
    def _is_state_cleaned_up(
        cls,
        context: CliContextPort,
        container_path: Path,
        model_path: Path,
    ) -> bool:
        if context.has_parameter(cls.STATE_CLEANED_KEY):
            marker: Any = context.get_parameter_value(cls.STATE_CLEANED_KEY)
            if isinstance(marker, bool) and marker:
                return True

        global_id_value: Any = context.get_parameter_value(cls.GLOBAL_ID_KEY)
        if isinstance(global_id_value, str) and global_id_value.strip():
            directory: Path = GeometricProductState.root_of(
                container_path
            ) / global_id_value.strip()
            if directory.exists():
                return False

        marker_after = context.get_parameter_value(cls.STATE_CLEANED_KEY)
        return bool(marker_after)

    @staticmethod
    def _path(context: CliContextPort, key: str) -> Optional[Path]:
        value: Any = context.get_parameter_value(key)
        if not isinstance(value, str) or not value.strip():
            return None

        return Path(value).expanduser().resolve()


class GeometricProductDeleteStateTransitionHandler(
    GeometricProductDeleteStateTransitionHandlerPort
):
    """
    Drives one geometric-product deletion through its own machine.

    Each transition is one capability, resolved by the id the state
    declares and executed through the capability executor. The handler
    sequences them and nothing else. The last transition optionally
    drops the product's assembled state directory, so a recreated
    product with the same GlobalId does not find stale STEP files.
    """

    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim", "ontobdc")

    GLOBAL_ID_KEY: ClassVar[str] = "global_id"
    RUN_LOCAL_KEYS: ClassVar[Tuple[str, ...]] = (
        "defederated",
        "state_cleaned_up",
    )

    STATECHART_PACKAGE: ClassVar[str] = (
        "infobim.ifc.plugin.machine.geometric_product_delete"
    )
    STATECHART_FILE: ClassVar[str] = "standard_geometric_product_delete.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "GeometricProductDeleteProcessStatePort"

    CAPABILITY_IDS: ClassVar[Dict[GeometricProductDeleteProcessStatePort, str]] = {
        GeometricProductDeleteProcessState.IFC_MODEL_HEALTHY: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "delete_ifc_model_healthy"
        ),
        GeometricProductDeleteProcessState.GLOBAL_ID_KNOWN: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "delete_global_id_known"
        ),
        GeometricProductDeleteProcessState.GLOBAL_ID_PRESENT: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "delete_global_id_present"
        ),
        GeometricProductDeleteProcessState.GEOMETRIC_PRODUCT_DEFEDERATED: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometric_product_defederated"
        ),
        GeometricProductDeleteProcessState.STATE_CLEANED_UP: (
            "org.infobim.ifc.plugin.capability.transformation.target."
            "delete_state_cleaned_up"
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
        self._state_evaluator: GeometricProductDeleteStateEvaluatorPort = (
            GeometricProductDeleteStateEvaluatorAdapter()
        )
        self._active_state: Optional[GeometricProductDeleteProcessStatePort] = None
        self._observed_state: Optional[GeometricProductDeleteProcessStatePort] = None
        self._state_names: Optional[List[str]] = None

    @property
    def current_state(self) -> GeometricProductDeleteProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> GeometricProductDeleteProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(
        self,
        to_state: GeometricProductDeleteProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: GeometricProductDeleteProcessStatePort,
    ) -> None:
        if self._is_reached(to_state):
            return

        self._logger.log_info(
            f"IFC geometric product delete transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )

        if to_state == GeometricProductDeleteProcessState.STATE_CLEANED_UP:
            self._cleanup_geometric_product_state()
            self._forget_observed_state()
            return

        capability_id: Optional[str] = self.CAPABILITY_IDS.get(to_state)
        if capability_id is None:
            raise ValueError(
                f"IFC geometric product delete capability id not declared "
                f"for state: {to_state.value}"
            )

        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"IFC geometric product delete capability not found for "
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
        from_state: GeometricProductDeleteProcessStatePort,
        to_state: GeometricProductDeleteProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._is_reached(to_state)

    def execute(self) -> CommandResponse:
        self._forget_run_local_references()
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=GeometricProductDeleteProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._statechart_file_path(),
        )
        visited_states: List[str] = worker.work()
        return self._final_response(visited_states)

    def _cleanup_geometric_product_state(self) -> None:
        global_id_value: Any = self._context.get_parameter_value(self.GLOBAL_ID_KEY)
        if not isinstance(global_id_value, str) or not global_id_value.strip():
            raise IfcCreationError(
                "The GlobalId of the product whose state should be cleaned up "
                "is not bound in the command context."
            )

        directory: Path = GeometricProductState.root_of(
            self._container_path
        ) / global_id_value.strip()
        if directory.exists():
            shutil.rmtree(directory)

        self._context.set_parameter_value(
            GeometricProductDeleteStateEvaluatorAdapter.STATE_CLEANED_KEY, True
        )

    def bind_active_state(
        self, state: GeometricProductDeleteProcessStatePort
    ) -> None:
        self._active_state = state
        self._forget_observed_state()

    @classmethod
    def statechart_path(cls) -> Path:
        return StatechartLocator.locate(
            cls.STATECHART_PACKAGE,
            cls.STATECHART_FILE,
        )

    def _forget_observed_state(self) -> None:
        self._observed_state = None

    def _forget_run_local_references(self) -> None:
        for key in self.RUN_LOCAL_KEYS:
            self._context.delete_parameter(key)

    def _is_reached(self, to_state: GeometricProductDeleteProcessStatePort) -> bool:
        state_names: List[str] = self._state_sequence()
        observed_name: str = self.observed_state.value.strip("_")
        target_name: str = to_state.value.strip("_")
        if observed_name not in state_names:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the "
                f"geometric product delete statechart."
            )

        if target_name not in state_names:
            raise ValueError(
                f"Target state '{target_name}' is absent from the geometric "
                f"product delete statechart."
            )

        return state_names.index(observed_name) >= state_names.index(target_name)

    def _state_sequence(self) -> List[str]:
        if self._state_names is None:
            statechart_data: Any = yaml.safe_load(
                self._statechart_file_path().read_text(encoding="utf-8")
            ) or {}
            if not isinstance(statechart_data, dict):
                raise TypeError(
                    "The geometric product delete statechart must be a mapping."
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
        global_id_value: Any = self._context.get_parameter_value(self.GLOBAL_ID_KEY)
        global_id: str = (
            str(global_id_value) if global_id_value is not None else ""
        )

        return CommandResponse(
            title="IFC Geometric Product Deleted",
            description=(
                "The IFC geometric product ran through its deletion state "
                "machine."
            ),
            content={
                "container_path": str(self._container_path),
                "global_id": global_id,
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )
