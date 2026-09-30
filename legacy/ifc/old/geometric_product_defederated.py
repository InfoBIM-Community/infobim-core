from typing import Any, ClassVar, Dict, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.federation import IfcProductFederator
from infobim.ifc.domain.port.federation import IfcProductFederatorPort
from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.plugin.machine.geometric_product_delete.state import (
    GeometricProductDeleteProcessState,
)


class GeometricProductDefederatedCapability(TransactionCapability):
    """
    Remove the element the GlobalId names from the federated model.

    Removal uses the same graph-traversal the federation flow uses to
    replace an existing product with a newer copy: the element is dropped
    from every spatial containment, then removed together with every
    entity only it references. Representation contexts, placement chains
    above the product's own, and the storey it was placed in are all
    shared by construction and are therefore preserved.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometric_product_defederated"
        ),
        version="0.1.0",
        name="Geometric Product Defederated",
        description=(
            "Remove an IFC product (and everything only it owns) from the "
            "project's federated model."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "infobim",
            "ifc",
            "geometric-product-delete",
            "geometric_product_defederated",
        ],
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
                    "description": (
                        "The IFC model the product to be removed lives in."
                    ),
                },
                "global_id": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "The GlobalId of the IFC product to remove."
                    ),
                },
            },
        },
        log_message={
            "info": {
                "en": "The IFC product is no longer part of the federated model.",
            },
            "debug_entry": {
                "en": "Removing the IFC product and its uniquely owned entities.",
            },
        },
    )

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    GLOBAL_ID_KEY: ClassVar[str] = "global_id"
    DEFEDERATED_KEY: ClassVar[str] = "defederated"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    REMOVED_IFC_CLASS_KEY: ClassVar[str] = "removed_ifc_class"

    def __init__(
        self,
        federator: Optional[IfcProductFederatorPort] = None,
    ) -> None:
        self._federator: IfcProductFederatorPort = (
            federator or IfcProductFederator()
        )

    def label(self, lang: str = "en") -> str:
        return (
            GeometricProductDeleteProcessState.GEOMETRIC_PRODUCT_DEFEDERATED.label(
                lang
            )
        )

    def description(self, lang: str = "en") -> str:
        return GeometricProductDeleteProcessState.GEOMETRIC_PRODUCT_DEFEDERATED.description(
            lang
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        _ = Path(
            RequiredParameter.of(context, self.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
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
                "The GlobalId of the product to defederate is empty."
            )

        removed_class: Optional[str] = self._class_before_removal(
            model_path, identifier
        )
        removed: bool = self._federator.defederate(model_path, identifier)
        context.set_parameter_value(self.DEFEDERATED_KEY, removed)

        if removed and removed_class is not None:
            context.set_parameter_value(self.REMOVED_IFC_CLASS_KEY, removed_class)

        if not removed:
            raise IfcCreationError(
                f"The IFC model {model_path} does not carry a product with "
                f"GlobalId '{identifier}', so nothing could be removed."
            )

        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductDeleteProcessState.GEOMETRIC_PRODUCT_DEFEDERATED
            ),
            self.GLOBAL_ID_KEY: identifier,
            self.DEFEDERATED_KEY: True,
            self.REMOVED_IFC_CLASS_KEY: removed_class,
        }

    @classmethod
    def _class_before_removal(
        cls,
        model_path: Path,
        global_id: str,
    ) -> Optional[str]:
        """
        Return the IFC class of the element before it gets removed.

        Reading it first lets the capability surface what was actually
        removed while the federator only owns the graph mutation.
        """
        import ifcopenshell

        try:
            model: Any = ifcopenshell.open(str(model_path))
            element: Any = model.by_guid(global_id)
        except Exception:
            return None

        ifc_class: Any = getattr(element, "is_a", None)
        if callable(ifc_class):
            try:
                return str(ifc_class())
            except Exception:
                return None
        if isinstance(ifc_class, str):
            return ifc_class
        return None
