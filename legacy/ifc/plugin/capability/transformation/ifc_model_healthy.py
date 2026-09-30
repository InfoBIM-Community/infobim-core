from typing import Any, ClassVar, Dict
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import IfcModelUnhealthyError
from infobim.ifc.plugin.check.is_ifc_model_healthy.check import (
    main as check_ifc_model_healthy,
)
from infobim.ifc.plugin.check.is_ifc_project_synced.check import (
    main as check_ifc_project_synced,
)
from infobim.ifc.plugin.check.is_ifc_project_synced.hotfix import (
    main as hotfix_ifc_project_synced,
)
from infobim.ifc.plugin.check.is_geometric_representation_context_ready.check import (
    main as check_geometric_representation_context_ready,
)
from infobim.ifc.plugin.check.is_geometric_representation_context_ready.hotfix import (
    main as hotfix_geometric_representation_context_ready,
)
from infobim.ifc.plugin.check.is_spatial_structure_valid.check import (
    main as check_spatial_structure_valid,
)
from infobim.ifc.plugin.check.is_spatial_structure_valid.hotfix import (
    main as hotfix_spatial_structure_valid,
)
from infobim.ifc.plugin.check.is_object_placement_valid.check import (
    main as check_object_placement_valid,
)
from infobim.ifc.plugin.check.is_object_placement_valid.hotfix import (
    main as hotfix_object_placement_valid,
)
from infobim.ifc.plugin.check.is_shape_representation_context_valid.check import (
    main as check_shape_representation_context_valid,
)
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)


class IfcModelHealthyCapability(TransactionCapability):
    """
    Bring the target IFC model to the complete IFC_MODEL_HEALTHY state.

    Each health concern remains owned by one standalone check/hotfix package.
    This capability only orchestrates them in dependency order. Checks never
    call other checks, and hotfixes never delegate verification to a sibling.

    The target itself must already be a usable model of this project: it is
    declared by the project's RO-Crate, writable, readable as STEP, and uses
    the schema family the project declares. Those conditions are not repaired
    here because choosing another file or another schema is not deterministic.

    Once that precondition holds, deterministic model concerns are repaired in
    order: IfcProject synchronization, geometric representation context,
    spatial structure, and object placement. Existing shape representations
    must then reference valid project contexts; that concern is checked but is
    not rewritten because changing an existing representation's context would
    discard modelling intent.

    Units deliberately remain outside this capability. UNIT_DEFINED is the
    next machine state and owns that concern.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "ifc_model_healthy"
        ),
        version="0.1.0",
        name="IFC Model Healthy",
        description="Ensure the target IFC model is healthy for geometric work.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometric-product", "ifc_model_healthy"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": "The InfoBIM project the model belongs to.",
                },
                "ifc_model_path": {
                    "type": "string",
                    "required": True,
                    "description": "The IFC model this state is about.",
                },
            },
        },
        log_message={
            "info": {
                "en": "The target IFC model is healthy for geometric work.",
            },
            "debug_entry": {
                "en": "Repairing and validating IFC model health.",
            },
        },
    )

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    PATH_KEY: ClassVar[str] = "path"

    def label(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.IFC_MODEL_HEALTHY.label(lang)

    def description(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.IFC_MODEL_HEALTHY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
        model_path: Path = Path(
            RequiredParameter.of(context, self.IFC_MODEL_PATH_KEY)
        ).expanduser().resolve()

        project_path_value: str = str(project_path)
        model_path_value: str = str(model_path)

        if check_ifc_model_healthy(
            project_path=project_path_value,
            ifc_model_path=model_path_value,
        ) != 0:
            raise IfcModelUnhealthyError(
                f"The IFC model {model_path} is not a usable target of the "
                f"project at {project_path}: it is not declared by the project, "
                f"is not writable/readable, or its schema family disagrees "
                f"with the project declaration."
            )

        self._ensure_repairable_concern(
            concern="IfcProject synchronization",
            project_path=project_path_value,
            model_path=model_path_value,
            check=check_ifc_project_synced,
            hotfix=hotfix_ifc_project_synced,
        )
        self._ensure_repairable_concern(
            concern="geometric representation context",
            project_path=project_path_value,
            model_path=model_path_value,
            check=check_geometric_representation_context_ready,
            hotfix=hotfix_geometric_representation_context_ready,
        )
        self._ensure_repairable_concern(
            concern="spatial structure",
            project_path=project_path_value,
            model_path=model_path_value,
            check=check_spatial_structure_valid,
            hotfix=hotfix_spatial_structure_valid,
        )
        self._ensure_repairable_concern(
            concern="object placement",
            project_path=project_path_value,
            model_path=model_path_value,
            check=check_object_placement_valid,
            hotfix=hotfix_object_placement_valid,
        )

        if check_shape_representation_context_valid(
            project_path=project_path_value,
            ifc_model_path=model_path_value,
        ) != 0:
            raise IfcModelUnhealthyError(
                f"The IFC model {model_path} contains an invalid shape "
                f"representation context. Existing representation contexts "
                f"are not rewritten automatically."
            )

        # Re-read the non-repairable target contract after all model writes.
        if check_ifc_model_healthy(
            project_path=project_path_value,
            ifc_model_path=model_path_value,
        ) != 0:
            raise IfcModelUnhealthyError(
                f"The IFC model {model_path} stopped satisfying the target "
                f"model contract while its health concerns were repaired."
            )

        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductCreateProcessState.IFC_MODEL_HEALTHY
            ),
            self.PATH_KEY: model_path_value,
        }

    @staticmethod
    def _ensure_repairable_concern(
        *,
        concern: str,
        project_path: str,
        model_path: str,
        check: Any,
        hotfix: Any,
    ) -> None:
        if check(
            project_path=project_path,
            ifc_model_path=model_path,
        ) == 0:
            return

        if hotfix(
            project_path=project_path,
            ifc_model_path=model_path,
        ) != 0:
            raise IfcModelUnhealthyError(
                f"The IFC model health concern '{concern}' could not be "
                f"repaired deterministically for {model_path}."
            )

        if check(
            project_path=project_path,
            ifc_model_path=model_path,
        ) != 0:
            raise IfcModelUnhealthyError(
                f"The IFC model health concern '{concern}' is still invalid "
                f"after its hotfix for {model_path}."
            )
