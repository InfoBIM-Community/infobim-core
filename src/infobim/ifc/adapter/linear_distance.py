"""Linear distances between IFC bounding-volume annotation centers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import ifcopenshell.util.placement
import ifcopenshell.util.unit
import numpy as np

from infobim.ifc.adapter.bounding_volume import BoundingVolumeService


Point3D = Tuple[float, float, float]


class LinearDistanceMode(str, Enum):
    """Supported interpretations of the vector between two volume centers."""

    STRAIGHT_LINE = "STRAIGHT_LINE"
    PARALLEL_PLANES = "PARALLEL_PLANES"


@dataclass(frozen=True)
class BoundingVolumeCenter:
    annotation_global_id: str
    shape_kind: str
    point: Point3D


@dataclass(frozen=True)
class LinearDistanceMeasurement:
    first: BoundingVolumeCenter
    second: BoundingVolumeCenter
    mode: LinearDistanceMode
    axis: Optional[str]
    vector: Point3D
    distance: float
    signed_distance: Optional[float]
    plane_normal: Optional[Point3D]
    project_unit_scale_to_si: float


class BoundingVolumeCenterRepository:
    """Resolve geometric centers from InfoBIM bounding-volume annotations."""

    SUPPORTED_ITEMS = (
        "IfcBoundingBox",
        "IfcRightCircularCylinder",
        "IfcSphere",
    )

    def __init__(self, model: Any) -> None:
        self._model = model

    def get(self, global_id: str) -> BoundingVolumeCenter:
        try:
            annotation: Any = self._model.by_guid(global_id)
        except RuntimeError as error:
            raise ValueError(
                f"No IFC annotation with GlobalId '{global_id}' was found."
            ) from error
        if annotation is None or not annotation.is_a("IfcAnnotation"):
            raise ValueError(
                f"GlobalId '{global_id}' does not identify an IfcAnnotation."
            )
        if str(getattr(annotation, "ObjectType", "") or "") != (
            BoundingVolumeService.OBJECT_TYPE
        ):
            raise ValueError(
                f"IfcAnnotation '{global_id}' is not an InfoBIM bounding volume."
            )
        placement: Any = getattr(annotation, "ObjectPlacement", None)
        if placement is None or not placement.is_a("IfcLocalPlacement"):
            raise ValueError(
                f"Bounding-volume annotation '{global_id}' has no IfcLocalPlacement."
            )

        item: Any = self._single_supported_item(annotation)
        local_center: Point3D = self._local_center(item)
        placement_matrix: Any = np.asarray(
            ifcopenshell.util.placement.get_local_placement(placement), dtype=float
        )
        local_homogeneous: Any = np.array((*local_center, 1.0), dtype=float)
        world: Any = placement_matrix @ local_homogeneous
        return BoundingVolumeCenter(
            annotation_global_id=str(annotation.GlobalId),
            shape_kind=str(item.is_a()),
            point=tuple(float(value) for value in world[:3]),  # type: ignore[arg-type]
        )

    def _single_supported_item(self, annotation: Any) -> Any:
        product_shape: Any = getattr(annotation, "Representation", None)
        if product_shape is None or not product_shape.is_a("IfcProductDefinitionShape"):
            raise ValueError(
                f"Bounding-volume annotation '{annotation.GlobalId}' has no product shape."
            )
        items: List[Any] = [
            item
            for representation in product_shape.Representations or ()
            for item in representation.Items or ()
            if any(item.is_a(ifc_class) for ifc_class in self.SUPPORTED_ITEMS)
        ]
        if len(items) != 1:
            raise ValueError(
                f"Bounding-volume annotation '{annotation.GlobalId}' must contain "
                "exactly one supported bounding representation item."
            )
        return items[0]

    def _local_center(self, item: Any) -> Point3D:
        if item.is_a("IfcBoundingBox"):
            corner: Tuple[float, ...] = tuple(
                float(value) for value in item.Corner.Coordinates
            )
            if len(corner) != 3:
                raise ValueError("IfcBoundingBox.Corner must be three-dimensional.")
            return (
                corner[0] + float(item.XDim) / 2.0,
                corner[1] + float(item.YDim) / 2.0,
                corner[2] + float(item.ZDim) / 2.0,
            )

        item_matrix: Any = np.asarray(
            ifcopenshell.util.placement.get_axis2placement(item.Position), dtype=float
        )
        if item.is_a("IfcRightCircularCylinder"):
            primitive_center: Any = np.array(
                (0.0, 0.0, float(item.Height) / 2.0, 1.0), dtype=float
            )
        else:
            primitive_center = np.array((0.0, 0.0, 0.0, 1.0), dtype=float)
        center: Any = item_matrix @ primitive_center
        return tuple(float(value) for value in center[:3])  # type: ignore[return-value]


class BoundingVolumeLinearDistanceService:
    """Calculate a center-to-center distance in one of two explicit modes."""

    AXIS_INDEX: Dict[str, int] = {"x": 0, "y": 1, "z": 2}
    AXIS_NORMAL: Dict[str, Point3D] = {
        "x": (1.0, 0.0, 0.0),
        "y": (0.0, 1.0, 0.0),
        "z": (0.0, 0.0, 1.0),
    }

    def __init__(self, model: Any) -> None:
        self._model = model
        self._centers = BoundingVolumeCenterRepository(model)

    def measure(
        self,
        first_global_id: str,
        second_global_id: str,
        mode: LinearDistanceMode,
        axis: Optional[str],
    ) -> LinearDistanceMeasurement:
        if first_global_id == second_global_id:
            raise ValueError("The two bounding-volume GlobalIds must be different.")
        normalized_axis: Optional[str] = (
            None if axis is None else str(axis).strip().lower()
        )
        if mode is LinearDistanceMode.STRAIGHT_LINE and normalized_axis is not None:
            raise ValueError("'axis' is not accepted for STRAIGHT_LINE measurement.")
        if mode is LinearDistanceMode.PARALLEL_PLANES and normalized_axis not in (
            self.AXIS_INDEX
        ):
            raise ValueError(
                "'axis' must be one of 'x', 'y' or 'z' for PARALLEL_PLANES measurement."
            )

        first: BoundingVolumeCenter = self._centers.get(first_global_id)
        second: BoundingVolumeCenter = self._centers.get(second_global_id)
        vector_array: Any = np.asarray(second.point) - np.asarray(first.point)
        vector: Point3D = tuple(
            float(value) for value in vector_array
        )  # type: ignore[assignment]
        signed_distance: Optional[float] = None
        plane_normal: Optional[Point3D] = None
        if mode is LinearDistanceMode.STRAIGHT_LINE:
            distance: float = float(np.linalg.norm(vector_array))
        else:
            axis_key: str = str(normalized_axis)
            signed_distance = float(vector_array[self.AXIS_INDEX[axis_key]])
            distance = abs(signed_distance)
            plane_normal = self.AXIS_NORMAL[axis_key]

        unit_scale: float = float(
            ifcopenshell.util.unit.calculate_unit_scale(self._model, "LENGTHUNIT")
        )
        return LinearDistanceMeasurement(
            first=first,
            second=second,
            mode=mode,
            axis=normalized_axis,
            vector=vector,
            distance=distance,
            signed_distance=signed_distance,
            plane_normal=plane_normal,
            project_unit_scale_to_si=unit_scale,
        )
