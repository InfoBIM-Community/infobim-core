from pathlib import Path
import math
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.adapter.geometry_state import GeometricProductState
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)


class ShapeRepresentationCreatedCapability(TransactionCapability):
    """
    Creates the IFC shape representation of the created geometry.

    It wraps the item where that item was created: in the state file of
    the product being assembled, never in the model the project
    federates. A representation whose item lives in another file is not
    something that file may reference, and a representation no product
    owns is not something the federated model should carry.

    What follows it — how the representation is assigned to a product,
    and when the assembled product enters the federated model — is not
    part of this contract and is not invented here. The states after
    this one are specified before they are added.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "shape_representation_created"
        ),
        version="0.1.0",
        name="Shape Representation Created",
        description="Create the shape representation of the created geometry.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometric-product", "shape_representation_created"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": "The InfoBIM project the product belongs to.",
                },
                "title": {
                    "type": "string",
                    "required": True,
                    "description": "The title of the product being assembled.",
                },
                "geometry": {
                    "type": "object",
                    "required": True,
                    "description": (
                        "The GeometryDefinition a geometry command produced "
                        "for this run."
                    ),
                    "uri": "org.infobim.ifc.geometry",
                },
            },
        },
        log_message={
            "info": {
                "en": "The shape representation of the geometry was created.",
            },
            "debug_entry": {
                "en": "Creating the shape representation of the created geometry.",
            },
        },
    )

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    TITLE_KEY: ClassVar[str] = "title"
    GEOMETRY_KEY: ClassVar[str] = "geometry"
    GEOMETRY_ITEM_KEY: ClassVar[str] = "geometry_item"
    STEP_ELEMENTS_KEY: ClassVar[str] = "step_elements"
    SHAPE_REPRESENTATION_KEY: ClassVar[str] = "shape_representation"
    STATE_PATH_KEY: ClassVar[str] = "geometry_state_path"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"

    GEOMETRY_ITEM_KIND_MAP: ClassVar[Dict[str, str]] = {
        GeometryDefinition.BOX_KIND: "SweptSolid",
        GeometryDefinition.CYLINDER_KIND: "CSG",
        GeometryDefinition.SPHERE_KIND: "CSG",
    }

    TESSELLATION_TYPE: ClassVar[str] = "Tessellation"
    TESSELLATION_CYLINDER_SEGMENTS: ClassVar[int] = 48
    TESSELLATION_SPHERE_SUBDIVISIONS: ClassVar[int] = 3

    KIND_KEY: ClassVar[str] = "kind"
    PARAMETERS_KEY: ClassVar[str] = "parameters"

    BODY_IDENTIFIER: ClassVar[str] = "Body"
    MODEL_TYPE: ClassVar[str] = "Model"
    MODEL_VIEW: ClassVar[str] = "MODEL_VIEW"
    SPACE_DIMENSION: ClassVar[int] = 3
    PRECISION: ClassVar[float] = 1e-5

    def label(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.SHAPE_REPRESENTATION_CREATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.SHAPE_REPRESENTATION_CREATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        geometry_kind: str = self._geometry_kind(context)
        geometry_definition: Optional[GeometryDefinition] = self._definition(context)
        state_path: Path = GeometricProductState.path_of(
            self._container_path(context),
            self._title(context),
            GeometricProductState.GEOMETRY_FILE_NAME,
        )
        model: Any = GeometricProductState.read(state_path)

        # Resolved in this model, not in one opened beside it: an entity
        # belongs to the file it was read from, so an item taken from
        # another handle is not something this file may reference.
        csg_item_entity: Optional[Any] = None
        if context.has_parameter(self.GEOMETRY_ITEM_KEY):
            reference: Any = context.get_parameter_value(self.GEOMETRY_ITEM_KEY)
            csg_item_entity = self._entity_of(model, reference)
        if csg_item_entity is None and context.has_parameter(self.STEP_ELEMENTS_KEY):
            elements: Any = context.get_parameter_value(self.STEP_ELEMENTS_KEY)
            if isinstance(elements, (list, tuple)):
                for element in reversed(elements):
                    entity = self._entity_of(model, element)
                    if entity is not None:
                        csg_item_entity = entity
                        break

        body_context: Any = self._body_subcontext(model)

        # Write an IfcTriangulatedFaceSet for known primitive kinds so
        # downstream viewers never depend on an optional CSG-capable
        # geometry engine: the default ifcopenshell.geom.iterator skips
        # IfcRightCircularCylinder, IfcBlock and IfcSphere items
        # entirely, which would cause `infobim 3d` to produce zero IFCX
        # meshes for any product assembled out of these primitives. The
        # original CSG item is left alive in the state file alongside
        # the tessellated representation so other consumers that DO
        # understand primitives keep reading them if they want to.
        representation_type: str = self.GEOMETRY_ITEM_KIND_MAP.get(
            geometry_kind, "SweptSolid"
        )
        items: List[Any] = []
        tessellated: Optional[Any] = self._tessellated_representation_item(
            model, geometry_kind, geometry_definition, csg_item_entity
        )
        if tessellated is not None:
            items = [tessellated]
            representation_type = self.TESSELLATION_TYPE
        elif csg_item_entity is not None:
            items = [csg_item_entity]
        else:
            raise IfcCreationError(
                "Neither a tessellated nor a primitive CSG geometry item "
                "could be resolved for this product; the representation "
                "of its shape cannot be stated."
            )

        shape: Any = model.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=body_context,
            RepresentationIdentifier=self.BODY_IDENTIFIER,
            RepresentationType=representation_type,
            Items=items,
        )

        shape_reference: str = str(shape.id())
        GeometricProductState.write(model, state_path)

        context.set_parameter_value(self.SHAPE_REPRESENTATION_KEY, shape_reference)

        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductCreateProcessState.SHAPE_REPRESENTATION_CREATED
            ),
            self.SHAPE_REPRESENTATION_KEY: shape_reference,
            self.STATE_PATH_KEY: str(state_path),
        }

    @classmethod
    def _definition(cls, context: CliContextPort) -> Optional[GeometryDefinition]:
        """Return the GeometryDefinition carried by the context, if any."""
        if not context.has_parameter(cls.GEOMETRY_KEY):
            return None
        value: Any = context.get_parameter_value(cls.GEOMETRY_KEY)
        if isinstance(value, GeometryDefinition):
            return value
        if isinstance(value, dict):
            kind: Any = value.get(cls.KIND_KEY)
            parameters: Any = value.get(cls.PARAMETERS_KEY)
            if isinstance(kind, str) and isinstance(parameters, dict):
                return GeometryDefinition(str(kind), dict(parameters))
        return None

    @classmethod
    def _tessellated_representation_item(
        cls,
        model: Any,
        geometry_kind: str,
        definition: Optional[GeometryDefinition],
        csg_item: Optional[Any],
    ) -> Optional[Any]:
        """
        Return a tessellated ``IfcTriangulatedFaceSet`` representing
        the same geometry the CSG primitive (``IfcBlock`` /
        ``IfcRightCircularCylinder`` / ``IfcSphere``) describes, or
        ``None`` when the kind is unknown or no parameters are
        available to triangulate from.

        Preferring parameters over inspecting the CSG instance keeps
        this side-effect free: every primitive the dictionary pipeline
        produces is parametrised already, and deriving faces from those
        parameters is deterministic and engine-independent. Reading
        dimensions from ``csg_item`` is a last-resort fallback for
        callers that carry the original primitive but no typed
        ``GeometryDefinition``.
        """
        coords_list: List[List[float]]
        faces_list: List[List[int]]
        if geometry_kind == GeometryDefinition.BOX_KIND:
            x, y, z = cls._box_dimensions(definition, csg_item)
            coords_list, faces_list = cls._triangulate_box(x, y, z)
        elif geometry_kind == GeometryDefinition.CYLINDER_KIND:
            radius, height, segments, axis = cls._cylinder_params(
                definition, csg_item
            )
            coords_list, faces_list = cls._triangulate_cylinder(
                radius, height, segments, axis
            )
        elif geometry_kind == GeometryDefinition.SPHERE_KIND:
            radius = cls._sphere_radius(definition, csg_item)
            coords_list, faces_list = cls._triangulate_sphere(
                radius, cls.TESSELLATION_SPHERE_SUBDIVISIONS
            )
        else:
            return None

        # Lift values into the IFC graph of the product file.
        coords_model: List[Any] = [
            model.create_entity("IfcCartesianPoint", Coordinates=[float(v) for v in p])
            for p in coords_list
        ]
        coord_list: Any = model.create_entity(
            "IfcCartesianPointList3d", CoordList=[c.Coordinates for c in coords_model]
        )
        # Indexed faces: IFC is 1-based on IfcTriangulatedFaceSet.CoordIndex
        coord_index: List[List[int]] = [
            [int(idx + 1) for idx in face] for face in faces_list
        ]
        return model.create_entity(
            "IfcTriangulatedFaceSet",
            Coordinates=coord_list,
            CoordIndex=coord_index,
            Closed=True,
        )

    @classmethod
    def _box_dimensions(
        cls,
        definition: Optional[GeometryDefinition],
        csg_item: Optional[Any],
    ) -> Tuple[float, float, float]:
        if definition is not None:
            params: Dict[str, Any] = dict(definition.parameters)
            try:
                return (
                    float(params["x_length"]),
                    float(params["y_length"]),
                    float(params["z_length"]),
                )
            except (KeyError, TypeError, ValueError):
                pass
        if csg_item is not None and getattr(csg_item, "is_a", lambda: "")() == "IfcBlock":
            try:
                return (
                    float(getattr(csg_item, "XLength")),
                    float(getattr(csg_item, "YLength")),
                    float(getattr(csg_item, "ZLength")),
                )
            except Exception:
                pass
        raise IfcCreationError(
            "IfcBlock (Box) geometry requires numeric x_length, y_length "
            "and z_length; the assembly did not carry usable dimensions."
        )

    @classmethod
    def _cylinder_params(
        cls,
        definition: Optional[GeometryDefinition],
        csg_item: Optional[Any],
    ) -> Tuple[float, float, int, List[float]]:
        radius: float
        height: float
        direction: List[float] = [0.0, 0.0, 1.0]
        if definition is not None:
            params: Dict[str, Any] = dict(definition.parameters)
            try:
                radius = float(params["radius"])
                height = float(params["height"])
                direction = [float(v) for v in params.get(
                    "direction", direction
                )]
                return radius, height, cls.TESSELLATION_CYLINDER_SEGMENTS, direction
            except (KeyError, TypeError, ValueError):
                pass
        if (
            csg_item is not None
            and getattr(csg_item, "is_a", lambda: "")() == "IfcRightCircularCylinder"
        ):
            try:
                radius = float(getattr(csg_item, "Radius"))
                height = float(getattr(csg_item, "Height"))
                position = getattr(csg_item, "Position", None)
                axis_entity = getattr(position, "Axis", None)
                if axis_entity is not None:
                    ratios = getattr(axis_entity, "DirectionRatios", None)
                    if ratios is not None:
                        direction = [float(v) for v in ratios]
                return radius, height, cls.TESSELLATION_CYLINDER_SEGMENTS, direction
            except Exception:
                pass
        raise IfcCreationError(
            "IfcRightCircularCylinder geometry requires numeric radius "
            "and height; the assembly did not carry usable dimensions."
        )

    @classmethod
    def _sphere_radius(
        cls,
        definition: Optional[GeometryDefinition],
        csg_item: Optional[Any],
    ) -> float:
        if definition is not None:
            params: Dict[str, Any] = dict(definition.parameters)
            try:
                return float(params["radius"])
            except (KeyError, TypeError, ValueError):
                pass
        if csg_item is not None and getattr(csg_item, "is_a", lambda: "")() == "IfcSphere":
            try:
                return float(getattr(csg_item, "Radius"))
            except Exception:
                pass
        raise IfcCreationError(
            "IfcSphere geometry requires a numeric radius; the assembly "
            "did not carry usable dimensions."
        )

    @staticmethod
    def _triangulate_box(
        x_length: float, y_length: float, z_length: float
    ) -> Tuple[List[List[float]], List[List[int]]]:
        """Return (vertices, faces) of an axis-aligned box.

        The box is positioned like the IfcBlock primitive produced by
        the geometry-creation capabilities: one corner at the origin,
        the opposite one at ``(x_length, y_length, z_length)``.
        """
        hx: float = 0.0
        hy: float = 0.0
        hz: float = 0.0
        X: float = float(x_length)
        Y: float = float(y_length)
        Z: float = float(z_length)
        verts: List[List[float]] = [
            [hx, hy, hz],          # 0
            [X, hy, hz],           # 1
            [X, Y, hz],            # 2
            [hx, Y, hz],           # 3
            [hx, hy, Z],           # 4
            [X, hy, Z],            # 5
            [X, Y, Z],             # 6
            [hx, Y, Z],            # 7
        ]
        # Two triangles per face (CCW winding viewed from outside).
        faces: List[List[int]] = [
            [0, 2, 1], [0, 3, 2],      # bottom (-z)
            [4, 5, 6], [4, 6, 7],      # top (+z)
            [0, 1, 5], [0, 5, 4],      # front (-y)
            [2, 3, 7], [2, 7, 6],      # back (+y)
            [0, 7, 3], [0, 4, 7],      # left (-x)
            [1, 2, 6], [1, 6, 5],      # right (+x)
        ]
        return verts, faces

    @staticmethod
    def _triangulate_cylinder(
        radius: float,
        height: float,
        segments: int,
        axis: Iterable[float],
    ) -> Tuple[List[List[float]], List[List[int]]]:
        """Return (vertices, faces) of a cylinder aligned to ``axis``.

        Centered at the origin for the bottom loop, top loop shifted in
        the direction of the unit-normalised ``axis`` by ``height``.
        Bottom cap centre is index ``segments``, top cap centre is index
        ``2 * segments + 1``.
        """
        n: int = max(3, int(segments))
        R: float = float(radius)
        H: float = float(height)

        ax, ay, az = (float(v) for v in axis)
        norm: float = math.sqrt(ax * ax + ay * ay + az * az)
        if norm <= 1e-12:
            ax, ay, az = 0.0, 0.0, 1.0
        else:
            ax /= norm; ay /= norm; az /= norm

        # Perpendicular u, v directions via Gram-Schmidt.
        if abs(az) < 0.9:
            ux, uy, uz = -ay, ax, 0.0
        else:
            ux, uy, uz = 1.0, 0.0, 0.0
        u_norm: float = math.sqrt(ux * ux + uy * uy + uz * uz)
        ux /= u_norm; uy /= u_norm; uz /= u_norm
        vx: float = ay * uz - az * uy
        vy: float = az * ux - ax * uz
        vz: float = ax * uy - ay * ux
        v_norm: float = math.sqrt(vx * vx + vy * vy + vz * vz)
        vx /= v_norm; vy /= v_norm; vz /= v_norm

        # Indices: [0..n-1] bottom loop, [n..2n-1] top loop, [2n] bottom center, [2n+1] top center
        bottom_center_i: int = 2 * n
        top_center_i: int = 2 * n + 1

        verts: List[List[float]] = []
        for i in range(n):
            theta: float = 2.0 * math.pi * i / n
            cos_t: float = math.cos(theta)
            sin_t: float = math.sin(theta)
            x: float = R * (cos_t * ux + sin_t * vx)
            y: float = R * (cos_t * uy + sin_t * vy)
            z: float = R * (cos_t * uz + sin_t * vz)
            verts.append([x, y, z])
        for i in range(n):
            theta = 2.0 * math.pi * i / n
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            x = H * ax + R * (cos_t * ux + sin_t * vx)
            y = H * ay + R * (cos_t * uy + sin_t * vy)
            z = H * az + R * (cos_t * uz + sin_t * vz)
            verts.append([x, y, z])
        verts.append([0.0, 0.0, 0.0])                                  # bottom center
        verts.append([H * ax, H * ay, H * az])                        # top center

        faces: List[List[int]] = []
        # Side quads -> two triangles each
        for i in range(n):
            b1: int = i
            b2: int = (i + 1) % n
            t1: int = n + i
            t2: int = n + (i + 1) % n
            faces.append([b1, b2, t1])
            faces.append([b2, t2, t1])
        # Bottom cap: outward normal = -axis -> triangle from center to bottom loop
        for i in range(n):
            i1 = i
            i2 = (i + 1) % n
            faces.append([bottom_center_i, i2, i1])
        # Top cap: outward normal = +axis
        for i in range(n):
            i1 = n + i
            i2 = n + (i + 1) % n
            faces.append([top_center_i, i1, i2])
        return verts, faces

    @classmethod
    def _triangulate_sphere(
        cls,
        radius: float,
        subdivisions: int,
    ) -> Tuple[List[List[float]], List[List[int]]]:
        """Return (vertices, faces) of a sphere of ``radius`` approximated
        by a subdivided icosahedron.

        The result is guaranteed not to degenerate on zero/negative
        radius: the caller validates dimensions before this helper.
        """
        R: float = max(0.0, float(radius))
        verts: List[List[float]]
        faces: List[List[int]]
        verts, faces = cls._icosahedron()
        for _ in range(max(0, int(subdivisions))):
            verts, faces = cls._subdivide_sphere(verts, faces)
        # Project every vertex onto the sphere of radius R.
        scaled: List[List[float]] = []
        for v in verts:
            x, y, z = float(v[0]), float(v[1]), float(v[2])
            length: float = math.sqrt(x * x + y * y + z * z)
            if length <= 1e-12:
                scaled.append([0.0, 0.0, 0.0])
            else:
                s: float = R / length
                scaled.append([x * s, y * s, z * s])
        return scaled, faces

    @staticmethod
    def _icosahedron() -> Tuple[List[List[float]], List[List[int]]]:
        t: float = (1.0 + math.sqrt(5.0)) / 2.0
        raw: List[List[float]] = [
            [-1.0,  t,  0.0], [ 1.0,  t,  0.0], [-1.0, -t,  0.0], [ 1.0, -t,  0.0],
            [ 0.0, -1.0,  t], [ 0.0,  1.0,  t], [ 0.0, -1.0, -t], [ 0.0,  1.0, -t],
            [ t,  0.0, -1.0], [ t,  0.0,  1.0], [-t,  0.0, -1.0], [-t,  0.0,  1.0],
        ]
        # Normalise unit length so subdivision projection is smooth.
        verts: List[List[float]] = []
        for v in raw:
            x, y, z = float(v[0]), float(v[1]), float(v[2])
            n: float = math.sqrt(x * x + y * y + z * z)
            verts.append([x / n, y / n, z / n])
        faces: List[List[int]] = [
            [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
            [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
            [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
            [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
        ]
        return verts, faces

    @staticmethod
    def _subdivide_sphere(
        verts: List[List[float]], faces: List[List[int]]
    ) -> Tuple[List[List[float]], List[List[int]]]:
        """Split each triangle into 4 new ones, normalising new midpoints."""
        from typing import Dict

        midpoint_cache: Dict[Tuple[int, int], int] = {}

        def mid(a: int, b: int) -> int:
            key: Tuple[int, int] = (a, b) if a < b else (b, a)
            if key in midpoint_cache:
                return midpoint_cache[key]
            va: List[float] = verts[a]
            vb: List[float] = verts[b]
            mx: float = 0.5 * (float(va[0]) + float(vb[0]))
            my: float = 0.5 * (float(va[1]) + float(vb[1]))
            mz: float = 0.5 * (float(va[2]) + float(vb[2]))
            n: float = math.sqrt(mx * mx + my * my + mz * mz)
            if n <= 1e-12:
                verts.append([0.0, 0.0, 0.0])
            else:
                verts.append([mx / n, my / n, mz / n])
            idx: int = len(verts) - 1
            midpoint_cache[key] = idx
            return idx

        new_faces: List[List[int]] = []
        for tri in faces:
            a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
            ab: int = mid(a, b)
            bc: int = mid(b, c)
            ca: int = mid(c, a)
            new_faces.extend([
                [a, ab, ca],
                [b, bc, ab],
                [c, ca, bc],
                [ab, bc, ca],
            ])
        return verts, new_faces

    @classmethod
    def _container_path(cls, context: CliContextPort) -> Path:
        value: Any = context.get_parameter_value(cls.CONTAINER_PATH_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The InfoBIM project is missing from the command context, so "
                "the product being assembled cannot be found."
            )
        return Path(value).expanduser().resolve()

    @classmethod
    def _title(cls, context: CliContextPort) -> str:
        value: Any = context.get_parameter_value(cls.TITLE_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The product title is missing from the command context, so "
                "the product being assembled cannot be found."
            )
        return value.strip()

    @classmethod
    def _geometry_kind(cls, context: CliContextPort) -> str:
        if not context.has_parameter(cls.GEOMETRY_KEY):
            return GeometryDefinition.BOX_KIND
        value: Any = context.get_parameter_value(cls.GEOMETRY_KEY)
        if isinstance(value, GeometryDefinition):
            return value.kind
        if isinstance(value, dict):
            kind: Any = value.get(cls.KIND_KEY)
            if isinstance(kind, str) and kind:
                return str(kind)
        return GeometryDefinition.BOX_KIND

    @classmethod
    def _geometry_item(cls, context: CliContextPort, model: Any) -> Any:
        """
        Return the entity the geometry state created, read from this model.

        The reference the previous state left is the STEP instance number
        of the item it wrote, because a representation item is not rooted
        and has no GlobalId to be addressed by. The list of elements that
        state also leaves is the fallback, read from its end, since the
        item is the last of the entities it created.
        """
        if context.has_parameter(cls.GEOMETRY_ITEM_KEY):
            reference: Any = context.get_parameter_value(cls.GEOMETRY_ITEM_KEY)
            entity: Optional[Any] = cls._entity_of(model, reference)
            if entity is not None:
                return entity

        if context.has_parameter(cls.STEP_ELEMENTS_KEY):
            elements: Any = context.get_parameter_value(cls.STEP_ELEMENTS_KEY)
            if isinstance(elements, (list, tuple)):
                for element in reversed(elements):
                    entity = cls._entity_of(model, element)
                    if entity is not None:
                        return entity

        raise IfcCreationError(
            "No IFC geometry item (IfcBlock, IfcCylinder, IfcSphere...) was "
            "found in the command context; a representation item must exist "
            "before a shape representation can wrap it."
        )

    @staticmethod
    def _entity_of(model: Any, reference: Any) -> Optional[Any]:
        """
        Return the entity a reference names, or None when it names none.

        A STEP instance number addresses any entity of the file, rooted
        or not; a GlobalId addresses only a rooted one. Both are tried,
        because a reference written by another state is read here as what
        it is rather than as what this one expects.
        """
        if not isinstance(reference, str) or not reference.strip():
            return None

        identifier: str = reference.strip()
        if identifier.lstrip("#").isdigit():
            try:
                return model.by_id(int(identifier.lstrip("#")))
            except Exception:
                return None

        try:
            return model.by_guid(identifier)
        except Exception:
            return None

    @classmethod
    def _body_subcontext(cls, model: Any) -> Any:
        """
        Return the Body context the representation hangs from.

        The product is assembled in a file of its own, so the context is
        this file's: the one it already carries, or one created for it.
        Reconciling it with the context of the model the project
        federates belongs to whoever merges the product into that model,
        which is a step after this one.
        """
        subcontexts: List[Any] = [
            subcontext
            for subcontext in model.by_type("IfcGeometricRepresentationSubContext")
            if getattr(subcontext, "ContextIdentifier", None) == cls.BODY_IDENTIFIER
            and getattr(subcontext, "ContextType", None) == cls.MODEL_TYPE
        ]
        if len(subcontexts) > 1:
            raise IfcCreationError(
                f"The product being assembled declares "
                f"{len(subcontexts)} Body/Model representation subcontexts, "
                f"and a representation hangs from exactly one."
            )

        if subcontexts:
            return subcontexts[0]

        return model.create_entity(
            "IfcGeometricRepresentationSubContext",
            ContextIdentifier=cls.BODY_IDENTIFIER,
            ContextType=cls.MODEL_TYPE,
            ParentContext=cls._root_context(model),
            TargetView=cls.MODEL_VIEW,
        )

    @classmethod
    def _root_context(cls, model: Any) -> Any:
        """
        Return the 3D Model context of the product, creating it if absent.
        """
        contexts: List[Any] = [
            candidate
            for candidate in model.by_type("IfcGeometricRepresentationContext")
            if candidate.is_a() == "IfcGeometricRepresentationContext"
            and getattr(candidate, "ContextType", None) == cls.MODEL_TYPE
        ]
        if len(contexts) > 1:
            raise IfcCreationError(
                f"The product being assembled declares {len(contexts)} Model "
                f"representation contexts, and its geometry is measured in "
                f"exactly one."
            )

        if contexts:
            return contexts[0]

        origin: Any = model.create_entity(
            "IfcCartesianPoint",
            Coordinates=(0.0, 0.0, 0.0),
        )
        world_coordinate_system: Any = model.create_entity(
            "IfcAxis2Placement3D",
            Location=origin,
        )

        return model.create_entity(
            "IfcGeometricRepresentationContext",
            ContextType=cls.MODEL_TYPE,
            CoordinateSpaceDimension=cls.SPACE_DIMENSION,
            Precision=cls.PRECISION,
            WorldCoordinateSystem=world_coordinate_system,
        )
