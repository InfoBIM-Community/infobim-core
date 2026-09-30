from typing import Any, ClassVar, Dict, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.product import IfcProductAssembler
from infobim.ifc.domain.port.product import (
    IfcProductAssemblerPort,
    IfcProductCreateResponsibilityPort,
)
from infobim.ifc.domain.exception.creation import IfcCreationError


class IfcFootingElementCreationCapability(
    TransformationCapability,
    IfcProductCreateResponsibilityPort,
):
    """
    Creates the product of a run as an ``IfcFooting``.

    Mirrors ``IfcPipeSegmentElementCreationCapability``: this capability
    answers only for its own class. The predefined type is the one the run
    states under ``ifc_predefined_type``; a run that states none picks
    ``NOTDEFINED`` rather than a wrong one.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.transformation.product.ifc_footing",
        version="0.1.0",
        name="IfcFooting Creation",
        description=(
            "Create the product of a run as an IfcFooting carrying the geometry "
            "assembled for it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "product", "footing"],
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
            "info": {"en": "The product was created as an IfcFooting."},
            "debug_entry": {"en": "Creating the product as an IfcFooting."},
        },
    )

    IFC_CLASS: ClassVar[str] = "IfcFooting"
    NOT_DEFINED_PREDEFINED_TYPE: ClassVar[str] = "NOTDEFINED"

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    TITLE_KEY: ClassVar[str] = "title"
    IFC_CLASS_KEY: ClassVar[str] = "ifc_class"
    PREDEFINED_TYPE_KEY: ClassVar[str] = "ifc_predefined_type"
    GEOMETRIC_PRODUCT_KEY: ClassVar[str] = "geometric_product"

    def __init__(self, assembler: Optional[IfcProductAssemblerPort] = None) -> None:
        self._assembler: IfcProductAssemblerPort = assembler or IfcProductAssembler()

    def label(self, lang: str = "en") -> str:
        return "IfcFooting Creation"

    def description(self, lang: str = "en") -> str:
        return "Creates the product as an IfcFooting carrying the geometry assembled for it."

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
        global_id: str = self._assembler.assemble(
            self._container_path(context),
            self._title(context),
            self.IFC_CLASS,
            {"PredefinedType": self._predefined_type(context)},
        )
        context.set_parameter_value(self.GEOMETRIC_PRODUCT_KEY, global_id)

        return {
            self.GEOMETRIC_PRODUCT_KEY: global_id,
            self.IFC_CLASS_KEY: self.IFC_CLASS,
        }

    @classmethod
    def _predefined_type(cls, context: CliContextPort) -> str:
        value: Any = context.get_parameter_value(cls.PREDEFINED_TYPE_KEY)
        if value is None:
            return cls.NOT_DEFINED_PREDEFINED_TYPE
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                f"The IfcFooting predefined type {value!r} is not a type name."
            )

        return value.strip()

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
