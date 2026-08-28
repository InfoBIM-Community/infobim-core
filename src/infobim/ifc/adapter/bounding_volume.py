"""Compute and attach compact IFC bounding-volume representations."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

import ifcopenshell.geom
import ifcopenshell.api.geometry
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.guid
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.shape
import ifcopenshell.util.unit
import numpy as np


Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]


class BoundingVolumeKind(str, Enum):
    """Supported convex envelopes, in deterministic tie-break order."""

    RECTANGULAR_CUBOID = "RECTANGULAR_CUBOID"
    CYLINDER = "CYLINDER"
    SPHERE = "SPHERE"


@dataclass(frozen=True)
class CircleFit:
    center: Point2D
    radius: float


@dataclass(frozen=True)
class SphereFit:
    center: Point3D
    radius: float


@dataclass(frozen=True)
class BoundingVolumeCandidate:
    kind: BoundingVolumeKind
    volume: float
    parameters: Dict[str, Any]


@dataclass(frozen=True)
class BoundingVolumeSelection:
    selected: BoundingVolumeCandidate
    candidates: Tuple[BoundingVolumeCandidate, ...]
    element_volume: float
    project_unit_scale_to_si: float

    @property
    def extra_volume(self) -> float:
        return max(0.0, self.selected.volume - self.element_volume)

    @property
    def extra_volume_ratio(self) -> float:
        return self.extra_volume / self.element_volume


@dataclass(frozen=True)
class BoundingVolumeRepresentation:
    annotation: Any
    shape_representation: Any
    representation_item: Any
    assignment: Any


class MinimumEnclosingCircle:
    """Deterministic incremental minimum enclosing circle solver."""

    EPSILON = 1.0e-9

    @classmethod
    def fit(cls, points: Sequence[Sequence[float]]) -> CircleFit:
        unique: Any = np.unique(np.asarray(points, dtype=float), axis=0)
        if len(unique) == 0:
            raise ValueError("Cannot fit a circle without geometric vertices.")

        order: Any = np.random.default_rng(0).permutation(len(unique))
        shuffled: Any = unique[order]
        circle: Optional[CircleFit] = None
        for first_index, first in enumerate(shuffled):
            if circle is not None and cls._contains(circle, first):
                continue
            circle = cls._boundary_circle([first])
            for second_index in range(first_index):
                second: Any = shuffled[second_index]
                if cls._contains(circle, second):
                    continue
                circle = cls._boundary_circle([first, second])
                for third_index in range(second_index):
                    third: Any = shuffled[third_index]
                    if cls._contains(circle, third):
                        continue
                    circle = cls._boundary_circle([first, second, third])
        if circle is None:
            raise ValueError("Could not fit a circle around the geometric vertices.")
        return circle

    @classmethod
    def _boundary_circle(cls, boundary: Sequence[Any]) -> CircleFit:
        candidates: List[CircleFit] = []
        for size in range(1, min(3, len(boundary)) + 1):
            for support in itertools.combinations(boundary, size):
                candidate: Optional[CircleFit] = cls._through(support)
                if candidate is not None and all(
                    cls._contains(candidate, point) for point in boundary
                ):
                    candidates.append(candidate)
        if not candidates:
            raise ValueError("The projected geometry cannot define an enclosing circle.")
        return min(candidates, key=lambda candidate: candidate.radius)

    @classmethod
    def _through(cls, support: Sequence[Any]) -> Optional[CircleFit]:
        if len(support) == 1:
            point: Any = support[0]
            return CircleFit((float(point[0]), float(point[1])), 0.0)
        if len(support) == 2:
            first: Any = support[0]
            second: Any = support[1]
            center: Any = (first + second) / 2.0
            return CircleFit(
                (float(center[0]), float(center[1])),
                float(np.linalg.norm(first - center)),
            )

        first = support[0]
        second = support[1]
        third: Any = support[2]
        matrix: Any = 2.0 * np.vstack((second - first, third - first))
        values: Any = np.array(
            (
                float(np.dot(second, second) - np.dot(first, first)),
                float(np.dot(third, third) - np.dot(first, first)),
            )
        )
        if abs(float(np.linalg.det(matrix))) <= cls.EPSILON:
            return None
        center = np.linalg.solve(matrix, values)
        return CircleFit(
            (float(center[0]), float(center[1])),
            float(np.linalg.norm(first - center)),
        )

    @classmethod
    def _contains(cls, circle: CircleFit, point: Any) -> bool:
        center: Any = np.asarray(circle.center, dtype=float)
        tolerance: float = cls.EPSILON * max(1.0, circle.radius)
        return float(np.linalg.norm(np.asarray(point) - center)) <= circle.radius + tolerance


class MinimumEnclosingSphere:
    """Deterministic incremental minimum enclosing sphere solver."""

    EPSILON = 1.0e-9

    @classmethod
    def fit(cls, points: Sequence[Sequence[float]]) -> SphereFit:
        unique: Any = np.unique(np.asarray(points, dtype=float), axis=0)
        if len(unique) == 0:
            raise ValueError("Cannot fit a sphere without geometric vertices.")

        order: Any = np.random.default_rng(0).permutation(len(unique))
        shuffled: Any = unique[order]
        sphere: Optional[SphereFit] = None
        for first_index, first in enumerate(shuffled):
            if sphere is not None and cls._contains(sphere, first):
                continue
            sphere = cls._boundary_sphere([first])
            for second_index in range(first_index):
                second: Any = shuffled[second_index]
                if cls._contains(sphere, second):
                    continue
                sphere = cls._boundary_sphere([first, second])
                for third_index in range(second_index):
                    third: Any = shuffled[third_index]
                    if cls._contains(sphere, third):
                        continue
                    sphere = cls._boundary_sphere([first, second, third])
                    for fourth_index in range(third_index):
                        fourth: Any = shuffled[fourth_index]
                        if cls._contains(sphere, fourth):
                            continue
                        sphere = cls._boundary_sphere(
                            [first, second, third, fourth]
                        )
        if sphere is None:
            raise ValueError("Could not fit a sphere around the geometric vertices.")
        return sphere

    @classmethod
    def _boundary_sphere(cls, boundary: Sequence[Any]) -> SphereFit:
        candidates: List[SphereFit] = []
        for size in range(1, min(4, len(boundary)) + 1):
            for support in itertools.combinations(boundary, size):
                candidate: Optional[SphereFit] = cls._through(support)
                if candidate is not None and all(
                    cls._contains(candidate, point) for point in boundary
                ):
                    candidates.append(candidate)
        if not candidates:
            raise ValueError("The geometry cannot define an enclosing sphere.")
        return min(candidates, key=lambda candidate: candidate.radius)

    @classmethod
    def _through(cls, support: Sequence[Any]) -> Optional[SphereFit]:
        if len(support) == 1:
            point: Any = support[0]
            return SphereFit(
                (float(point[0]), float(point[1]), float(point[2])), 0.0
            )
        if len(support) == 2:
            first: Any = support[0]
            second: Any = support[1]
            center: Any = (first + second) / 2.0
            return SphereFit(
                (float(center[0]), float(center[1]), float(center[2])),
                float(np.linalg.norm(first - center)),
            )
        if len(support) == 3:
            first = support[0]
            second = support[1]
            third: Any = support[2]
            first_second: Any = second - first
            first_third: Any = third - first
            normal: Any = np.cross(first_second, first_third)
            denominator: float = 2.0 * float(np.dot(normal, normal))
            if abs(denominator) <= cls.EPSILON:
                return None
            offset: Any = (
                float(np.dot(first_third, first_third))
                * np.cross(normal, first_second)
                + float(np.dot(first_second, first_second))
                * np.cross(first_third, normal)
            ) / denominator
            center = first + offset
            return SphereFit(
                (float(center[0]), float(center[1]), float(center[2])),
                float(np.linalg.norm(first - center)),
            )

        first = support[0]
        matrix: Any = 2.0 * np.vstack(
            tuple(point - first for point in support[1:4])
        )
        values: Any = np.array(
            tuple(
                float(np.dot(point, point) - np.dot(first, first))
                for point in support[1:4]
            )
        )
        if abs(float(np.linalg.det(matrix))) <= cls.EPSILON:
            return None
        center = np.linalg.solve(matrix, values)
        return SphereFit(
            (float(center[0]), float(center[1]), float(center[2])),
            float(np.linalg.norm(first - center)),
        )

    @classmethod
    def _contains(cls, sphere: SphereFit, point: Any) -> bool:
        center: Any = np.asarray(sphere.center, dtype=float)
        tolerance: float = cls.EPSILON * max(1.0, sphere.radius)
        return float(np.linalg.norm(np.asarray(point) - center)) <= sphere.radius + tolerance


class BoundingVolumeService:
    """Fit three convex envelopes and attach the smallest to one IFC product."""

    EPSILON = 1.0e-9
    OBJECT_TYPE = "INFOBIM_BOUNDING_VOLUME"

    def __init__(self, model: Any) -> None:
        self._model = model

    def select(self, target: Any) -> BoundingVolumeSelection:
        vertices, element_volume, unit_scale = self._geometry(target)
        candidates: Tuple[BoundingVolumeCandidate, ...] = (
            self._rectangular_cuboid(vertices),
            self._cylinder(vertices),
            self._sphere(vertices),
        )
        selected: BoundingVolumeCandidate = min(
            candidates, key=lambda candidate: candidate.volume
        )
        if selected.volume + self.EPSILON < element_volume:
            raise ValueError(
                "The selected bounding volume is smaller than the source element volume."
            )
        return BoundingVolumeSelection(
            selected=selected,
            candidates=candidates,
            element_volume=element_volume,
            project_unit_scale_to_si=unit_scale,
        )

    def attach(
        self, target: Any, selection: BoundingVolumeSelection
    ) -> BoundingVolumeRepresentation:
        product_shape: Any = getattr(target, "Representation", None)
        if product_shape is None or not product_shape.is_a("IfcProductDefinitionShape"):
            raise ValueError("The target element has no IfcProductDefinitionShape.")
        self._ensure_not_attached(target)

        body_representations: List[Any] = [
            representation
            for representation in product_shape.Representations or ()
            if str(getattr(representation, "RepresentationIdentifier", "") or "").lower()
            == "body"
        ]
        if not body_representations:
            raise ValueError("The target element has no Body representation.")
        context: Any = body_representations[0].ContextOfItems
        item, identifier, representation_type = self._create_item(selection.selected)
        shape_representation: Any = self._model.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationIdentifier=identifier,
            RepresentationType=representation_type,
            Items=[item],
        )
        description: str = (
            f"{selection.selected.kind.value} bounding volume; "
            f"volume={selection.selected.volume}; "
            f"extra_volume={selection.extra_volume}."
        )
        annotation_shape: Any = self._model.create_entity(
            "IfcProductDefinitionShape", Representations=[shape_representation]
        )
        annotation: Any = ifcopenshell.api.root.create_entity(
            self._model,
            ifc_class="IfcAnnotation",
            name=f"Bounding Volume — {str(getattr(target, 'Name', '') or target.GlobalId)}",
            predefined_type="USERDEFINED",
        )
        annotation.ObjectType = self.OBJECT_TYPE
        annotation.Representation = annotation_shape
        annotation.Description = description

        container: Any = ifcopenshell.util.element.get_container(target)
        if container is not None:
            ifcopenshell.api.spatial.assign_container(
                self._model, relating_structure=container, products=[annotation]
            )
        placement_matrix: Any = ifcopenshell.util.placement.get_local_placement(
            target.ObjectPlacement
        )
        ifcopenshell.api.geometry.edit_object_placement(
            self._model,
            product=annotation,
            matrix=placement_matrix,
            is_si=False,
            should_transform_children=False,
        )
        assignment: Any = self._model.create_entity(
            "IfcRelAssignsToProduct",
            GlobalId=ifcopenshell.guid.new(),
            Description=description,
            RelatedObjects=[annotation],
            RelatingProduct=target,
        )
        return BoundingVolumeRepresentation(
            annotation=annotation,
            shape_representation=shape_representation,
            representation_item=item,
            assignment=assignment,
        )

    def _geometry(self, target: Any) -> Tuple[Any, float, float]:
        placement: Any = getattr(target, "ObjectPlacement", None)
        if placement is None or not placement.is_a("IfcLocalPlacement"):
            raise ValueError("The target element has no IfcLocalPlacement.")

        settings: Any = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        try:
            shape: Any = ifcopenshell.geom.create_shape(settings, target)
        except Exception as error:
            raise ValueError("The target element has no usable Body geometry.") from error
        faces: List[int] = [int(index) for index in shape.geometry.faces]
        if not faces or not ifcopenshell.geom.tree.is_manifold(faces):
            raise ValueError(
                "Bounding-volume selection requires a closed manifold Body geometry."
            )

        unit_scale: float = float(
            ifcopenshell.util.unit.calculate_unit_scale(self._model, "LENGTHUNIT")
        )
        if unit_scale <= 0.0:
            raise ValueError("The IFC project has an invalid length-unit scale.")
        element_volume_si: float = float(ifcopenshell.util.shape.get_volume(shape.geometry))
        if element_volume_si <= self.EPSILON:
            raise ValueError("The target element Body has no positive enclosed volume.")

        vertices_si: Any = ifcopenshell.util.shape.get_shape_vertices(
            shape, shape.geometry
        )
        vertices_world: Any = np.asarray(vertices_si, dtype=float) / unit_scale
        placement_matrix: Any = np.asarray(
            ifcopenshell.util.placement.get_local_placement(placement), dtype=float
        )
        inverse_placement: Any = np.linalg.inv(placement_matrix)
        homogeneous: Any = np.column_stack(
            (vertices_world, np.ones(len(vertices_world), dtype=float))
        )
        vertices_local: Any = (inverse_placement @ homogeneous.T).T[:, :3]
        element_volume: float = element_volume_si / (unit_scale ** 3)
        return vertices_local, element_volume, unit_scale

    def _rectangular_cuboid(self, vertices: Any) -> BoundingVolumeCandidate:
        minimum: Any = np.min(vertices, axis=0)
        maximum: Any = np.max(vertices, axis=0)
        dimensions: Any = maximum - minimum
        if bool(np.any(dimensions <= self.EPSILON)):
            raise ValueError("The element cannot define a positive rectangular cuboid.")
        volume: float = float(np.prod(dimensions))
        return BoundingVolumeCandidate(
            kind=BoundingVolumeKind.RECTANGULAR_CUBOID,
            volume=volume,
            parameters={
                "corner": tuple(float(value) for value in minimum),
                "dimensions": tuple(float(value) for value in dimensions),
            },
        )

    def _cylinder(self, vertices: Any) -> BoundingVolumeCandidate:
        candidates: List[BoundingVolumeCandidate] = []
        for axis_index in range(3):
            radial_indexes: Tuple[int, int] = tuple(
                index for index in range(3) if index != axis_index
            )  # type: ignore[assignment]
            projected: Any = vertices[:, radial_indexes]
            circle: CircleFit = MinimumEnclosingCircle.fit(projected)
            axial_minimum: float = float(np.min(vertices[:, axis_index]))
            axial_maximum: float = float(np.max(vertices[:, axis_index]))
            height: float = axial_maximum - axial_minimum
            if height <= self.EPSILON or circle.radius <= self.EPSILON:
                continue
            bottom_center: List[float] = [0.0, 0.0, 0.0]
            bottom_center[axis_index] = axial_minimum
            bottom_center[radial_indexes[0]] = circle.center[0]
            bottom_center[radial_indexes[1]] = circle.center[1]
            axis: List[float] = [0.0, 0.0, 0.0]
            axis[axis_index] = 1.0
            reference: List[float] = [0.0, 0.0, 0.0]
            reference[radial_indexes[0]] = 1.0
            candidates.append(
                BoundingVolumeCandidate(
                    kind=BoundingVolumeKind.CYLINDER,
                    volume=math.pi * circle.radius * circle.radius * height,
                    parameters={
                        "bottom_center": tuple(bottom_center),
                        "axis": tuple(axis),
                        "reference_direction": tuple(reference),
                        "radius": circle.radius,
                        "height": height,
                    },
                )
            )
        if not candidates:
            raise ValueError("The element cannot define a positive bounding cylinder.")
        return min(candidates, key=lambda candidate: candidate.volume)

    def _sphere(self, vertices: Any) -> BoundingVolumeCandidate:
        sphere: SphereFit = MinimumEnclosingSphere.fit(vertices)
        if sphere.radius <= self.EPSILON:
            raise ValueError("The element cannot define a positive bounding sphere.")
        return BoundingVolumeCandidate(
            kind=BoundingVolumeKind.SPHERE,
            volume=(4.0 / 3.0) * math.pi * sphere.radius ** 3,
            parameters={"center": sphere.center, "radius": sphere.radius},
        )

    def _create_item(
        self, candidate: BoundingVolumeCandidate
    ) -> Tuple[Any, str, str]:
        if candidate.kind is BoundingVolumeKind.RECTANGULAR_CUBOID:
            corner: Point3D = candidate.parameters["corner"]
            dimensions: Point3D = candidate.parameters["dimensions"]
            item: Any = self._model.create_entity(
                "IfcBoundingBox",
                Corner=self._point(corner),
                XDim=dimensions[0],
                YDim=dimensions[1],
                ZDim=dimensions[2],
            )
            return item, "Box", "BoundingBox"

        if candidate.kind is BoundingVolumeKind.CYLINDER:
            item = self._model.create_entity(
                "IfcRightCircularCylinder",
                Position=self._placement(
                    candidate.parameters["bottom_center"],
                    candidate.parameters["axis"],
                    candidate.parameters["reference_direction"],
                ),
                Height=candidate.parameters["height"],
                Radius=candidate.parameters["radius"],
            )
            return item, "Reference", "CSG"

        item = self._model.create_entity(
            "IfcSphere",
            Position=self._placement(candidate.parameters["center"]),
            Radius=candidate.parameters["radius"],
        )
        return item, "Reference", "CSG"

    def _ensure_not_attached(self, target: Any) -> None:
        for assignment in self._model.by_type("IfcRelAssignsToProduct"):
            if assignment.RelatingProduct != target:
                continue
            for related in assignment.RelatedObjects or ():
                if related.is_a("IfcAnnotation") and str(
                    getattr(related, "ObjectType", "") or ""
                ) == self.OBJECT_TYPE:
                    raise ValueError(
                        "The target element already has an IFC bounding-volume annotation."
                    )

    def _point(self, coordinates: Point3D) -> Any:
        return self._model.create_entity(
            "IfcCartesianPoint", Coordinates=tuple(float(value) for value in coordinates)
        )

    def _placement(
        self,
        location: Point3D,
        axis: Point3D = (0.0, 0.0, 1.0),
        reference_direction: Point3D = (1.0, 0.0, 0.0),
    ) -> Any:
        return self._model.create_entity(
            "IfcAxis2Placement3D",
            Location=self._point(location),
            Axis=self._model.create_entity(
                "IfcDirection", DirectionRatios=tuple(float(value) for value in axis)
            ),
            RefDirection=self._model.create_entity(
                "IfcDirection",
                DirectionRatios=tuple(float(value) for value in reference_direction),
            ),
        )
