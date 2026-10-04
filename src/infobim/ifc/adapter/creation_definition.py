import re
from typing import Any, ClassVar, Dict, List, Tuple, Pattern, Optional
from dataclasses import dataclass
from functools import lru_cache

from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary

from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.domain.exception.creation import IfcCreationError


@dataclass(frozen=True)
class IfcCreationDefinition:
    """
    What creating one product of a resolved kind needs.

    The IFC class and predefined type come from the kind's IFC element
    binding; the geometry comes from its visual representation.
    ``dimensions`` are the visual's declared lengths in metres, keyed by the
    parameter names the geometry primitive declares; ``directions`` are its
    unitless direction ratios.
    """

    title_base: str
    binding_iri: str
    visual_iri: str
    ifc_class: str
    ifc_schema: str
    predefined_type: Optional[str]
    geometry_kind: str
    dimensions: Tuple[Tuple[str, float], ...]
    directions: Tuple[Tuple[str, float], ...]

    def geometry(self, metres_per_model_unit: float) -> GeometryDefinition:
        """
        Return the geometry in the length unit of the target model.
        """
        if metres_per_model_unit <= 0.0:
            raise IfcCreationError(
                f"The target model length unit scale {metres_per_model_unit} "
                "is not a positive number."
            )
        parameters: List[Tuple[str, float]] = [
            (name, value / metres_per_model_unit) for name, value in self.dimensions
        ]
        parameters.extend(self.directions)
        return GeometryDefinition(kind=self.geometry_kind, parameters=tuple(parameters))


class KindRepresentationCreationDefinition:
    """
    Read the creation definition of the kind a term resolved to.

    The input is the dictionary pipeline's own output: the ontology term
    resolution and the representations resolved for its terms, each with
    its JSON-LD definition. Nothing here reads the text the user typed.

    A kind is created from two declarations that complement each other:
    its IFC element binding (``aeco:IfcElementBinding``), which names the
    IFC class and predefined type, and its visual representation
    (``aeco:VisualRepresentation``), which names the geometry and its
    dimensions. Creating products needs exactly one term of an exact match
    declaring exactly one of each; any other resolution has no rule that
    picks what to create, and fails.
    """

    EXACT_MATCH_TYPE: ClassVar[str] = "exact"
    AECO_CATALOG_IRI: ClassVar[str] = "http://datacenter.app.br/ontology/domain/aeco/catalog.ttl"
    #: The prefix the AECO catalog binds to the AECO core schema.
    AECO_PREFIX: ClassVar[str] = "aeco"
    IFC_ELEMENT_BINDING_NAME: ClassVar[str] = "IfcElementBinding"
    VISUAL_REPRESENTATION_NAME: ClassVar[str] = "VisualRepresentation"
    SUBCLASS_OF: ClassVar[str] = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
    ON_PROPERTY: ClassVar[str] = "http://www.w3.org/2002/07/owl#onProperty"
    SOME_VALUES_FROM: ClassVar[str] = "http://www.w3.org/2002/07/owl#someValuesFrom"
    HAS_VALUE: ClassVar[str] = "http://www.w3.org/2002/07/owl#hasValue"
    HAS_GEOMETRY: ClassVar[str] = "https://w3id.org/omg#hasGeometry"
    IFC_IRI: ClassVar[Pattern[str]] = re.compile(
        r"^https://standards\.buildingsmart\.org/IFC/DEV/(?P<schema>[^/]+)/.*#(?P<name>.+)$"
    )
    PREDEFINED_TYPE_PREFIX: ClassVar[str] = "predefinedType_"

    GEOMETRY_KINDS: ClassVar[Dict[str, str]] = {
        "SolidBox3DRepresentation": GeometryDefinition.BOX_KIND,
        "SolidCylindrical3DRepresentation": GeometryDefinition.CYLINDER_KIND,
        "SolidSpherical3DRepresentation": GeometryDefinition.SPHERE_KIND,
    }
    DIMENSION_PARAMETERS: ClassVar[Dict[str, str]] = {
        "xLength": "x_length",
        "yLength": "y_length",
        "zLength": "z_length",
        "radius": "radius",
        "height": "height",
    }
    DIRECTION_PARAMETERS: ClassVar[Dict[str, str]] = {
        "directionX": "direction_x",
        "directionY": "direction_y",
        "directionZ": "direction_z",
    }

    @classmethod
    def of(
        cls,
        resolution: Dict[str, Any],
        kind_representations: Dict[str, List[Dict[str, Any]]],
    ) -> IfcCreationDefinition:
        if resolution["match_type"] != cls.EXACT_MATCH_TYPE:
            raise IfcCreationError(
                "Creating IFC products needs an exact ontology match; the term "
                f"resolved only as '{resolution['match_type']}' candidates."
            )

        creatable: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
        term: Dict[str, Any]
        for term in resolution["exact_matches"]:
            bindings: List[Dict[str, Any]] = []
            visuals: List[Dict[str, Any]] = []
            representation: Dict[str, Any]
            for representation in kind_representations[term["iri"]]:
                role: str = cls._role(representation)
                (bindings if role == cls._aeco() + cls.IFC_ELEMENT_BINDING_NAME else visuals).append(
                    representation
                )
            if not bindings and not visuals:
                continue
            if len(bindings) != 1 or len(visuals) != 1:
                raise IfcCreationError(
                    f"Kind {term['iri']} declares {len(bindings)} IFC element "
                    f"bindings and {len(visuals)} visual representations; "
                    "creating products needs exactly one of each."
                )
            creatable.append((term["label"], bindings[0], visuals[0]))

        if len(creatable) != 1:
            kinds: str = ", ".join(
                binding["iri"] for _label, binding, _visual in creatable
            ) or "none"
            raise IfcCreationError(
                f"The resolved terms declare {len(creatable)} creatable kinds "
                f"({kinds}); creating products needs exactly one."
            )

        label, binding, visual = creatable[0]
        ifc_class, ifc_schema, predefined_type = cls._binding(binding)
        geometry_kind, dimensions, directions = cls._visual(visual)
        return IfcCreationDefinition(
            title_base=label,
            binding_iri=binding["iri"],
            visual_iri=visual["iri"],
            ifc_class=ifc_class,
            ifc_schema=ifc_schema,
            predefined_type=predefined_type,
            geometry_kind=geometry_kind,
            dimensions=dimensions,
            directions=directions,
        )

    @classmethod
    @lru_cache(maxsize=1)
    def _aeco(cls) -> str:
        """
        The AECO core schema namespace: the one the AECO catalog binds.
        """
        library: BrasidataCenterOntologyLibrary = BrasidataCenterOntologyLibrary()
        return str(
            library.bound_namespace(library.graph(cls.AECO_CATALOG_IRI), cls.AECO_PREFIX)
        )

    @classmethod
    def _role(cls, representation: Dict[str, Any]) -> str:
        """
        Return whether a representation is an IFC element binding or a visual.
        """
        parents: List[str] = [
            parent["@id"] for parent in cls._node(representation).get(cls.SUBCLASS_OF, [])
        ]
        roles: List[str] = [
            role
            for role in (
                cls._aeco() + cls.IFC_ELEMENT_BINDING_NAME,
                cls._aeco() + cls.VISUAL_REPRESENTATION_NAME,
            )
            if role in parents
        ]
        if len(roles) != 1:
            raise IfcCreationError(
                f"Representation {representation['iri']!r} is not exactly one of "
                "an IFC element binding or a visual representation."
            )
        return roles[0]

    @classmethod
    def _binding(cls, binding: Dict[str, Any]) -> Tuple[str, str, Optional[str]]:
        """Return the IFC class, schema and predefined type a binding names."""
        iri: str = binding["iri"]
        nodes: Dict[str, Dict[str, Any]] = cls._nodes(binding)
        ifc_classes: List[Tuple[str, str]] = []
        predefined_types: List[Tuple[str, str]] = []
        parent: Dict[str, str]
        for parent in nodes[iri].get(cls.SUBCLASS_OF, []):
            parent_id: str = parent["@id"]
            if parent_id not in nodes:
                match: Optional[re.Match[str]] = cls.IFC_IRI.match(parent_id)
                if match is not None:
                    ifc_classes.append((match["name"], match["schema"]))
                continue
            restriction: Dict[str, Any] = nodes[parent_id]
            if cls.ON_PROPERTY not in restriction:
                continue
            property_name: str = cls._local_name(
                cls._single(restriction, cls.ON_PROPERTY)["@id"]
            )
            if property_name.startswith(cls.PREDEFINED_TYPE_PREFIX):
                predefined_types.append(
                    (
                        property_name,
                        cls._local_name(cls._single(restriction, cls.HAS_VALUE)["@id"]),
                    )
                )

        if len(ifc_classes) != 1:
            raise IfcCreationError(
                f"IFC element binding {iri!r} names {len(ifc_classes)} IFC "
                "classes; creating a product needs exactly one."
            )
        ifc_class, ifc_schema = ifc_classes[0]

        if not predefined_types:
            return ifc_class, ifc_schema, None
        expected: str = cls.PREDEFINED_TYPE_PREFIX + ifc_class
        if len(predefined_types) != 1 or predefined_types[0][0] != expected:
            raise IfcCreationError(
                f"IFC element binding {iri!r} must restrict at most one "
                f"predefined type, through {expected}."
            )
        return ifc_class, ifc_schema, predefined_types[0][1]

    @classmethod
    def _visual(
        cls, visual: Dict[str, Any]
    ) -> Tuple[str, Tuple[Tuple[str, float], ...], Tuple[Tuple[str, float], ...]]:
        """Return the geometry kind, dimensions and directions a visual declares."""
        iri: str = visual["iri"]
        nodes: Dict[str, Dict[str, Any]] = cls._nodes(visual)
        geometry_classes: List[str] = []
        dimensions: List[Tuple[str, float]] = []
        directions: List[Tuple[str, float]] = []
        parent: Dict[str, str]
        for parent in nodes[iri].get(cls.SUBCLASS_OF, []):
            restriction: Optional[Dict[str, Any]] = nodes.get(parent["@id"])
            if restriction is None or cls.ON_PROPERTY not in restriction:
                continue
            property_iri: str = cls._single(restriction, cls.ON_PROPERTY)["@id"]
            property_name: str = cls._local_name(property_iri)
            if property_iri == cls.HAS_GEOMETRY:
                geometry_classes.append(
                    cls._single(restriction, cls.SOME_VALUES_FROM)["@id"]
                )
            elif property_iri.startswith(cls._aeco()) and (
                property_name in cls.DIMENSION_PARAMETERS
            ):
                dimensions.append(
                    (
                        cls.DIMENSION_PARAMETERS[property_name],
                        cls._number(restriction, property_name),
                    )
                )
            elif property_iri.startswith(cls._aeco()) and (
                property_name in cls.DIRECTION_PARAMETERS
            ):
                directions.append(
                    (
                        cls.DIRECTION_PARAMETERS[property_name],
                        cls._number(restriction, property_name),
                    )
                )

        if len(geometry_classes) != 1:
            raise IfcCreationError(
                f"Visual representation {iri!r} declares {len(geometry_classes)} "
                "geometries; creating a product needs exactly one."
            )
        geometry_class: str = geometry_classes[0]
        geometry_name: str = cls._local_name(geometry_class)
        if not geometry_class.startswith(cls._aeco()) or (
            geometry_name not in cls.GEOMETRY_KINDS
        ):
            raise IfcCreationError(
                f"Visual representation {iri!r} declares the geometry "
                f"{geometry_class}, which is not a solid primitive the IFC "
                f"creation supports ({', '.join(sorted(cls.GEOMETRY_KINDS))})."
            )
        if not dimensions:
            raise IfcCreationError(
                f"Visual representation {iri!r} declares no dimension of its "
                "geometry."
            )
        return (
            cls.GEOMETRY_KINDS[geometry_name],
            tuple(sorted(dimensions)),
            tuple(sorted(directions)),
        )

    @classmethod
    def _nodes(cls, representation: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        nodes: Dict[str, Dict[str, Any]] = {
            node["@id"]: node for node in representation["json_ld"]
        }
        if representation["iri"] not in nodes:
            raise IfcCreationError(
                f"JSON-LD does not describe representation {representation['iri']!r}."
            )
        return nodes

    @classmethod
    def _node(cls, representation: Dict[str, Any]) -> Dict[str, Any]:
        return cls._nodes(representation)[representation["iri"]]

    @classmethod
    def _number(cls, restriction: Dict[str, Any], property_name: str) -> float:
        literal: Dict[str, Any] = cls._single(restriction, cls.HAS_VALUE)
        if "@value" not in literal:
            raise IfcCreationError(f"{property_name} must restrict a literal value.")
        try:
            return float(literal["@value"])
        except (TypeError, ValueError) as error:
            raise IfcCreationError(
                f"{property_name} value {literal['@value']!r} is not a number."
            ) from error

    @staticmethod
    def _single(node: Dict[str, Any], key: str) -> Dict[str, Any]:
        values: Any = node.get(key)
        if not isinstance(values, list) or len(values) != 1:
            raise IfcCreationError(
                f"Restriction {node['@id']!r} must state exactly one {key}."
            )
        return values[0]

    @staticmethod
    def _local_name(iri: str) -> str:
        return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
