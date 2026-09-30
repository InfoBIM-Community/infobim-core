import math
from typing import Any, ClassVar, Dict, List, Optional, Set
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
from infobim.dict.plugin.parameter.kind import KindStrategy


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

        element: EntityDefinition = entry.element_definition(
            self._aeco_class_hint(context)
        )
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
        position: Optional[Dict[str, float]] = self._position(context)
        global_id: str = self._assembler.assemble(
            container_path,
            self._stated(context, DictionaryEntityContextKeys.TITLE_KEY),
            ifc_class,
            self._attributes(element),
            position=position,
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

    @classmethod
    def _position(
        cls,
        context: CliContextPort,
    ) -> Optional[Dict[str, float]]:
        """
        Return the element placement this invocation stated, or None.

        The position is written as a dictionary of three finite floats
        (``x``, ``y``, ``z``) by ``PositionDefinedCapability``. If the
        invocation did not state a position (for example, because the
        dictionary machine reached this state through a path that did
        not require one) returning None tells the assembler to place
        the element at the origin, which keeps the contract of older
        callers that never passed a placement.
        """
        if not context.has_parameter(DictionaryEntityContextKeys.POSITION_KEY):
            return None

        value: Any = context.get_parameter_value(
            DictionaryEntityContextKeys.POSITION_KEY
        )
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
    def _aeco_class_hint(cls, context: CliContextPort) -> Optional[List[str]]:
        """
        Return the AECO domain class clique the --kind strategy resolved.

        The narrowing used by ``GEOMETRY_DEFINED`` must be repeated here,
        because this state assembles the same element the geometry state
        described the shape of. Picking the wrong representation out of
        an entry that groups several IFC classes would write an IFC
        product with the wrong predefined type, leaving the assembled
        geometry mismatched against its element.

        Because the shared context persists this key as a single scalar
        URI through RDF, the equivalent-class clique is reconstructed
        from the kind graph via ``KindStrategy.expand_equivalent_clique``
        so the same semantic concept is matched on both sides of the
        domain→representation link.
        """
        if not context.has_parameter(
            DictionaryEntityContextKeys.AECO_CLASS_URI_KEY
        ):
            return None
        value: Any = context.get_parameter_value(
            DictionaryEntityContextKeys.AECO_CLASS_URI_KEY
        )
        if isinstance(value, list):
            items: List[str] = []
            item: Any
            for item in value:
                if not isinstance(item, str):
                    continue
                s: str = item.strip()
                if s:
                    items.append(s)
            if not items:
                return None
            merged: Set[str] = set(items)
            for item in items:
                merged.update(KindStrategy.expand_equivalent_clique(item))
            return sorted(merged)

        if isinstance(value, str):
            stripped: str = value.strip()
            if not stripped:
                return None
            return sorted(set(KindStrategy.expand_equivalent_clique(stripped)))

        return None

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
