from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.dict.adapter.geometry import DictionaryGeometryTranslator
from infobim.dict.domain.model.definition import (
    DictionaryEntry,
    EntityDefinition,
    GeometryDescription,
)
from infobim.dict.domain.exception.dictionary import (
    DictionaryDefinitionInvalidError,
)
from infobim.dict.plugin.machine.dictionary_entity_create.state import (
    DictionaryEntityContextKeys,
    DictionaryEntityCreateProcessState,
)


class DictionaryGeometryDefinedCapability(TransactionCapability):
    """
    Defines this run's geometry from the shape the dictionary states.

    The state means the same thing it means when a geometry command
    brings it about — the primitive of this run is completely defined —
    and it is reached differently: there a caller measured the solid,
    here the dictionary already did. That is the whole point of defining
    an element from a dictionary, so the measurements are taken as the
    entry states them and nothing about them is asked of the caller.

    What is bound is what the rest of the flow expects to find, in the
    form it expects: the definition every geometry responsibility
    dispatches on. From here the element's geometry is created by the
    same capability that creates a command's, because by this point
    there is nothing left to tell them apart.

    An entry that describes no shape fails here rather than further on.
    Everything after this state exists to give the element a
    representation, and an element defined from an entry with no geometry
    has nothing for them to work with.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.dict.plugin.capability.transformation.target."
            "geometry_defined"
        ),
        version="0.1.0",
        name="Dictionary Geometry Defined",
        description=(
            "Define this run's geometry from the shape the dictionary entry "
            "states for the element."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "dict", "dictionary", "geometry", "geometry_defined"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                # Declared without a JSON type on purpose: what this
                # takes is the DictionaryEntry the reading state bound,
                # which is an object of this domain rather than a
                # mapping, and calling it one would fail the input check
                # for being exactly what it should be.
                "dictionary_definition": {
                    "required": True,
                    "description": (
                        "The entry this run read, carrying the element's own "
                        "definition."
                    ),
                },
            },
            "required": ["dictionary_definition"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "geometry": {"type": "object"},
            },
            "required": ["geometry"],
        },
        log_message={
            "info": {
                "en": "The geometry the dictionary states for the element is defined.",
            },
            "debug_entry": {
                "en": "Defining the element's geometry from the dictionary entry.",
            },
        },
    )

    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    GEOMETRY_KEY: ClassVar[str] = "geometry"

    def label(self, lang: str = "en") -> str:
        return DictionaryEntityCreateProcessState.GEOMETRY_DEFINED.label(lang)

    def description(self, lang: str = "en") -> str:
        return DictionaryEntityCreateProcessState.GEOMETRY_DEFINED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Bind the primitive the dictionary describes, for this run.
        """
        entry: Any = context.get_parameter_value(
            DictionaryEntityContextKeys.DICTIONARY_DEFINITION_KEY
        )
        if not isinstance(entry, DictionaryEntry):
            raise DictionaryDefinitionInvalidError(
                "No dictionary entry was read for this run, so the element's "
                "geometry cannot be defined from one."
            )

        element: EntityDefinition = entry.element_definition()
        description: GeometryDescription = self._described(entry, element)
        definition: GeometryDefinition = DictionaryGeometryTranslator.translate(
            description
        )
        serialized: Dict[str, Any] = definition.to_dict()
        context.set_parameter_value(self.GEOMETRY_KEY, serialized)

        return {
            self.RESULTING_STATE_KEY: (
                DictionaryEntityCreateProcessState.GEOMETRY_DEFINED
            ),
            self.GEOMETRY_KEY: serialized,
        }

    @staticmethod
    def _described(
        entry: DictionaryEntry,
        element: EntityDefinition,
    ) -> GeometryDescription:
        """
        Return the shape the entry states, or fail saying it states none.
        """
        if element.geometry is None:
            raise DictionaryDefinitionInvalidError(
                f"The dictionary entry at {entry.source_uri} defines "
                f"{element.label} without a geometry, so there is no shape to "
                f"create for the element."
            )

        return element.geometry
