from pathlib import Path
from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.plugin.check.is_unit_defined.check import (
    main as check_unit_defined,
)
from infobim.ifc.plugin.check.is_unit_defined.hotfix import (
    main as hotfix_unit_defined,
)
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)


class UnitDefinedCapability(TransactionCapability):
    """
    Bring the target IFC model to UNIT_DEFINED.

    UNIT_DEFINED is the complete project-wide physical unit context, not only
    length. The standalone check requires every standard named physical unit
    type and every standard derived unit type to be present exactly once with
    dimensionally valid definitions.

    Existing valid project units are authoritative and are not converted. Any
    missing unit is created by the standalone hotfix in coherent SI at 10^0.
    The deliberate exception is plane angle, which is bootstrapped as degree;
    angle-bearing derived units therefore use degree as well. Mass is kilogram
    (IfcSIUnit GRAM with KILO prefix), as required by the SI base system.

    Ambiguous or dimensionally invalid existing declarations are not silently
    replaced. The check and hotfix remain standalone scripts; this capability
    only orchestrates and verifies their result.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "unit_defined"
        ),
        version="0.1.0",
        name="Unit Defined",
        description=(
            "Ensure the target IFC model has a complete physical unit "
            "assignment for named and derived quantities."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometric-product", "unit_defined"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_model_path": {
                    "type": "string",
                    "required": True,
                    "description": "The IFC model this state is about.",
                },
            },
        },
        log_message={
            "info": {
                "en": "The target IFC model states its complete physical unit context.",
            },
            "debug_entry": {
                "en": "Ensuring all standard IFC physical units are defined.",
            },
        },
    )

    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    PATH_KEY: ClassVar[str] = "path"

    def label(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.UNIT_DEFINED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.UNIT_DEFINED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        model_path: Path = Path(
            RequiredParameter.of(context, self.IFC_MODEL_PATH_KEY)
        ).expanduser().resolve()
        model_path_value: str = str(model_path)

        if check_unit_defined(ifc_model_path=model_path_value) != 0:
            if hotfix_unit_defined(ifc_model_path=model_path_value) != 0:
                raise RuntimeError(
                    f"Failed to complete the IFC physical unit assignment for "
                    f"{model_path}."
                )

        if check_unit_defined(ifc_model_path=model_path_value) != 0:
            raise RuntimeError(
                f"The IFC model {model_path} still does not have a complete, "
                f"dimensionally valid physical unit assignment after the "
                f"UNIT_DEFINED hotfix."
            )

        return {
            self.RESULTING_STATE_KEY: GeometricProductCreateProcessState.UNIT_DEFINED,
            self.PATH_KEY: model_path_value,
        }
