from typing import (
    Any,
    ClassVar,
    Collection,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)
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
    REPRESENTS_DOMAIN_CLASSES_KEY: ClassVar[str] = "represents_domain_classes"
    GEOMETRY_KEY: ClassVar[str] = "geometry"

    uri: str
    label: str
    ifc_class: Optional[str]
    predefined_type: Optional[str]
    classifications: Tuple[str, ...]
    represents_domain_classes: Tuple[str, ...]
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
            self.REPRESENTS_DOMAIN_CLASSES_KEY: list(
                self.represents_domain_classes
            ),
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

    def ifc_definitions(
        self,
        aeco_class_uri: Optional[Union[str, Collection[str]]] = None,
    ) -> List[EntityDefinition]:
        """
        Return the definitions that map onto an IFC class.

        When ``aeco_class_uri`` is given, only the definitions that state
        a ``crm:P138_represents`` restriction pointing at that domain
        class (or any member of a collection passed in) are returned.
        Accepting a collection is deliberate: when the resolver matched
        an AECO class declared as ``owl:equivalentClass`` to a distinct
        node the representation link actually points to, passing the
        whole equivalent-class clique in keeps this narrowing consistent
        with the reverse-link lookup that picked the entry document.

        A URI collection that does not match anything does not widen the
        filter back to "everything with an IFC class": a stated hint that
        matches no candidate is reported as zero matches so callers do
        not silently create the wrong element.
        """
        targets: Optional[List[str]] = self._normalise_targets(aeco_class_uri)

        if targets is None:
            return [
                definition
                for definition in self.definitions
                if definition.ifc_class is not None
            ]

        matched: List[EntityDefinition] = []
        definition: EntityDefinition
        for definition in self.definitions:
            if definition.ifc_class is None:
                continue
            if self._definition_represents(definition, targets):
                matched.append(definition)

        return matched

    def element_definition(
        self,
        aeco_class_uri: Optional[Union[str, Collection[str]]] = None,
    ) -> EntityDefinition:
        """
        Return the one definition that says what the element is.

        An entry declares several classes and only one of them is the
        element: the others say what its representation is, what its
        shape is, what it is a kind of. The element is the one that maps
        onto an IFC class, and there is exactly one of those or the entry
        does not define an element — none, and it defines something else;
        two, and it does not say which of them to create. Neither is a
        choice for this side to make.

        When the caller knows which AECO domain class the kind string
        resolved to, or the equivalent-class clique the resolver
        expanded it to, that hint is used to narrow the candidates down
        to the representation that ``crm:P138_represents`` any of those
        specific domain classes. Entries that group several predefined
        types of one IFC class in a single document (e.g.
        ``IfcSanitaryTerminal`` with TOILETPAN/WASHHANDBASIN/SHOWER/SINK)
        depend on this narrowing, because every one of them maps onto an
        IFC class and the generic single-candidate rule would otherwise
        reject them all.
        """
        candidates: List[EntityDefinition] = self.ifc_definitions(aeco_class_uri)
        if len(candidates) != 1:
            rendered_targets: str
            targets: Optional[List[str]] = self._normalise_targets(aeco_class_uri)
            if targets is None:
                rendered_targets = ""
            elif len(targets) == 1:
                rendered_targets = f" narrowed by AECO class <{targets[0]}>"
            else:
                rendered_targets = (
                    " narrowed by AECO classes ["
                    + ", ".join(f"<{t}>" for t in targets)
                    + "]"
                )
            raise DictionaryDefinitionInvalidError(
                f"The dictionary entry at {self.source_uri} declares "
                f"{len(candidates)} classes that map onto an IFC class"
                f"{rendered_targets}, and an element is defined by exactly one."
            )

        return candidates[0]

    @staticmethod
    def _normalise_targets(
        aeco_class_uri: Optional[Union[str, Collection[str]]],
    ) -> Optional[List[str]]:
        """
        Coerce the caller's ``aeco_class_uri`` argument into a clean list
        of stripped target URIs, or ``None`` when no narrowing was asked
        for.

        A single string, an empty string, an empty collection and
        collections whose every item is whitespace-only are all handled
        deterministically so callers do not need to mirror this
        normalisation on their side.
        """
        if aeco_class_uri is None:
            return None
        if isinstance(aeco_class_uri, str):
            stripped: str = aeco_class_uri.strip()
            return [stripped] if stripped else None

        cleaned: List[str] = []
        item: Any
        for item in aeco_class_uri:
            if not isinstance(item, str):
                continue
            s: str = item.strip()
            if s:
                cleaned.append(s)
        return cleaned or None

    @classmethod
    def _definition_represents(
        cls,
        definition: EntityDefinition,
        target_aeco_class_uris: Collection[str],
    ) -> bool:
        """
        Return whether ``definition`` was declared as the representation
        that ``crm:P138_represents`` any of the target AECO domain class
        URIs.

        This match is exact and case-sensitive on the stripped URI, so
        ``http://.../Lavatorio`` and ``http://.../Lavatorio#`` collapse
        to the same target while ``http://.../LavatorioCuba`` is a
        distinct class and does not match.
        """
        targets: List[str] = [
            uri.strip().rstrip("#") for uri in target_aeco_class_uris
        ]
        domain_uri: str
        for domain_uri in definition.represents_domain_classes:
            cleaned: str = domain_uri.strip().rstrip("#")
            if cleaned in targets:
                return True
        return False

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
