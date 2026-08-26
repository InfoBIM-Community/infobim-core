"""Geometric primitives and bounding-box services for IFC model manipulation.

Pure math (cross product, affine transforms) and ifcopenshell geometry
introspection are intentionally decoupled from any single capability, so
that annotation, clipping, surveying, framing and camera-target features
can reuse the same primitives without duplicating them inline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence, Tuple


@dataclass(frozen=True)
class ModelExtents:
    """Axis-aligned 3D bounding box of an IFC model in world coordinates."""

    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float

    @property
    def x_range(self) -> float:
        return self.max_x - self.min_x

    @property
    def y_range(self) -> float:
        return self.max_y - self.min_y

    @property
    def z_range(self) -> float:
        return self.max_z - self.min_z


@dataclass(frozen=True)
class PlacementFrame:
    """A right-handed (u, v) frame embedded in world 3D space.

    ``u_dir``/``v_dir`` become the grid's local X/Y axes; their cross
    product is the plane normal, which IFC needs as IfcAxis2Placement3D's
    Axis (local Z). Geometry authored in the simple local (u, v, 0) frame
    is rotated/translated into world space via :meth:`world_point` and
    :meth:`ifc_4x4_matrix`.
    """

    location: Tuple[float, float, float]
    u_dir: Tuple[float, float, float]
    v_dir: Tuple[float, float, float]

    @property
    def normal(self) -> Tuple[float, float, float]:
        ux, uy, uz = self.u_dir
        vx, vy, vz = self.v_dir
        return (
            uy * vz - uz * vy,
            uz * vx - ux * vz,
            ux * vy - uy * vx,
        )

    def world_point(self, u: float, v: float) -> Tuple[float, float, float]:
        return (
            self.location[0] + u * self.u_dir[0] + v * self.v_dir[0],
            self.location[1] + u * self.u_dir[1] + v * self.v_dir[1],
            self.location[2] + u * self.u_dir[2] + v * self.v_dir[2],
        )

    def ifc_4x4_matrix(self) -> Sequence[Sequence[float]]:
        """4x4 row-major matrix in the layout ifcopenshell ``edit_object_placement`` expects."""
        nx, ny, nz = self.normal
        return (
            (self.u_dir[0], self.v_dir[0], nx, self.location[0]),
            (self.u_dir[1], self.v_dir[1], ny, self.location[1]),
            (self.u_dir[2], self.v_dir[2], nz, self.location[2]),
            (0.0, 0.0, 0.0, 1.0),
        )


class ModelExtentsService:
    """Compute the world-space bounding box of an IFC model's rendered geometry."""

    @staticmethod
    def compute(model: Any, exclude_object_types: Sequence[str] = ()) -> ModelExtents:
        """Iterate every ``IfcProduct`` that carries geometry.

        Products derived from ``IfcGrid`` itself, and any product whose
        ``ObjectType`` matches ``exclude_object_types`` (e.g. reference-grid
        text labels, whose own margin-expanded geometry would otherwise
        inflate every subsequent recompute), are skipped.
        """
        import ifcopenshell.geom as geom

        excluded = set(exclude_object_types)
        settings = geom.settings()
        settings.set("use-world-coords", True)
        min_x = min_y = min_z = math.inf
        max_x = max_y = max_z = -math.inf
        found = False
        for product in model.by_type("IfcProduct"):
            if product.is_a("IfcGrid"):
                continue
            if excluded and str(getattr(product, "ObjectType", "") or "") in excluded:
                continue
            if not getattr(product, "Representation", None):
                continue
            try:
                shape = geom.create_shape(settings, product)
            except Exception:
                continue
            verts = shape.geometry.verts
            for i in range(0, len(verts), 3):
                x, y, z = verts[i], verts[i + 1], verts[i + 2]
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                min_z, max_z = min(min_z, z), max(max_z, z)
                found = True
        if not found:
            raise ValueError("No product with geometry was found to compute model extents from.")
        return ModelExtents(min_x, max_x, min_y, max_y, min_z, max_z)
