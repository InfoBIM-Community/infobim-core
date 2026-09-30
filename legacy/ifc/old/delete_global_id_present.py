from pathlib import Path
from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.plugin.machine.geometric_product_delete.state import (
    GeometricProductDeleteProcessState,
)


class DeleteGlobalIdPresentCapability(TransactionCapability):
    """
    Verify that the federated model carries a product under the GlobalId.

    A presence-verification state sits deliberately between the run-local
    shape validation and the actual removal. The sequence `check -> raise`
    is the check half of the `check -> hotfix -> check` pattern the
    state machine uses; the hotfix for "GlobalId not present" is a user
    decision — a different identifier — which this capability does not
    invent.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "delete_global_id_present"
        ),
        version="0.1.0",
        name="Delete - GlobalId Present",
        description=(
            "Confirm that the IFC model carries a product with the "
            "requested GlobalId."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "infobim",
            "ifc",
            "geometric-product-delete",
            "delete_global_id_present",
        ],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_model_path": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "The IFC model that should carry the product."
                    ),
                },
                "global_id": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "The GlobalId to look up in the model."
                    ),
                },
            },
        },
        log_message={
            "info": {
                "en": "The requested GlobalId names a product in the model.",
            },
            "debug_entry": {
                "en": "Verifying the GlobalId names a product in the federated model.",
            },
        },
    )

    GLOBAL_ID_KEY: ClassVar[str] = "global_id"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    ELEMENT_IFC_CLASS_KEY: ClassVar[str] = "element_ifc_class"

    def label(self, lang: str = "en") -> str:
        return GeometricProductDeleteProcessState.GLOBAL_ID_PRESENT.label(lang)

    def description(self, lang: str = "en") -> str:
        return (
            GeometricProductDeleteProcessState.GLOBAL_ID_PRESENT.description(lang)
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ifcopenshell

        model_path: Path = Path(
            RequiredParameter.of(context, self.IFC_MODEL_PATH_KEY)
        ).expanduser().resolve()
        global_id: str = RequiredParameter.of(context, self.GLOBAL_ID_KEY)

        if not model_path.is_file():
            raise IfcCreationError(
                f"The IFC model that should carry the product does not "
                f"exist: {model_path}."
            )

        identifier: str = global_id.strip()
        if not identifier:
            raise IfcCreationError(
                "The GlobalId to look up is empty; no presence can be "
                "verified."
            )

        try:
            model: Any = ifcopenshell.open(str(model_path))
            element: Any = model.by_guid(identifier)
        except Exception as error:
            raise IfcCreationError(
                f"Could not verify whether the federated model {model_path} "
                f"carries GlobalId '{identifier}' — {error}."
            ) from error

        ifc_class: str = getattr(element, "is_a", lambda: element.__class__.__name__)()
        context.set_parameter_value(self.ELEMENT_IFC_CLASS_KEY, ifc_class)
        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductDeleteProcessState.GLOBAL_ID_PRESENT
            ),
            self.GLOBAL_ID_KEY: identifier,
            self.ELEMENT_IFC_CLASS_KEY: ifc_class,
        }
