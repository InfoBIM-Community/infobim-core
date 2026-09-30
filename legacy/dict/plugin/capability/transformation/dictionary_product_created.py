from typing import Any, ClassVar, Dict, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.product import IfcProductAssembler
from infobim.ifc.domain.port.product import IfcProductAssemblerPort
from infobim.dict.domain.model.definition import DictionaryEntry, EntityDefinition
from infobim.dict.domain.exception.dictionary import (
    DictionaryDefinitionInvalidError,
)
from infobim.dict.plugin.machine.dictionary_entity_create.state import (
    DictionaryEntityContextKeys,
    DictionaryEntityCreateProcessState,
)


class DictionaryProductCreatedCapability(TransactionCapability):
    """
    Creates the element the dictionary defines, carrying its geometry.

    What class the element is, and what predefined type of that class, is
    the dictionary's answer and not this run's: the entry says the
    element is an ``IfcSanitaryTerminal`` restricted to ``TOILETPAN``,
    and this creates exactly that. Nothing here asks a chain which
    capability answers for the class, the way the IFC creation flow does
    when a caller names one — that chain exists so each class can fill in
    what its own class declares, and here the entry has already filled it
    in. A class this runtime's schema does not declare fails as the class
    it was: an element created as something else would be an element
    nobody defined.

    The element is written into the project's state, beside the geometry
    it carries, under the identity derived for it. Bringing it into the
    model the project federates is the state after this one, and it is
    the same state it is for any other product — by this point an element
    defined from a dictionary and one created by a command are the same
    kind of thing, which is why they are federated by the same
    capability.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.dict.plugin.capability.transformation.target."
            "dictionary_product_created"
        ),
        version="0.1.0",
        name="Dictionary Product Created",
        description=(
            "Create the IFC element the dictionary entry defines, carrying "
            "the geometry assembled for it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "dict", "dictionary", "dictionary_product_created"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": "The InfoBIM project the element belongs to.",
                },
                "title": {
                    "type": "string",
                    "required": True,
                    "description": "The title the element carries as its name.",
                },
                # Declared without a JSON type on purpose: see the note
                # on the same input in the geometry state's capability.
                "dictionary_definition": {
                    "required": True,
                    "description": (
                        "The entry this run read, which says what the element "
                        "is."
                    ),
                },
            },
            "required": ["container_path", "title", "dictionary_definition"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "geometric_product": {"type": "string"},
            },
            "required": ["geometric_product"],
        },
        log_message={
            "info": {
                "en": "The IFC element the dictionary defines exists.",
            },
            "debug_entry": {
                "en": "Creating the IFC element the dictionary entry defines.",
            },
        },
    )

    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    GEOMETRIC_PRODUCT_KEY: ClassVar[str] = "geometric_product"
    IFC_CLASS_KEY: ClassVar[str] = "ifc_class"
    PREDEFINED_TYPE_ATTRIBUTE: ClassVar[str] = "PredefinedType"

    def __init__(self, assembler: Optional[IfcProductAssemblerPort] = None) -> None:
        self._assembler: IfcProductAssemblerPort = assembler or IfcProductAssembler()

    def label(self, lang: str = "en") -> str:
        return DictionaryEntityCreateProcessState.GEOMETRIC_PRODUCT_CREATED.label(
            lang
        )

    def description(self, lang: str = "en") -> str:
        return (
            DictionaryEntityCreateProcessState.GEOMETRIC_PRODUCT_CREATED.description(
                lang
            )
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Create the element as the entry defines it, and bind its identity.
        """
        entry: Any = context.get_parameter_value(
            DictionaryEntityContextKeys.DICTIONARY_DEFINITION_KEY
        )
        if not isinstance(entry, DictionaryEntry):
            raise DictionaryDefinitionInvalidError(
                "No dictionary entry was read for this run, so there is "
                "nothing saying what the element is."
            )

        element: EntityDefinition = entry.element_definition()
        ifc_class: Optional[str] = element.ifc_class
        if ifc_class is None:
            raise DictionaryDefinitionInvalidError(
                f"The dictionary entry at {entry.source_uri} defines "
                f"{element.label} as no IFC class, so no IFC element can be "
                f"created from it."
            )

        container_path: Path = Path(
            self._stated(context, DictionaryEntityContextKeys.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
        global_id: str = self._assembler.assemble(
            container_path,
            self._stated(context, DictionaryEntityContextKeys.TITLE_KEY),
            ifc_class,
            self._attributes(element),
        )
        context.set_parameter_value(self.GEOMETRIC_PRODUCT_KEY, global_id)

        return {
            self.RESULTING_STATE_KEY: (
                DictionaryEntityCreateProcessState.GEOMETRIC_PRODUCT_CREATED
            ),
            self.GEOMETRIC_PRODUCT_KEY: global_id,
            self.IFC_CLASS_KEY: ifc_class,
        }

    @classmethod
    def _attributes(cls, element: EntityDefinition) -> Dict[str, Any]:
        """
        Return the attributes the entry fills in for the element's class.

        A predefined type nobody stated is not written at all: leaving the
        attribute out is the element saying nothing about which kind of
        its class it is, while writing something in its place would be
        this capability deciding it.
        """
        if element.predefined_type is None:
            return {}

        return {cls.PREDEFINED_TYPE_ATTRIBUTE: element.predefined_type}

    @staticmethod
    def _stated(context: CliContextPort, key: str) -> str:
        """
        Return what the run states under a key, or fail saying it states none.
        """
        value: Any = context.get_parameter_value(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"The dictionary run states no '{key}', which this state "
                f"cannot be reached without."
            )

        return value.strip()
