"""Shared mechanics for IFC positioning capabilities.

All public numeric inputs handled here are expressed in the IFC project's
declared length unit.  No implicit metre conversion is performed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.atomic_file import AtomicFileWriter
from ontobdc.shared.adapter.capability import TransactionCapability


Point3D = Tuple[float, float, float]


class PositioningCapabilityBase(TransactionCapability):
    """Common presentation and execution helpers for positioning plugins."""

    def label(self, lang: str = "en") -> str:
        return str(self.METADATA.name)

    def description(self, lang: str = "en") -> str:
        return str(self.METADATA.description)


class PositioningSupport:
    """Stateless IFC positioning operations shared by the four plugins."""

    AXES = ("x", "y", "z")
    EPSILON = 1.0e-9

    @staticmethod
    def open_target(context: CliContextPort) -> Tuple[Path, Any, Any]:
        import ifcopenshell

        ifc_path = Path(str(context.get_parameter_value("ifc_path"))).expanduser().resolve()
        if not ifc_path.is_file():
            raise ValueError(f"IFC file does not exist: {ifc_path}")

        global_id = str(context.get_parameter_value("element_global_id")).strip()
        if not global_id:
            raise ValueError("'element_global_id' is required.")

        model = ifcopenshell.open(str(ifc_path))
        try:
            target = model.by_guid(global_id)
        except RuntimeError as exc:
            raise ValueError(f"No IFC element with GlobalId '{global_id}' was found.") from exc
        if target is None:
            raise ValueError(f"No IFC element with GlobalId '{global_id}' was found.")
        return ifc_path, model, target

    @classmethod
    def partial_coordinates(cls, context: CliContextPort) -> Dict[str, float]:
        values = {
            axis: float(context.get_parameter_value(axis))
            for axis in cls.AXES
            if context.has_parameter(axis)
        }
        if not values:
            raise ValueError("At least one of 'x', 'y' or 'z' is required.")
        return values

    @staticmethod
    def merge_coordinates(current: Point3D, values: Dict[str, float]) -> Point3D:
        indexes = {"x": 0, "y": 1, "z": 2}
        merged = list(current)
        for axis, value in values.items():
            merged[indexes[axis]] = float(value)
        return tuple(merged)  # type: ignore[return-value]

    @staticmethod
    def project_unit_scale_to_si(model: Any) -> float:
        import ifcopenshell.util.unit

        return float(ifcopenshell.util.unit.calculate_unit_scale(model, "LENGTHUNIT"))

    @staticmethod
    def write(ifc_path: Path, model: Any) -> None:
        AtomicFileWriter.write(ifc_path, lambda temporary: model.write(str(temporary)))

    @staticmethod
    def placement_matrix(target: Any) -> Any:
        import ifcopenshell.util.placement

        placement = getattr(target, "ObjectPlacement", None)
        if placement is None or not placement.is_a("IfcLocalPlacement"):
            raise ValueError(
                f"Element '{getattr(target, 'GlobalId', '')}' does not have an "
                "IfcLocalPlacement."
            )
        return ifcopenshell.util.placement.get_local_placement(placement)

    @classmethod
    def move(cls, model: Any, target: Any, offsets: Dict[str, float]) -> Tuple[Point3D, Point3D]:
        import ifcopenshell.api.geometry
        import numpy as np

        matrix = np.array(cls.placement_matrix(target), dtype=float)
        old_point: Point3D = tuple(float(value) for value in matrix[:3, 3])  # type: ignore[assignment]
        matrix[0, 3] += float(offsets.get("x", 0.0))
        matrix[1, 3] += float(offsets.get("y", 0.0))
        matrix[2, 3] += float(offsets.get("z", 0.0))
        ifcopenshell.api.geometry.edit_object_placement(
            model,
            product=target,
            matrix=matrix,
            is_si=False,
            should_transform_children=False,
        )
        new_point: Point3D = tuple(float(value) for value in matrix[:3, 3])  # type: ignore[assignment]
        return old_point, new_point

    @staticmethod
    def linear_solid(target: Any) -> Any:
        representation = getattr(target, "Representation", None)
        if representation is None:
            raise ValueError("The target element has no geometric representation.")

        solids = []
        for shape in representation.Representations or ():
            if str(getattr(shape, "RepresentationIdentifier", "") or "").lower() != "body":
                continue
            for item in shape.Items or ():
                if item.is_a("IfcExtrudedAreaSolid"):
                    solids.append(item)
        if len(solids) != 1:
            raise ValueError(
                "A linear positioning capability requires exactly one "
                "IfcExtrudedAreaSolid in the Body representation."
            )
        return solids[0]

    @classmethod
    def endpoints(cls, target: Any, solid: Any | None = None) -> Tuple[Point3D, Point3D, Point3D]:
        import ifcopenshell.util.placement
        import numpy as np

        linear_solid = solid or cls.linear_solid(target)
        product_matrix = np.array(cls.placement_matrix(target), dtype=float)
        solid_matrix = np.array(
            ifcopenshell.util.placement.get_axis2placement(linear_solid.Position),
            dtype=float,
        )
        combined = product_matrix @ solid_matrix
        extrusion = np.array(linear_solid.ExtrudedDirection.DirectionRatios, dtype=float)
        world_direction = combined[:3, :3] @ extrusion
        norm = float(np.linalg.norm(world_direction))
        if norm <= cls.EPSILON:
            raise ValueError("The linear element has a zero extrusion direction.")
        world_direction /= norm
        start_array = combined[:3, 3]
        end_array = start_array + world_direction * float(linear_solid.Depth)
        start: Point3D = tuple(float(value) for value in start_array)  # type: ignore[assignment]
        end: Point3D = tuple(float(value) for value in end_array)  # type: ignore[assignment]
        direction: Point3D = tuple(float(value) for value in world_direction)  # type: ignore[assignment]
        return start, end, direction

    @classmethod
    def set_endpoints(cls, model: Any, target: Any, start: Point3D, end: Point3D) -> float:
        import numpy as np

        solid = cls.linear_solid(target)
        product_matrix = np.array(cls.placement_matrix(target), dtype=float)
        inverse_product = np.linalg.inv(product_matrix)
        start_world = np.array(start, dtype=float)
        end_world = np.array(end, dtype=float)
        vector_world = end_world - start_world
        length = float(np.linalg.norm(vector_world))
        if length <= cls.EPSILON:
            raise ValueError("Linear element start and end points cannot be equal.")

        local_start = (inverse_product @ np.append(start_world, 1.0))[:3]
        local_direction = inverse_product[:3, :3] @ (vector_world / length)
        local_direction /= float(np.linalg.norm(local_direction))
        reference = cls.perpendicular_reference(local_direction)

        point = model.create_entity(
            "IfcCartesianPoint", Coordinates=tuple(float(value) for value in local_start)
        )
        axis = model.create_entity(
            "IfcDirection", DirectionRatios=tuple(float(value) for value in local_direction)
        )
        ref_direction = model.create_entity(
            "IfcDirection", DirectionRatios=tuple(float(value) for value in reference)
        )
        solid.Position = model.create_entity(
            "IfcAxis2Placement3D",
            Location=point,
            Axis=axis,
            RefDirection=ref_direction,
        )
        solid.ExtrudedDirection = model.create_entity(
            "IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)
        )
        solid.Depth = length
        return length

    @staticmethod
    def perpendicular_reference(direction: Iterable[float]) -> Point3D:
        import numpy as np

        axis = np.array(tuple(direction), dtype=float)
        candidates = (
            np.array((1.0, 0.0, 0.0)),
            np.array((0.0, 1.0, 0.0)),
            np.array((0.0, 0.0, 1.0)),
        )
        reference = min(candidates, key=lambda candidate: abs(float(np.dot(axis, candidate))))
        reference -= axis * float(np.dot(axis, reference))
        reference /= float(np.linalg.norm(reference))
        return tuple(float(value) for value in reference)  # type: ignore[return-value]

    @classmethod
    def ensure_forward(cls, start: Point3D, end: Point3D, direction: Point3D) -> None:
        import numpy as np

        projection = float(
            np.dot(np.array(end, dtype=float) - np.array(start, dtype=float), direction)
        )
        if projection <= cls.EPSILON:
            raise ValueError(
                "The linear element end point must remain after its start point."
            )

