from typing import Any, ClassVar, Dict, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.federation import IfcProductFederator
from infobim.ifc.domain.port.federation import IfcProductFederatorPort
from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)


class GeometricProductFederatedCapability(TransactionCapability):
    """
    Brings the product this run assembled into the project's IFC model.

    Everything before this state happens in the project's own workspace,
    where an unfinished product harms nobody. This is where it becomes
    part of what the project federates, so it arrives whole: the element,
    its placement related to the storey that holds it, its representation
    measured in the model's own Body context, and the containment that
    makes it part of the building rather than a thing that happens to sit
    in the same file.

    A product already federated under the same identity is replaced,
    together with what only it owned.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometric_product_federated"
        ),
        version="0.1.0",
        name="Geometric Product Federated",
        description="Bring the assembled IFC product into the project's model.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometric-product", "geometric_product_federated"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": "The InfoBIM project the product belongs to.",
                },
                "title": {
                    "type": "string",
                    "required": True,
                    "description": "The title of the product being federated.",
                },
                "ifc_model_path": {
                    "type": "string",
                    "required": True,
                    "description": "The IFC model the product is federated into.",
                },
            },
        },
        log_message={
            "info": {
                "en": "The product is part of the project's federated IFC model.",
            },
            "debug_entry": {
                "en": "Federating the assembled product into the IFC model.",
            },
        },
    )

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    TITLE_KEY: ClassVar[str] = "title"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    FEDERATED_PRODUCT_KEY: ClassVar[str] = "federated_product"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"

    def __init__(self, federator: Optional[IfcProductFederatorPort] = None) -> None:
        self._federator: IfcProductFederatorPort = federator or IfcProductFederator()

    def label(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_FEDERATED.label(
            lang
        )

    def description(self, lang: str = "en") -> str:
        return (
            GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_FEDERATED.description(
                lang
            )
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Federate the assembled product and bind the identity it carries.
        """
        global_id: str = self._federator.federate(
            self._container_path(context),
            self._title(context),
            self._model_path(context),
        )
        context.set_parameter_value(self.FEDERATED_PRODUCT_KEY, global_id)

        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_FEDERATED
            ),
            self.FEDERATED_PRODUCT_KEY: global_id,
        }

    @classmethod
    def _container_path(cls, context: CliContextPort) -> Path:
        value: Any = context.get_parameter_value(cls.CONTAINER_PATH_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The InfoBIM project is missing from the command context, so "
                "the product being federated cannot be found."
            )

        return Path(value).expanduser().resolve()

    @classmethod
    def _title(cls, context: CliContextPort) -> str:
        value: Any = context.get_parameter_value(cls.TITLE_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The product title is missing from the command context, so "
                "the product being federated cannot be found."
            )

        return value.strip()

    @classmethod
    def _model_path(cls, context: CliContextPort) -> Path:
        value: Any = context.get_parameter_value(cls.IFC_MODEL_PATH_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The IFC model is missing from the command context, so the "
                "product has nothing to be federated into."
            )

        model_path: Path = Path(value).expanduser().resolve()
        if not model_path.is_file():
            raise IfcCreationError(
                f"The IFC model the product is federated into does not "
                f"exist: {model_path}."
            )

        return model_path
