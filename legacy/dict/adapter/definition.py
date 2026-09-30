from math import isfinite
from typing import Any, ClassVar, List, Optional, Set, Tuple
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from infobim.dict.adapter.vocabulary import DictionaryVocabulary
from infobim.dict.domain.port.dictionary import DictionaryDefinitionReaderPort
from infobim.dict.domain.exception.dictionary import (
    DictionaryDefinitionInvalidError,
)
from infobim.dict.domain.model.definition import (
    DictionaryEntry,
    EntityDefinition,
    GeometryDescription,
)


class DictionaryDefinitionReader(DictionaryDefinitionReaderPort):
    """
    Reads what a dictionary document declares, as the document declares it.

    An entry is a small OWL document: one or more classes, each stated to
    be a subclass of the things it is a kind of. What this reads out of
    that is exactly those statements — the IFC class the definition maps
    onto, the predefined type an OWL restriction pins that class to, and
    every other class the definition belongs to. Nothing is inferred and
    nothing is completed: a reasoner is a different tool with different
    guarantees, and an element defined from an entry should be explainable
    by reading the entry.

    A definition that maps onto no IFC class is kept rather than
    discarded. The reference entry for a sanitary terminal declares both
    the element and its 3D representation, and the one without an IFC
    class is the representation — a statement about the same element, not
    a defect in the document.

    The document is read from the copy the project stored, never from the
    dictionary again, so what a definition says cannot change between
    being downloaded and being understood.
    """

    TURTLE_FORMAT: ClassVar[str] = "turtle"

    def read(self, document_path: Path, source_uri: str) -> DictionaryEntry:
        """
        Return everything the document declares, or fail saying why not.
        """
        graph: Graph = self._graph(document_path)
        definitions: List[EntityDefinition] = [
            self._definition(graph, subject)
            for subject in self._declared_classes(graph)
        ]
        if not definitions:
            raise DictionaryDefinitionInvalidError(
                f"The dictionary entry at {source_uri} declares no class, so "
                f"it defines nothing that could be applied to an element."
            )

        return DictionaryEntry(
            source_uri=source_uri,
            document_path=str(document_path),
            definitions=tuple(definitions),
        )

    @classmethod
    def _graph(cls, document_path: Path) -> Graph:
        """
        Return the document as a graph, or fail saying it is not one.
        """
        graph: Graph = Graph()
        try:
            graph.parse(source=str(document_path), format=cls.TURTLE_FORMAT)
        except Exception as error:
            raise DictionaryDefinitionInvalidError(
                f"The dictionary entry stored at {document_path} does not "
                f"read as Turtle: {error}."
            ) from error

        return graph

    @staticmethod
    def _declared_classes(graph: Graph) -> List[URIRef]:
        """
        Return the named classes the document declares, in a stable order.

        A blank node typed as a class is an OWL construct inside another
        statement — a restriction, an intersection — and not a class the
        dictionary is offering by name, so only named subjects are
        definitions here.
        """
        declared: Set[URIRef] = {
            subject
            for subject in graph.subjects(RDF.type, OWL.Class)
            if isinstance(subject, URIRef)
        }

        return sorted(declared, key=str)

    @classmethod
    def _definition(cls, graph: Graph, subject: URIRef) -> EntityDefinition:
        """
        Return one class as the definition it states itself to be.
        """
        ifc_classes: Set[str] = set()
        predefined_types: Set[str] = set()
        classifications: List[str] = []

        super_class: Any
        for super_class in graph.objects(subject, RDFS.subClassOf):
            if isinstance(super_class, URIRef):
                ifc_class: Optional[str] = DictionaryVocabulary.ifc_local_name_of(
                    str(super_class)
                )
                if ifc_class is None:
                    classifications.append(str(super_class))
                else:
                    ifc_classes.add(ifc_class)
                continue

            if isinstance(super_class, BNode):
                restricted: Optional[Tuple[str, str]] = cls._restriction(
                    graph,
                    super_class,
                )
                if restricted is not None:
                    ifc_classes.add(restricted[0])
                    predefined_types.add(restricted[1])

        return EntityDefinition(
            uri=str(subject),
            label=DictionaryVocabulary.local_name_of(str(subject)),
            ifc_class=cls._single(ifc_classes, subject, "IFC class"),
            predefined_type=cls._single(
                predefined_types,
                subject,
                "predefined type",
            ),
            classifications=tuple(sorted(classifications)),
            geometry=cls._geometry(graph, subject),
        )

    @classmethod
    def _geometry(cls, graph: Graph, subject: URIRef) -> Optional[GeometryDescription]:
        """
        Return the shape the entry states for a class, if it states one.

        The entry says it in three steps, and each one is a different
        statement worth keeping apart: the element has a geometry, that
        geometry has a description, and the description is a primitive
        with measurements. This walks exactly those three and nothing
        else — a class that states no geometry has none here, which is
        what an entry for something with no shape looks like.

        A chain that starts and does not finish is an error rather than
        an absence: an element declared to have a geometry whose
        description cannot be read is an entry that promised a shape it
        does not deliver, and reporting it as shapeless would hide that.
        """
        representation: Optional[URIRef] = cls._some_values_from(
            graph,
            subject,
            DictionaryVocabulary.HAS_GEOMETRY_PROPERTY,
        )
        if representation is None:
            return None

        description: Optional[URIRef] = cls._some_values_from(
            graph,
            representation,
            DictionaryVocabulary.HAS_DESCRIPTION_PROPERTY,
        )
        if description is None:
            raise DictionaryDefinitionInvalidError(
                f"The definition {subject} states a geometry at "
                f"{representation}, and that geometry states no description "
                f"of its shape."
            )

        primitive: Optional[str] = cls._primitive(graph, description)
        if primitive is None:
            raise DictionaryDefinitionInvalidError(
                f"The geometry description {description} states no X3D "
                f"primitive, so what the element is shaped like cannot be "
                f"read from it."
            )

        return GeometryDescription(
            primitive=primitive,
            parameters=cls._measurements(graph, description),
            level_of_detail=cls._level_of_detail(graph, representation),
        )

    @classmethod
    def _some_values_from(
        cls,
        graph: Graph,
        subject: URIRef,
        property_uri: str,
    ) -> Optional[URIRef]:
        """
        Return the class a restriction on the given property points at.
        """
        node: Any
        for node in graph.objects(subject, RDFS.subClassOf):
            if not isinstance(node, BNode):
                continue
            if (node, RDF.type, OWL.Restriction) not in graph:
                continue
            if graph.value(node, OWL.onProperty) != URIRef(property_uri):
                continue

            target: Any = graph.value(node, OWL.someValuesFrom)
            if isinstance(target, URIRef):
                return target

        return None

    @classmethod
    def _primitive(cls, graph: Graph, description: URIRef) -> Optional[str]:
        """
        Return the X3D primitive a geometry description is a kind of.
        """
        super_class: Any
        for super_class in graph.objects(description, RDFS.subClassOf):
            if not isinstance(super_class, URIRef):
                continue

            primitive: Optional[str] = DictionaryVocabulary.x3d_local_name_of(
                str(super_class)
            )
            if primitive is not None:
                return primitive

        return None

    @classmethod
    def _measurements(
        cls,
        graph: Graph,
        description: URIRef,
    ) -> Tuple[Tuple[str, float], ...]:
        """
        Return the values the description pins to the primitive's own
        properties.

        A measurement that does not read as a number is reported rather
        than dropped: a radius stated as something that is not a length
        is a defect in the entry, and an element built from the rest of
        it would be an element nobody asked for.
        """
        measurements: List[Tuple[str, float]] = []
        node: Any
        for node in graph.objects(description, RDFS.subClassOf):
            if not isinstance(node, BNode):
                continue
            if (node, RDF.type, OWL.Restriction) not in graph:
                continue

            prop: Any = graph.value(node, OWL.onProperty)
            if not isinstance(prop, URIRef):
                continue

            name: Optional[str] = DictionaryVocabulary.x3d_local_name_of(str(prop))
            if name is None:
                continue

            value: Any = graph.value(node, OWL.hasValue)
            if not isinstance(value, Literal):
                continue

            measurements.append((name, cls._measurement(description, name, value)))

        return tuple(sorted(measurements))

    @staticmethod
    def _measurement(description: URIRef, name: str, value: Literal) -> float:
        """
        Return one stated measurement as the number it has to be.
        """
        try:
            measurement: float = float(value.toPython())
        except (TypeError, ValueError) as error:
            raise DictionaryDefinitionInvalidError(
                f"The geometry description {description} states "
                f"'{value}' for {name}, which does not read as a number."
            ) from error

        if not isfinite(measurement):
            raise DictionaryDefinitionInvalidError(
                f"The geometry description {description} states "
                f"{measurement} for {name}, and a shape cannot be measured "
                f"by a value that is not finite."
            )

        return measurement

    @classmethod
    def _level_of_detail(cls, graph: Graph, representation: URIRef) -> Optional[str]:
        """
        Return what the entry says the geometry is good for, if it says.
        """
        node: Any
        for node in graph.objects(representation, RDFS.subClassOf):
            if not isinstance(node, BNode):
                continue
            if (node, RDF.type, OWL.Restriction) not in graph:
                continue
            if graph.value(node, OWL.onProperty) != URIRef(
                DictionaryVocabulary.HAS_LEVEL_OF_DETAIL_PROPERTY
            ):
                continue

            level: Any = graph.value(node, OWL.hasValue)
            if isinstance(level, URIRef):
                return DictionaryVocabulary.local_name_of(str(level))

        return None

    @classmethod
    def _restriction(
        cls,
        graph: Graph,
        node: BNode,
    ) -> Optional[Tuple[str, str]]:
        """
        Return the (IFC class, predefined type) a restriction pins, if any.

        Only a restriction on an ifcOWL ``predefinedType_`` property says
        this; every other restriction a dictionary may carry states
        something this reader does not claim to understand and is left
        alone rather than half-read.
        """
        if (node, RDF.type, OWL.Restriction) not in graph:
            return None

        prop: Any = graph.value(node, OWL.onProperty)
        value: Any = graph.value(node, OWL.hasValue)
        if not isinstance(prop, URIRef) or not isinstance(value, URIRef):
            return None

        owner: Optional[str] = DictionaryVocabulary.predefined_type_property(
            str(prop)
        )
        predefined_type: Optional[str] = DictionaryVocabulary.ifc_local_name_of(
            str(value)
        )
        if owner is None or predefined_type is None:
            return None

        return owner, predefined_type

    @staticmethod
    def _single(
        values: Set[str],
        subject: URIRef,
        what: str,
    ) -> Optional[str]:
        """
        Return the one value the definition states, or ``None`` for none.

        Two of them is not a value to choose between: a definition that
        maps onto two IFC classes, or onto two predefined types, does not
        say what the element is, and picking either would be this reader
        deciding something the dictionary did not.
        """
        if not values:
            return None

        if len(values) > 1:
            raise DictionaryDefinitionInvalidError(
                f"The dictionary definition {subject} states "
                f"{len(values)} values for its {what} "
                f"({', '.join(sorted(values))}), so what the element is "
                f"cannot be read from it."
            )

        return next(iter(values))
