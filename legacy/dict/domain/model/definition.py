from typing import Any, ClassVar, Dict, List, Optional, Tuple
from dataclasses import dataclass

from infobim.dict.domain.exception.dictionary import (
    DictionaryDefinitionInvalidError,
)


@dataclass(frozen=True)
class GeometryDescription:
    """
    The shape a dictionary entry states for an element, in its own terms.

    A dictionary does not describe geometry in IFC. It says the element
    has a geometry, that the geometry is of some level of detail, and
    that its shape is a primitive of the X3D vocabulary carrying the
    measurements that primitive declares. This carries exactly that, as
    the entry stated it: the primitive's own name and the values pinned
    to its own properties.

    Nothing here is an IFC decision. Which IFC representation item says
    this shape, and in which units and context it is measured, belongs to
    the step that creates the geometry — and keeping the two apart is
    what lets the same entry be read by something that is not writing IFC
    at all.

    ``level_of_detail`` is what the entry says the description is good
    for. An entry that states none leaves it ``None``: a description with
    no declared level of detail is not a description at level zero.
    """

    PRIMITIVE_KEY: ClassVar[str] = "primitive"
    PARAMETERS_KEY: ClassVar[str] = "parameters"
    LEVEL_OF_DETAIL_KEY: ClassVar[str] = "level_of_detail"

    primitive: str
    parameters: Tuple[Tuple[str, float], ...]
    level_of_detail: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """
        Return the serializable form of this description.
        """
        return {
            self.PRIMITIVE_KEY: self.primitive,
            self.PARAMETERS_KEY: [list(pair) for pair in self.parameters],
            self.LEVEL_OF_DETAIL_KEY: self.level_of_detail,
        }


@dataclass(frozen=True)
class EntityDefinition:
    """
    One class a dictionary entry declares, in the terms the entry used.

    A dictionary says what an element *is* by declaring a class and what
    that class is a kind of: an IFC class it maps onto, a predefined type
    that IFC class is restricted to, and the domain classes it also
    belongs to. This carries those four things and nothing else — no IFC
    entity, no placement, no product. Turning a definition into something
    an IFC model carries is a later step, and keeping this free of it is
    what lets the same definition be applied to an element that already
    exists as well as to one that does not exist yet.

    ``ifc_class``, ``predefined_type`` and ``geometry`` are ``None`` when
    the entry declares none. A dictionary entry may declare a class that
    maps onto no IFC class at all — the 3D representation of an element
    is one — and that absence is part of what the entry says, never a
    value to be filled in from somewhere else.

    ``geometry`` is reached through the entry rather than carried by the
    element's own class: an element has a geometry, that geometry has a
    description, and the description is the shape. Following that chain
    is the reader's job, so what arrives here is the shape itself and
    whoever holds a definition does not have to walk a graph to find out
    what the element looks like.
    """

    URI_KEY: ClassVar[str] = "uri"
    LABEL_KEY: ClassVar[str] = "label"
    IFC_CLASS_KEY: ClassVar[str] = "ifc_class"
    PREDEFINED_TYPE_KEY: ClassVar[str] = "predefined_type"
    CLASSIFICATIONS_KEY: ClassVar[str] = "classifications"
    GEOMETRY_KEY: ClassVar[str] = "geometry"

    uri: str
    label: str
    ifc_class: Optional[str]
    predefined_type: Optional[str]
    classifications: Tuple[str, ...]
    geometry: Optional[GeometryDescription]

    def to_dict(self) -> Dict[str, Any]:
        """
        Return the serializable form of this definition.
        """
        return {
            self.URI_KEY: self.uri,
            self.LABEL_KEY: self.label,
            self.IFC_CLASS_KEY: self.ifc_class,
            self.PREDEFINED_TYPE_KEY: self.predefined_type,
            self.CLASSIFICATIONS_KEY: list(self.classifications),
            self.GEOMETRY_KEY: (
                self.geometry.to_dict() if self.geometry is not None else None
            ),
        }


@dataclass(frozen=True)
class DictionaryEntry:
    """
    Everything one dictionary document declares, and where it came from.

    An entry is not a single definition: the sanitary terminal entry of
    the reference dictionary declares the element and its 3D
    representation in the same document, and both belong to whoever asked
    for that URI. So the entry keeps all of them, in the order the
    document declared them, and answers separately for the one that maps
    onto an IFC class — which is the definition an IFC element is made
    from, when the entry has one.

    ``source_uri`` is the URI the caller named and ``document_path`` is
    where this run stored what that URI returned, so a definition can
    always be traced back both to its dictionary and to the copy this
    element was defined from.
    """

    SOURCE_URI_KEY: ClassVar[str] = "source_uri"
    DOCUMENT_PATH_KEY: ClassVar[str] = "document_path"
    DEFINITIONS_KEY: ClassVar[str] = "definitions"

    source_uri: str
    document_path: str
    definitions: Tuple[EntityDefinition, ...]

    def ifc_definitions(self) -> List[EntityDefinition]:
        """
        Return the definitions that map onto an IFC class.
        """
        return [
            definition
            for definition in self.definitions
            if definition.ifc_class is not None
        ]

    def element_definition(self) -> EntityDefinition:
        """
        Return the one definition that says what the element is.

        An entry declares several classes and only one of them is the
        element: the others say what its representation is, what its
        shape is, what it is a kind of. The element is the one that maps
        onto an IFC class, and there is exactly one of those or the entry
        does not define an element — none, and it defines something else;
        two, and it does not say which of them to create. Neither is a
        choice for this side to make.
        """
        candidates: List[EntityDefinition] = self.ifc_definitions()
        if len(candidates) != 1:
            raise DictionaryDefinitionInvalidError(
                f"The dictionary entry at {self.source_uri} declares "
                f"{len(candidates)} classes that map onto an IFC class, and "
                f"an element is defined by exactly one."
            )

        return candidates[0]

    def to_dict(self) -> Dict[str, Any]:
        """
        Return the serializable form of this entry.
        """
        return {
            self.SOURCE_URI_KEY: self.source_uri,
            self.DOCUMENT_PATH_KEY: self.document_path,
            self.DEFINITIONS_KEY: [
                definition.to_dict() for definition in self.definitions
            ],
        }
