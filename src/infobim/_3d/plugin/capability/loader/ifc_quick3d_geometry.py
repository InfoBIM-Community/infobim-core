from typing import Any, ClassVar, Dict, List, Optional
import os

import ifcopenshell
import ifcopenshell.geom

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim._3d.adapter.quick3d import IfcElementGeometry


class IfcQuick3DGeometryCapability(DataLoaderCapability):
    """
    Triangulate the IFC model in the context into one Qt Quick 3D geometry
    per element.

    The shapes come out of IfcOpenShell in world coordinates, so every
    element's geometry is placed on its own, with unwelded vertices so each
    face carries its own normals. Each geometry keeps the GlobalId, Name
    and IFC type of the element it draws. Opening elements are the voids
    already subtracted from their hosts, not something to draw, and an
    element the reader builds no triangles for gets no geometry.
    """

    EXCLUDED_TYPES: ClassVar[List[str]] = ["IfcOpeningElement"]

    MODEL_KEY: ClassVar[str] = "ifc_model"
    GEOMETRIES_KEY: ClassVar[str] = "ifc_quick3d_geometries"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._3d.plugin.capability.loader.ifc_quick3d_geometry",
        version="1.0.0",
        name="IFC Qt Quick 3D Geometry",
        description=(
            "Triangulate the IFC model in the context with IfcOpenShell into "
            "one QQuick3DGeometry per element, keeping its GlobalId, Name and "
            "IFC type."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "3d", "ifc", "geometry", "qt", "read-only"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                MODEL_KEY: {"type": ifcopenshell.file, "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                GEOMETRIES_KEY: {"type": list, "required": True},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "IFC Qt Quick 3D Geometry"

    def description(self, lang: str = "en") -> str:
        return "Creates one Qt Quick 3D geometry per IFC element."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        model: ifcopenshell.file = context.get_parameter_value(self.MODEL_KEY)
        geometries: List[IfcElementGeometry] = self._geometries(model)
        if not geometries:
            raise ValueError("The IFC model has no element with geometry to show.")

        context.set_parameter_value(self.GEOMETRIES_KEY, geometries)
        return {self.GEOMETRIES_KEY: geometries}

    @classmethod
    def _geometries(cls, model: ifcopenshell.file) -> List[IfcElementGeometry]:
        settings: Any = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        settings.set("weld-vertices", False)

        excluded: List[Any] = [
            element
            for ifc_type in cls.EXCLUDED_TYPES
            for element in model.by_type(ifc_type)
        ]
        iterator: Any = ifcopenshell.geom.iterator(
            settings,
            model,
            os.cpu_count(),
            exclude=excluded,
        )
        geometries: List[IfcElementGeometry] = []
        if not iterator.initialize():
            return geometries

        while True:
            shape: Any = iterator.get()
            geometry: Optional[IfcElementGeometry] = cls._geometry_of(model, shape)
            if geometry is not None:
                geometries.append(geometry)
            if not iterator.next():
                return geometries

    @classmethod
    def _geometry_of(
        cls,
        model: ifcopenshell.file,
        shape: Any,
    ) -> Optional[IfcElementGeometry]:
        vertices: List[float] = [float(value) for value in shape.geometry.verts]
        indices: List[int] = [int(value) for value in shape.geometry.faces]
        if not vertices or not indices:
            return None

        normals: List[float] = [float(value) for value in shape.geometry.normals]
        element: Any = model.by_guid(shape.guid)
        return IfcElementGeometry(
            global_id=str(shape.guid),
            name=cls._name_of(element),
            ifc_type=str(element.is_a()),
            vertices=vertices,
            indices=indices,
            normals=normals if len(normals) == len(vertices) else None,
        )

    @staticmethod
    def _name_of(element: Any) -> str:
        """Return what the element is called, or what it is when unnamed."""
        name: Any = element.Name
        if isinstance(name, str) and name.strip():
            return name.strip()

        return str(element.is_a())
