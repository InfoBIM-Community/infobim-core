from typing import Any, ClassVar, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass(frozen=True)
class GeometryDefinition:
    """
    A primitive geometry as its own command defined it, before any IFC.

    This is what a geometry command produces and what ``GEOMETRY_DEFINED``
    means: the dimensions of a solid in its own local terms, serializable
    and carrying no IFC entity, no product semantics and no placement.
    Which IFC class the geometry ends up representing is decided elsewhere,
    and turning this into ``IfcRepresentationItem`` is the step after it.

    ``kind`` names the primitive and ``parameters`` carries the values that
    primitive's own signature declared — the three orthogonal dimensions of
    a box, the radius, length and extrusion direction of a cylinder, the
    radius of a sphere.
    """

    BOX_KIND: ClassVar[str] = "box"
    CYLINDER_KIND: ClassVar[str] = "cylinder"
    SPHERE_KIND: ClassVar[str] = "sphere"

    KIND_KEY: ClassVar[str] = "kind"
    PARAMETERS_KEY: ClassVar[str] = "parameters"

    kind: str
    parameters: Tuple[Tuple[str, Any], ...]

    def to_dict(self) -> Dict[str, Any]:
        """
        Return the serializable form of this definition.
        """
        return {
            self.KIND_KEY: self.kind,
            self.PARAMETERS_KEY: list(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["GeometryDefinition"]:
        """
        Rebuild a definition from its serializable form.

        Invalid structures return ``None`` so every caller uses the same
        decoding rule instead of maintaining its own almost-identical parser.
        """
        kind: Any = data.get(cls.KIND_KEY)
        parameters_raw: Any = data.get(cls.PARAMETERS_KEY)
        if not isinstance(kind, str) or not kind:
            return None
        if not isinstance(parameters_raw, (list, tuple)):
            return None

        parameters = []
        for pair in parameters_raw:
            if (
                not isinstance(pair, (list, tuple))
                or len(pair) != 2
                or not isinstance(pair[0], str)
            ):
                return None
            parameters.append((pair[0], pair[1]))

        return cls(kind=kind, parameters=tuple(parameters))
