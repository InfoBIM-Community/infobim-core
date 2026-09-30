from typing import ClassVar, Dict, List, Optional, Tuple

from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.dict.domain.model.definition import GeometryDescription
from infobim.dict.domain.exception.dictionary import (
    DictionaryDefinitionInvalidError,
)


class DictionaryGeometryTranslator:
    """
    Says a dictionary's shape in the terms the creation flow works in.

    A dictionary describes a shape in X3D — a primitive and the values
    pinned to that primitive's own properties — and the flow that creates
    geometry works with a ``GeometryDefinition``, which names a primitive
    of its own and the parameters that primitive's signature declares.
    The two say the same shapes and call them different things, so
    something has to translate, and this is it: one place, so a
    dictionary's cylinder and a ``--cylinder`` command's cylinder end up
    as the same definition and are created by the same responsibility.

    Which X3D primitive is which is a declared pair, never a rule over
    spelling. A primitive nobody registered is reported as unsupported,
    naming what is: an entry may legitimately describe a shape this
    runtime cannot build yet, and building the wrong one instead would
    put a solid nobody asked for in the model.

    An axis is not something X3D's cylinder carries, and the dictionary
    states none, so one is supplied: the project's own up. That is the
    contract of this translation and not a value invented to cover an
    absence — a cylinder described by radius and height alone is a
    cylinder standing upright, which is what a toilet pan, a column or a
    pipe riser described that way means.
    """

    CYLINDER_PRIMITIVE: ClassVar[str] = "Cylinder"
    SPHERE_PRIMITIVE: ClassVar[str] = "Sphere"

    PRIMITIVES: ClassVar[Dict[str, Tuple[str, Tuple[str, ...]]]] = {
        CYLINDER_PRIMITIVE: (
            GeometryDefinition.CYLINDER_KIND,
            ("radius", "height"),
        ),
        SPHERE_PRIMITIVE: (GeometryDefinition.SPHERE_KIND, ("radius",)),
    }

    UPRIGHT_AXIS: ClassVar[Tuple[Tuple[str, float], ...]] = (
        ("direction_x", 0.0),
        ("direction_y", 0.0),
        ("direction_z", 1.0),
    )

    AXIS_PRIMITIVES: ClassVar[Tuple[str, ...]] = (CYLINDER_PRIMITIVE,)

    @classmethod
    def translate(cls, description: GeometryDescription) -> GeometryDefinition:
        """
        Return the shape the entry described, as this flow's definition.
        """
        registered: Optional[Tuple[str, Tuple[str, ...]]] = cls.PRIMITIVES.get(
            description.primitive
        )
        if registered is None:
            raise DictionaryDefinitionInvalidError(
                f"The dictionary describes the element as an X3D "
                f"'{description.primitive}', which this runtime does not "
                f"create yet. It creates: "
                f"{', '.join(sorted(cls.PRIMITIVES))}."
            )

        kind: str = registered[0]
        stated: Dict[str, float] = dict(description.parameters)
        parameters: List[Tuple[str, float]] = []

        name: str
        for name in registered[1]:
            if name not in stated:
                raise DictionaryDefinitionInvalidError(
                    f"The dictionary describes an X3D "
                    f"'{description.primitive}' without stating its {name}, "
                    f"which a {kind} is not defined without."
                )

            parameters.append((name, stated[name]))

        if description.primitive in cls.AXIS_PRIMITIVES:
            parameters.extend(cls.UPRIGHT_AXIS)

        return GeometryDefinition(kind=kind, parameters=tuple(parameters))
