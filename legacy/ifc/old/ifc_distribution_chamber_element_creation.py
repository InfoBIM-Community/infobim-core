from typing import Any, ClassVar, Dict, Optional
from pathlib import Path
import math

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.product import IfcProductAssembler
from infobim.ifc.domain.port.product import (
    IfcProductAssemblerPort,
    IfcProductCreateResponsibilityPort,
)
from infobim.ifc.domain.exception.creation import IfcCreationError


class IfcDistributionChamberElementCreationCapability(
    TransformationCapability,
    IfcProductCreateResponsibilityPort,
):
    """
    Creates the product of a run as an ``IfcDistributionChamberElement``.

    The class is what this capability answers for, and what the class
    declares beyond a name and a representation is what it fills: a
    distribution chamber says which kind of chamber it is, and a run that
    does not say picks none of them rather than a wrong one, which is
    what ``NOTDEFINED`` is for in the schema.

    Nothing here knows the chain it belongs to, and the state that
    creates the product knows no class by name: the chain asks who can
    handle the class the run named, and this answers for one of them.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.product."
            "ifc_distribution_chamber_element"
        ),
        version="0.1.0",
        name="IfcDistributionChamberElement Creation",
        description=(
            "Create the product of a run as an IfcDistributionChamberElement "
            "carrying the geometry assembled for it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "product", "distribution-chamber"],
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
                    "description": "The title of the product being assembled.",
                },
            },
        },
        log_message={
            "info": {
                "en": "The product was created as an IfcDistributionChamberElement.",
            },
            "debug_entry": {
                "en": "Creating the product as an IfcDistributionChamberElement.",
            },
        },
    )

    IFC_CLASS: ClassVar[str] = "IfcDistributionChamberElement"
    PREDEFINED_TYPE: ClassVar[str] = "NOTDEFINED"

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    TITLE_KEY: ClassVar[str] = "title"
    IFC_CLASS_KEY: ClassVar[str] = "ifc_class"
    GEOMETRIC_PRODUCT_KEY: ClassVar[str] = "geometric_product"

    def __init__(self, assembler: Optional[IfcProductAssemblerPort] = None) -> None:
        self._assembler: IfcProductAssemblerPort = assembler or IfcProductAssembler()

    def label(self, lang: str = "en") -> str:
        return "IfcDistributionChamberElement Creation"

    def description(self, lang: str = "en") -> str:
        return (
            "Creates the product as an IfcDistributionChamberElement carrying "
            "the geometry assembled for it."
        )

    def can_handle(
        self,
        context: CliContextPort,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Answer for the one class this capability creates.
        """
        if not isinstance(extra_data, dict):
            return False

        requested: Any = extra_data.get(self.IFC_CLASS_KEY)

        return (
            isinstance(requested, str)
            and requested.strip().lower() == self.IFC_CLASS.lower()
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Create the element and bind the identity it carries.
        """
        position: Optional[Dict[str, float]] = self._position(context)
        global_id: str = self._assembler.assemble(
            self._container_path(context),
            self._title(context),
            self.IFC_CLASS,
            {"PredefinedType": self.PREDEFINED_TYPE},
            position=position,
        )
        context.set_parameter_value(self.GEOMETRIC_PRODUCT_KEY, global_id)

        return {
            self.GEOMETRIC_PRODUCT_KEY: global_id,
            self.IFC_CLASS_KEY: self.IFC_CLASS,
        }

    @classmethod
    def _position(
        cls,
        context: CliContextPort,
    ) -> Optional[Dict[str, float]]:
        """
        Return the element placement this invocation stated, or None.
        """
        position_key: str = "position"
        if not context.has_parameter(position_key):
            return None

        value: Any = context.get_parameter_value(position_key)
        if not isinstance(value, dict):
            return None

        position: Dict[str, float] = {}
        for axis in ("x", "y", "z"):
            raw: Any = value.get(axis)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                return None
            numeric: float = float(raw)
            if not math.isfinite(numeric):
                return None
            position[axis] = numeric

        if len(position) != 3:
            return None

        return position

    @classmethod
    def _container_path(cls, context: CliContextPort) -> Path:
        value: Any = context.get_parameter_value(cls.CONTAINER_PATH_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The InfoBIM project is missing from the command context, so "
                "the product has nowhere to be created."
            )

        return Path(value).expanduser().resolve()

    @classmethod
    def _title(cls, context: CliContextPort) -> str:
        value: Any = context.get_parameter_value(cls.TITLE_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The product title is missing from the command context, so "
                "the product cannot be named."
            )

        return value.strip()
